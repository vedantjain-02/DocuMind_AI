import json
import logging
import os
import re
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("documind.google_drive_mcp")

# Supported file types matching DocuMind AI pipeline
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".png", ".jpg", ".jpeg", ".webp"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

GOOGLE_DOCS_MIME = "application/vnd.google-apps.document"
GOOGLE_SHEETS_MIME = "application/vnd.google-apps.spreadsheet"
GOOGLE_SLIDES_MIME = "application/vnd.google-apps.presentation"
GOOGLE_FOLDER_MIME = "application/vnd.google-apps.folder"

MIME_TYPE_EXTENSIONS = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    GOOGLE_DOCS_MIME: ".pdf",  # Exported to PDF
}


class MCPError(Exception):
    """Base exception for MCP errors."""
    pass


class MCPConnectionError(MCPError):
    """Raised when the MCP server cannot be started or reached."""
    pass


class MCPAuthenticationError(MCPError):
    """Raised when Google Drive authentication is missing or invalid."""
    pass


class MCPDownloadError(MCPError):
    """Raised when a file download fails."""
    pass


class GoogleDriveMCPClient:
    """
    Client for the @piotr-agier/google-drive-mcp server communicating over stdio.
    Maintains a persistent JSON-RPC 2.0 connection with automatic reconnection.
    """

    def __init__(self, mcp_command: Optional[list[str]] = None):
        self._custom_command = mcp_command
        self._process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._request_counter = 0

    def _get_command(self) -> list[str]:
        if self._custom_command:
            return self._custom_command
        # Resolve npx for Windows and Unix
        npx_path = shutil.which("npx") or "npx"
        return [npx_path, "-y", "@piotr-agier/google-drive-mcp"]

    def _ensure_process(self) -> subprocess.Popen:
        """Starts or returns the running MCP server subprocess."""
        if self._process is not None and self._process.poll() is None:
            return self._process

        self._close_process()

        cmd = self._get_command()
        logger.info("[GoogleDriveMCP] Starting MCP server subprocess: %s", " ".join(cmd))

        try:
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=True,
                bufsize=1,
            )
        except Exception as err:
            logger.error("[GoogleDriveMCP] Failed to spawn MCP process: %s", err)
            raise MCPConnectionError(f"Failed to start Google Drive MCP server: {err}") from err

        # Perform MCP initialization handshake
        try:
            self._initialize_handshake()
        except Exception as err:
            self._close_process()
            raise MCPConnectionError(f"MCP server initialization failed: {err}") from err

        return self._process

    def _initialize_handshake(self) -> None:
        """Sends initialize request and initialized notification."""
        init_req = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "documind-ai", "version": "1.0.0"},
            },
        }
        resp = self._send_request_raw(init_req, timeout_seconds=30)
        if "error" in resp:
            raise MCPConnectionError(f"Initialize error: {resp['error']}")

        # Send initialized notification
        notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        self._send_notification_raw(notif)
        logger.info("[GoogleDriveMCP] Server initialized successfully.")

    def _next_id(self) -> int:
        self._request_counter += 1
        return self._request_counter

    def _send_notification_raw(self, msg: dict) -> None:
        if not self._process or not self._process.stdin:
            return
        payload = json.dumps(msg) + "\n"
        self._process.stdin.write(payload)
        self._process.stdin.flush()

    def _send_request_raw(self, msg: dict, timeout_seconds: int = 60) -> dict:
        req_id = msg.get("id")
        payload = json.dumps(msg) + "\n"

        if not self._process or not self._process.stdin or not self._process.stdout:
            raise MCPConnectionError("MCP process is not running.")

        self._process.stdin.write(payload)
        self._process.stdin.flush()

        import time
        start_time = time.time()

        while True:
            if time.time() - start_time > timeout_seconds:
                raise TimeoutError(f"Timed out waiting for response to request ID {req_id}")

            line = self._process.stdout.readline()
            if not line:
                returncode = self._process.poll()
                raise MCPConnectionError(
                    f"MCP process closed stdout unexpectedly (exit code: {returncode})"
                )

            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                # Some servers print status messages on stdout before protocol starts
                continue

            if isinstance(data, dict) and data.get("id") == req_id:
                return data

    def call_tool(self, tool_name: str, arguments: dict, timeout_seconds: int = 90) -> dict:
        """Calls a tool on the MCP server and returns the result."""
        with self._lock:
            proc = self._ensure_process()
            req_id = self._next_id()
            req = {
                "jsonrpc": "2.0",
                "id": req_id,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            }

            try:
                resp = self._send_request_raw(req, timeout_seconds=timeout_seconds)
            except (TimeoutError, MCPConnectionError) as err:
                self._close_process()
                raise MCPConnectionError(f"MCP tool call '{tool_name}' failed: {err}") from err

            if "error" in resp:
                err_data = resp["error"]
                raise MCPError(f"MCP tool error ({err_data.get('code')}): {err_data.get('message')}")

            result = resp.get("result", {})
            if result.get("isError"):
                content = result.get("content", [])
                err_text = ""
                for c in content:
                    if c.get("type") == "text":
                        err_text += c.get("text", "")
                raise MCPError(err_text or f"Tool {tool_name} returned an error")

            return result

    def check_status(self) -> dict:
        """
        Queries authGetStatus to verify authentication.
        Does NOT expose access tokens, refresh tokens, or credentials.
        """
        try:
            result = self.call_tool("authGetStatus", {}, timeout_seconds=20)
            content = result.get("content", [])
            text = ""
            for item in content:
                if item.get("type") == "text":
                    text += item.get("text", "")

            # Check for email and auth status
            email_match = re.search(r'"emailAddress":\s*"([^"]+)"', text)
            display_name_match = re.search(r'"displayName":\s*"([^"]+)"', text)
            has_token = "tokenFileExists\": true" in text or "hasAccessToken\": true" in text or "mode=oauth" in text

            email = email_match.group(1) if email_match else None
            display_name = display_name_match.group(1) if display_name_match else None

            if not has_token:
                return {
                    "connected": True,
                    "authenticated": False,
                    "identity": None,
                    "message": "Google Drive authentication token not found or expired.",
                }

            return {
                "connected": True,
                "authenticated": True,
                "identity": email or display_name or "Connected User",
                "display_name": display_name,
                "message": f"Connected as {email or display_name or 'Google Account'}",
            }
        except Exception as err:
            logger.warning("[GoogleDriveMCP] Status check failed: %s", err)
            return {
                "connected": False,
                "authenticated": False,
                "identity": None,
                "message": f"Google Drive MCP server unavailable: {str(err)}",
            }

    def list_files(
        self,
        query: str = "",
        page_size: int = 50,
        page_token: Optional[str] = None,
    ) -> dict:
        """
        Searches or lists accessible files in Google Drive.
        Parses output and annotates with DocuMind support metadata.
        """
        # Build search query
        if query and query.strip():
            clean_q = query.strip().replace("'", "\\'")
            drive_query = f"name contains '{clean_q}' and trashed = false"
        else:
            drive_query = "trashed = false"

        args: dict[str, Any] = {
            "query": drive_query,
            "rawQuery": True,
            "pageSize": min(max(page_size, 1), 100),
            "orderBy": "modifiedTime desc",
        }
        if page_token:
            args["pageToken"] = page_token

        result = self.call_tool("search", args, timeout_seconds=45)
        content = result.get("content", [])
        text = ""
        for item in content:
            if item.get("type") == "text":
                text += item.get("text", "")

        files, next_page_token = self._parse_file_list_text(text)
        return {
            "files": files,
            "next_page_token": next_page_token,
            "count": len(files),
        }

    def _parse_file_list_text(self, text: str) -> tuple[list[dict], Optional[str]]:
        """Parses the text output of search tool into a list of file dictionaries."""
        files: list[dict] = []
        next_page_token: Optional[str] = None

        # Line pattern:
        # <name> (<mimeType>) [id: <id>, path: <path>] [created: <c>, modified: <m>] [size: <s>]
        pattern = re.compile(
            r"^(?P<name>.+?)\s+\((?P<mime>[^)]+)\)\s+\[id:\s*(?P<id>[^,\]]+)"
            r"(?:,\s*path:\s*(?P<path>[^\]]*))?\]"
            r"(?:\s+\[created:\s*(?P<created>[^,\]]+)(?:,\s*modified:\s*(?P<modified>[^\]]+))?\])?"
            r"(?:\s+\[size:\s*(?P<size>[^\]]+)\])?",
            re.MULTILINE,
        )

        for match in pattern.finditer(text):
            name = match.group("name").strip()
            mime = match.group("mime").strip()
            file_id = match.group("id").strip()
            path = (match.group("path") or "").strip()
            created = (match.group("created") or "").strip()
            modified = (match.group("modified") or "").strip()
            size_str = (match.group("size") or "").strip()

            # Skip folders in document list
            if mime == GOOGLE_FOLDER_MIME:
                continue

            # Determine file extension and support status
            ext = Path(name).suffix.lower()
            is_gdoc = mime == GOOGLE_DOCS_MIME
            is_supported = (
                ext in SUPPORTED_EXTENSIONS
                or mime in MIME_TYPE_EXTENSIONS
                or is_gdoc
            )

            file_type = "gdoc" if is_gdoc else (ext.lstrip(".") or mime.split("/")[-1])

            files.append({
                "id": file_id,
                "name": name,
                "mime_type": mime,
                "file_type": file_type,
                "path": path,
                "created": created,
                "modified": modified,
                "size": size_str,
                "is_supported": is_supported,
                "is_gdoc": is_gdoc,
            })

        # Check for page token
        token_match = re.search(r"pageToken:\s*([^\s\r\n]+)", text)
        if token_match:
            next_page_token = token_match.group(1).strip()

        return files, next_page_token

    def download_file(
        self,
        file_id: str,
        target_path: Path,
        export_mime_type: Optional[str] = None,
    ) -> Path:
        """
        Downloads a Google Drive file to target_path using the downloadFile MCP tool.
        For Google Docs, exports to PDF.
        """
        target_path.parent.mkdir(parents=True, exist_ok=True)
        local_path_str = str(target_path.resolve())

        args: dict[str, Any] = {
            "fileId": file_id,
            "localPath": local_path_str,
            "overwrite": True,
        }
        if export_mime_type:
            args["exportMimeType"] = export_mime_type

        logger.info("[GoogleDriveMCP] Downloading file %s to %s", file_id, local_path_str)
        try:
            result = self.call_tool("downloadFile", args, timeout_seconds=120)
        except Exception as err:
            logger.error("[GoogleDriveMCP] Download failed for %s: %s", file_id, err)
            raise MCPDownloadError(f"Failed to download file from Google Drive: {err}") from err

        if not target_path.exists():
            raise MCPDownloadError(f"File was not saved to expected path: {target_path}")

        if target_path.stat().st_size == 0:
            target_path.unlink(missing_ok=True)
            raise MCPDownloadError("Downloaded file is empty (0 bytes).")

        logger.info(
            "[GoogleDriveMCP] Successfully downloaded %s (%d bytes)",
            target_path.name,
            target_path.stat().st_size,
        )
        return target_path

    def _close_process(self) -> None:
        """Gracefully terminates the MCP server process."""
        if self._process is not None:
            try:
                self._process.terminate()
                self._process.wait(timeout=3)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None

    def close(self) -> None:
        with self._lock:
            self._close_process()


# Singleton client instance
_client_instance: Optional[GoogleDriveMCPClient] = None
_client_lock = threading.Lock()


def get_google_drive_mcp_client() -> GoogleDriveMCPClient:
    global _client_instance
    with _client_lock:
        if _client_instance is None:
            _client_instance = GoogleDriveMCPClient()
        return _client_instance
