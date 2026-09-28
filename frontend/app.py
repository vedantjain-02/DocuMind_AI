import base64
import hashlib
import html
import json
import logging
import re
from io import BytesIO
from pathlib import Path
from typing import Any

import fitz
from PIL import Image
import requests
import streamlit as st
import streamlit.components.v1 as components


# ============================================================================
# CONFIGURATION
# ============================================================================

LOGGER = logging.getLogger("documind.frontend")

BACKEND_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="DocuMind AI",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================================
# PROFESSIONAL DARK THEME (Linear / Notion / Perplexity AI Workspace)
# ============================================================================

APP_CSS = """
:root {
  --bg: #070a14;
  --bg-subtle: #0d1326;
  --panel: #0d1428;
  --panel-elevated: #131d38;
  --panel-hover: #192548;
  --border: #1a2544;
  --border-subtle: rgba(255, 255, 255, 0.07);
  --border-focus: #6366f1;
  --text: #f8fafc;
  --text-muted: #8899b7;
  --muted: #627293;
  --primary: #6366f1;
  --primary-hover: #4f46e5;
  --primary-light: rgba(99, 102, 241, 0.14);
  --primary-glow: rgba(99, 102, 241, 0.35);
  --accent-cyan: #06b6d4;
  --accent-purple: #8b5cf6;
  --success: #10b981;
  --success-bg: rgba(16, 185, 129, 0.12);
  --warning: #f59e0b;
  --warning-bg: rgba(245, 158, 11, 0.12);
  --highlight: #fbbf24;
  --highlight-bg: rgba(251, 191, 36, 0.16);
  --danger: #ef4444;
  --font-stack: "Inter", ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
  font-family: var(--font-stack) !important;
  color: var(--text);
  -webkit-font-smoothing: antialiased;
}

/* Base application background with deep ambient lighting */
.stApp {
  background:
    radial-gradient(ellipse 90% 45% at 85% -15%, rgba(99, 102, 241, 0.15), transparent 60%),
    radial-gradient(ellipse 70% 35% at 10% 105%, rgba(139, 92, 246, 0.10), transparent 50%),
    var(--bg) !important;
  color: var(--text);
}

/* Hide Streamlit default chrome */
[data-testid="stHeader"] {
  background: transparent !important;
  height: 2rem !important;
}
#MainMenu, footer, .stDeployButton {
  display: none !important;
  visibility: hidden !important;
}
[data-testid="stToolbar"] {
  display: none !important;
}

/* Clean up main container layout */
.block-container {
  padding-top: 0.85rem !important;
  padding-bottom: 1.75rem !important;
  padding-left: 2rem !important;
  padding-right: 2rem !important;
  max-width: 100% !important;
}

/* Custom sleek scrollbar */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: rgba(10, 15, 30, 0.4);
}
::-webkit-scrollbar-thumb {
  background: #1f2b4c;
  border-radius: 999px;
}
::-webkit-scrollbar-thumb:hover {
  background: #334470;
}

/* ==========================================================================
   WORKSPACE HEADER (TOP BAR)
   ========================================================================== */
.workspace-header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(13, 20, 40, 0.75);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 8px 16px;
  margin-bottom: 16px;
  gap: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
}
.header-left-brand {
  display: flex;
  align-items: center;
  gap: 10px;
}
.brand-glyph {
  width: 32px;
  height: 32px;
  border-radius: 9px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4);
}
.brand-text-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}
.brand-name {
  font-size: 16px;
  font-weight: 800;
  letter-spacing: -0.4px;
  color: #ffffff;
}
.brand-badge {
  font-size: 9.5px;
  font-weight: 800;
  letter-spacing: 1.2px;
  padding: 2px 7px;
  border-radius: 6px;
  background: rgba(99, 102, 241, 0.18);
  border: 1px solid rgba(99, 102, 241, 0.35);
  color: #a5b4fc;
}
.header-center-info {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
}
.header-active-doc {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  background: rgba(22, 33, 62, 0.6);
  border: 1px solid rgba(99, 102, 241, 0.3);
  padding: 4px 12px;
  border-radius: 999px;
  font-size: 12px;
}
.header-doc-icon {
  font-size: 13px;
}
.header-doc-name {
  font-weight: 600;
  color: #e2e8f0;
}
.header-doc-meta {
  color: var(--muted);
  font-size: 11px;
}
.header-source-pill {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 999px;
}
.header-source-pill.local {
  background: rgba(99, 102, 241, 0.2);
  color: #a5b4fc;
  border: 1px solid rgba(99, 102, 241, 0.4);
}
.header-source-pill.drive {
  background: rgba(56, 189, 248, 0.15);
  color: #7dd3fc;
  border: 1px solid rgba(56, 189, 248, 0.35);
}
.header-empty-doc {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--muted);
  font-size: 12px;
}
.header-empty-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #475569;
}
.header-right-status {
  display: flex;
  align-items: center;
  gap: 10px;
}
.header-status-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 999px;
}
.header-status-chip.success {
  background: rgba(16, 185, 129, 0.14);
  border: 1px solid rgba(16, 185, 129, 0.35);
  color: #6ee7b7;
}
.header-status-chip.ready {
  background: rgba(99, 102, 241, 0.12);
  border: 1px solid rgba(99, 102, 241, 0.28);
  color: #a5b4fc;
}
.header-doc-count {
  font-size: 11px;
  font-weight: 600;
  color: var(--muted);
  background: rgba(255, 255, 255, 0.04);
  padding: 3px 8px;
  border-radius: 6px;
  border: 1px solid var(--border-subtle);
}
.chip-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 6px rgba(16, 185, 129, 0.8);
}

/* ==========================================================================
   SIDEBAR STYLING
   ========================================================================== */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #090e1e 0%, #0c1228 100%) !important;
  border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] > div:first-child {
  padding: 16px 14px !important;
}
[data-testid="stSidebar"] * {
  color: #dfe6f5;
}

.sidebar-brand-wrapper {
  display: flex;
  align-items: center;
  gap: 11px;
  margin-bottom: 14px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.sidebar-logo {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #6366f1, #06b6d4);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  box-shadow: 0 4px 16px rgba(99, 102, 241, 0.4);
}
.sidebar-brand-title {
  font-size: 16px;
  font-weight: 800;
  color: #ffffff;
  letter-spacing: -0.3px;
  line-height: 1.2;
}
.sidebar-brand-desc {
  font-size: 11px;
  color: var(--muted);
  line-height: 1.3;
}

.sidebar-section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #64748b;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 1.2px;
  text-transform: uppercase;
  margin: 18px 0 8px 2px;
}
.sidebar-section-header::after {
  content: "";
  flex: 1;
  height: 1px;
  background: rgba(255, 255, 255, 0.06);
}

/* Sidebar buttons */
[data-testid="stSidebar"] .stButton > button {
  background: #10182f;
  color: #cbd5e1;
  border: 1px solid #1e2b4d;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  min-height: 32px;
  padding: 4px 10px;
  transition: all 0.15s ease;
  text-align: left;
}
[data-testid="stSidebar"] .stButton > button:hover {
  background: #172448;
  color: #ffffff;
  border-color: #6366f1;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
  background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%) !important;
  border: 1px solid rgba(255, 255, 255, 0.18) !important;
  color: #ffffff !important;
  box-shadow: 0 2px 12px rgba(99, 102, 241, 0.35);
  font-weight: 600;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
  background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%) !important;
  box-shadow: 0 4px 16px rgba(99, 102, 241, 0.5);
}

/* Sidebar Popover (for chat rename/delete) */
[data-testid="stSidebar"] [data-testid="stPopover"] > button {
  min-height: 32px !important;
  height: 32px !important;
  padding: 0 !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  background: #10182f !important;
  border: 1px solid #1e2b4d !important;
  color: #64748b !important;
  border-radius: 8px !important;
}
[data-testid="stSidebar"] [data-testid="stPopover"] > button:hover {
  color: #ffffff !important;
  border-color: #6366f1 !important;
  background: #172448 !important;
}

/* Sidebar Document Cards */
.sidebar-doc-card {
  background: #0f172f;
  border: 1px solid #1e2b4d;
  border-radius: 9px;
  padding: 8px 10px;
  margin-bottom: 6px;
  transition: all 0.15s ease;
}
.sidebar-doc-card:hover {
  border-color: #3b4d79;
  background: #141f3d;
}
.sidebar-doc-card.active {
  border-color: #6366f1;
  background: rgba(99, 102, 241, 0.12);
  box-shadow: 0 0 12px rgba(99, 102, 241, 0.22);
}
.sidebar-doc-top {
  display: flex;
  align-items: center;
  gap: 8px;
}
.sidebar-doc-glyph {
  font-size: 15px;
  flex-shrink: 0;
}
.sidebar-doc-info {
  flex: 1;
  min-width: 0;
}
.sidebar-doc-name {
  font-size: 12px;
  font-weight: 600;
  color: #f1f5f9;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.3;
}
.sidebar-doc-meta {
  font-size: 10px;
  color: var(--muted);
  line-height: 1.2;
}
.doc-active-pill {
  font-size: 9px;
  font-weight: 800;
  color: #a5b4fc;
  background: rgba(99, 102, 241, 0.25);
  border: 1px solid rgba(99, 102, 241, 0.45);
  padding: 2px 6px;
  border-radius: 999px;
  letter-spacing: 0.5px;
}

/* Tabs in Sidebar */
[data-testid="stSidebar"] [data-baseweb="tab-list"] {
  background: #0b1122 !important;
  border: 1px solid var(--border) !important;
  border-radius: 8px !important;
  padding: 3px !important;
  gap: 2px !important;
}
[data-testid="stSidebar"] [data-baseweb="tab"] {
  border-radius: 6px !important;
  font-size: 11.5px !important;
  font-weight: 600 !important;
  color: #8899b7 !important;
  padding: 5px 10px !important;
  border: none !important;
}
[data-testid="stSidebar"] [data-baseweb="tab"][aria-selected="true"] {
  background: #172448 !important;
  color: #ffffff !important;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3) !important;
}
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] {
  display: none !important;
}

/* File Uploader Dropzone */
[data-testid="stFileUploader"] {
  background: rgba(14, 21, 41, 0.7) !important;
  border: 1px dashed rgba(99, 102, 241, 0.35) !important;
  border-radius: 10px !important;
  padding: 10px !important;
  transition: all 0.2s ease !important;
}
[data-testid="stFileUploader"]:hover {
  border-color: #6366f1 !important;
  background: rgba(99, 102, 241, 0.08) !important;
}
[data-testid="stFileUploader"] section {
  padding: 2px !important;
}

/* ==========================================================================
   MAIN WORKSPACE PANELS & CONTAINERS
   ========================================================================== */
[data-testid="stVerticalBlockBorderWrapper"] {
  background: rgba(12, 18, 35, 0.7) !important;
  backdrop-filter: blur(14px) !important;
  -webkit-backdrop-filter: blur(14px) !important;
  border: 1px solid var(--border) !important;
  border-radius: 14px !important;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35) !important;
}

.panel-header-wrap {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  padding: 2px 2px;
}
.panel-kicker {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 1.4px;
  color: #818cf8;
  text-transform: uppercase;
  margin-bottom: 2px;
}
.panel-heading {
  font-size: 16px;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: -0.2px;
  line-height: 1.3;
}
.panel-badges {
  display: flex;
  align-items: center;
  gap: 6px;
}
.panel-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}
.panel-badge.badge-ready {
  background: rgba(16, 185, 129, 0.14);
  border: 1px solid rgba(16, 185, 129, 0.35);
  color: #6ee7b7;
}
.panel-badge.badge-local {
  background: rgba(99, 102, 241, 0.14);
  border: 1px solid rgba(99, 102, 241, 0.35);
  color: #a5b4fc;
}
.panel-badge.badge-drive {
  background: rgba(56, 189, 248, 0.14);
  border: 1px solid rgba(56, 189, 248, 0.35);
  color: #7dd3fc;
}
.panel-badge.badge-pages {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--muted);
}

.pulse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 8px rgba(16, 185, 129, 0.85);
  animation: pulse-glow 2s infinite ease-in-out;
}
@keyframes pulse-glow {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.8); }
}

/* ==========================================================================
   DOCUMENT CANVAS & VIEWER
   ========================================================================== */
.pdf-canvas-wrapper {
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 16px;
  background: rgba(6, 10, 20, 0.6);
  border-radius: 10px;
  margin: 10px 0;
  border: 1px solid rgba(255, 255, 255, 0.04);
}
.pdf-paper {
  background: #ffffff;
  border-radius: 6px;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.75), 0 2px 6px rgba(0, 0, 0, 0.4);
  padding: 0;
  max-width: 100%;
  overflow: hidden;
  line-height: 0;
}
.pdf-paper img {
  display: block;
  border-radius: 6px;
}

.page-counter-badge {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 38px;
  font-size: 11.5px;
  font-weight: 600;
  color: var(--muted);
  background: #10172e;
  border: 1px solid #1e2b4d;
  border-radius: 8px;
}

.source-highlight-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 12px;
  margin-top: 8px;
  margin-bottom: 8px;
}
.source-highlight-banner.active {
  background: rgba(251, 191, 36, 0.14);
  border: 1px solid rgba(251, 191, 36, 0.45);
  color: #fde68a;
}
.source-highlight-banner.warning {
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.35);
  color: #fca5a5;
}

/* Empty states */
.workspace-empty-card {
  text-align: center;
  padding: 60px 24px;
}
.empty-card-glyph {
  font-size: 44px;
  margin-bottom: 14px;
}
.empty-card-title {
  font-size: 18px;
  font-weight: 700;
  color: #f1f5f9;
  margin-bottom: 6px;
}
.empty-card-subtitle {
  font-size: 12.5px;
  color: var(--muted);
  line-height: 1.6;
  max-width: 380px;
  margin: 0 auto 16px;
}
.empty-card-formats {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-bottom: 16px;
}
.format-pill {
  font-size: 10.5px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 6px;
  background: #131d38;
  border: 1px solid #233157;
  color: #94a3b8;
}
.empty-card-tip {
  font-size: 11px;
  color: #64748b;
  line-height: 1.6;
}

/* ==========================================================================
   AI CHAT & SOURCES
   ========================================================================== */
[data-testid="stChatMessage"] {
  background: #0e162f !important;
  border: 1px solid #1f2c4e !important;
  border-radius: 12px !important;
  padding: 12px 14px !important;
  margin-bottom: 10px !important;
}
[data-testid="stChatMessage"] p {
  font-size: 13px !important;
  line-height: 1.75 !important;
  color: #e2e8f0 !important;
}
[data-testid="stChatMessage"] code {
  background: #182242 !important;
  color: #c7d2fe !important;
  border: 1px solid #2a3962 !important;
  border-radius: 4px !important;
  padding: 2px 6px !important;
  font-size: 12px !important;
}

.chat-empty-state {
  text-align: center;
  padding: 50px 20px;
}
.chat-empty-icon {
  font-size: 38px;
  margin-bottom: 10px;
}
.chat-empty-title {
  font-size: 17px;
  font-weight: 700;
  color: #f1f5f9;
  margin-bottom: 6px;
}
.chat-empty-desc {
  font-size: 12px;
  color: var(--muted);
  line-height: 1.6;
  max-width: 320px;
  margin: 0 auto 16px;
}
.chat-suggestions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 320px;
  margin: 0 auto;
}
.suggestion-chip {
  background: #101830;
  border: 1px solid #202d50;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 11.5px;
  color: #94a3b8;
  text-align: left;
}

/* Source citations */
.sources-container-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 14px 0 6px;
  padding-bottom: 4px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.sources-title {
  font-size: 10.5px;
  font-weight: 800;
  letter-spacing: 0.8px;
  text-transform: uppercase;
  color: #818cf8;
}
.sources-count {
  font-size: 10px;
  background: rgba(99, 102, 241, 0.16);
  color: #a5b4fc;
  padding: 2px 7px;
  border-radius: 999px;
  font-weight: 700;
}
.source-card-wrap {
  margin-top: 6px;
  margin-bottom: 4px;
}
.source-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 2px;
}
.source-badge-pill {
  font-size: 10px;
  font-weight: 700;
  color: #818cf8;
  letter-spacing: 0.5px;
}
.source-active-pill {
  font-size: 9px;
  font-weight: 800;
  color: #fbbf24;
  background: rgba(251, 191, 36, 0.16);
  border: 1px solid rgba(251, 191, 36, 0.4);
  padding: 2px 6px;
  border-radius: 999px;
}
.source-preview {
  color: #cbd5e1;
  font-size: 11.5px;
  line-height: 1.65;
  padding: 8px 12px;
  border-left: 3px solid #6366f1;
  background: rgba(14, 21, 41, 0.8);
  border-radius: 0 8px 8px 0;
  margin-top: 4px;
  margin-bottom: 10px;
}

/* Chat Input Bar */
[data-testid="stChatInput"] {
  padding-top: 8px;
}
[data-testid="stChatInput"] textarea {
  background: #0c1328 !important;
  color: #f8fafc !important;
  border: 1px solid #233156 !important;
  border-radius: 12px !important;
  font-size: 13.5px !important;
  padding: 12px 14px !important;
}
[data-testid="stChatInput"] textarea:focus {
  border-color: #6366f1 !important;
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.25) !important;
}

/* Global button styling */
.stButton > button {
  background: #111a33;
  color: #dbe3f3;
  border: 1px solid #253358;
  border-radius: 8px;
  font-weight: 600;
  min-height: 36px;
  transition: all 0.15s ease;
}
.stButton > button:hover {
  background: #192548;
  color: #ffffff;
  border-color: #6366f1;
}
.stButton > button[kind="primary"] {
  background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
  border: 1px solid rgba(255, 255, 255, 0.15) !important;
  color: #ffffff !important;
  box-shadow: 0 2px 12px rgba(99, 102, 241, 0.35);
}
.stButton > button[kind="primary"]:hover {
  background: linear-gradient(135deg, #4f46e5, #7c3aed) !important;
  box-shadow: 0 4px 16px rgba(99, 102, 241, 0.5);
}

/* Global overflow and production layout hardening */
html, body, #root, [data-testid="stAppViewContainer"], [data-testid="stAppViewBlockContainer"] {
  max-width: 100% !important;
  overflow-x: hidden !important;
}
[data-testid="stMainBlockContainer"], .block-container {
  width: 100% !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
  overflow-x: hidden !important;
}
[data-testid="stHorizontalBlock"] {
  max-width: 100% !important;
  min-width: 0 !important;
  box-sizing: border-box !important;
}
[data-testid="stColumn"] {
  min-width: 0 !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
}
iframe {
  max-width: 100% !important;
  border: 0 !important;
}

/* Native workspace header */
.workspace-native-header {
  background: linear-gradient(135deg, rgba(15,23,48,.96), rgba(10,16,34,.96));
  border: 1px solid rgba(99,102,241,.24);
  border-radius: 16px;
  padding: 14px 16px;
  margin: 0 0 18px 0;
  box-shadow: 0 12px 35px rgba(0,0,0,.25), inset 0 1px 0 rgba(255,255,255,.035);
}
.workspace-native-label {
  color: #818cf8;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 1.25px;
  text-transform: uppercase;
  margin-bottom: 3px;
}
.workspace-native-name {
  color: #f8fafc;
  font-size: 15px;
  font-weight: 750;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.workspace-native-meta {
  color: #64748b;
  font-size: 11px;
  margin-top: 3px;
}
.workspace-native-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 9px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
  border: 1px solid rgba(255,255,255,.08);
  background: rgba(255,255,255,.035);
  color: #cbd5e1;
}
.workspace-native-chip.drive {
  color: #7dd3fc;
  background: rgba(56,189,248,.08);
  border-color: rgba(56,189,248,.22);
}
.workspace-native-chip.local {
  color: #a5b4fc;
  background: rgba(99,102,241,.08);
  border-color: rgba(99,102,241,.22);
}
.workspace-native-chip.ready {
  color: #6ee7b7;
  background: rgba(16,185,129,.08);
  border-color: rgba(16,185,129,.22);
}
.workspace-native-chip .dot {
  width: 6px; height: 6px; border-radius: 50%; background: currentColor;
}
.workspace-native-divider {
  height: 1px;
  background: rgba(255,255,255,.06);
  margin: 10px 0;
}

/* Cleaner native Streamlit controls */
[data-testid="stNumberInput"] input,
[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] [data-baseweb="select"] > div {
  background: #0d152b !important;
  color: #f8fafc !important;
  border-color: #253358 !important;
}

/* Responsive adjustment */
@media (max-width: 991px) {
  .block-container {
    padding-left: 1rem !important;
    padding-right: 1rem !important;
  }
  .workspace-header-bar {
    flex-direction: column;
    align-items: flex-start;
  }
}
"""

st.markdown(
    f"<style>{APP_CSS}</style>",
    unsafe_allow_html=True,
)


# ============================================================================
# SESSION STATE
# ============================================================================

DEFAULT_STATE = {
    "document_id": None,
    "filename": None,
    "pdf_bytes": None,
    "image_bytes": None,
    "documents": [],
    "documents_needs_refresh": True,
    "processed_file_fingerprints": set(),
    "upload_statuses": [],
    "messages": [],
    "conversation_id": None,
    "conversation_title": "New chat",
    "conversations": [],
    "current_page": 1,
    "page_input": 1,
    "highlight_text": "",
    "active_source_key": None,
    "pending_page": None,
    "upload_key": 0,
    "total_pages": 0,
    "total_chunks": 0,
    "drive_status": None,
    "drive_files": [],
    "drive_search_query": "",
    "drive_loaded": False,
    "drive_error": None,
    "drive_browser_open": False,
    "selected_drive_file_id": None,
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================================
# GENERAL HELPERS
# ============================================================================

def safe_text(value: Any) -> str:
    return str(value or "").strip()


def escape_html(value: Any) -> str:
    return html.escape(str(value or ""))


def compute_file_fingerprint(uploaded_file) -> str:
    file_bytes = uploaded_file.getvalue()
    digest = hashlib.sha256(file_bytes).hexdigest()
    return f"{uploaded_file.name}:{uploaded_file.size}:{digest}"


def truncate_display(text: Any, limit: int = 32) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "…"


def auto_title(question: str, limit: int = 40) -> str:
    title = " ".join(str(question or "").split())
    if len(title) > limit:
        title = title[:limit].rstrip() + "…"
    return title if title else "New chat"


def reset_document_viewer():
    st.session_state.pdf_bytes = None
    st.session_state.image_bytes = None
    st.session_state.current_page = 1
    st.session_state.page_input = 1
    st.session_state.pending_page = None
    st.session_state.highlight_text = ""
    st.session_state.active_source_key = None
    st.session_state.selected_source_bbox = None
    st.session_state.selected_source_bboxes = []
    st.session_state.selected_source_dimensions = None
    st.session_state.selected_source_confidence = None
    st.session_state.selected_source_match_type = None
    st.session_state.total_pages = 0
    st.session_state.total_chunks = 0


def clear_highlight():
    st.session_state.highlight_text = ""
    st.session_state.active_source_key = None
    st.session_state.selected_source_bbox = None
    st.session_state.selected_source_bboxes = []
    st.session_state.selected_source_dimensions = None
    st.session_state.selected_source_confidence = None
    st.session_state.selected_source_match_type = None


# ============================================================================
# DOCUMENT API
# ============================================================================

def fetch_selected_document_bytes(document_id: str):
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/documents/{document_id}/file",
            timeout=60,
        )
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException:
        return None


def refresh_documents():
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/documents",
            timeout=30,
        )
        response.raise_for_status()

        documents = response.json() or []
        st.session_state.documents = documents
        st.session_state.documents_needs_refresh = False

        if not documents:
            st.session_state.document_id = None
            st.session_state.filename = None
            reset_document_viewer()
            return

        active_ids = {
            item.get("document_id")
            for item in documents
            if isinstance(item, dict)
        }

        if st.session_state.document_id not in active_ids:
            selected = documents[-1]
            st.session_state.document_id = selected.get("document_id")

        selected = next(
            (
                item
                for item in documents
                if item.get("document_id") == st.session_state.document_id
            ),
            documents[-1],
        )

        st.session_state.document_id = selected.get("document_id")
        st.session_state.filename = selected.get("filename")
        st.session_state.total_pages = selected.get("total_pages", 0)
        st.session_state.total_chunks = selected.get("total_chunks", 0)

        if st.session_state.filename and not st.session_state.pdf_bytes and not st.session_state.image_bytes:
            filename_lower = st.session_state.filename.lower()
            if filename_lower.endswith(".pdf"):
                st.session_state.pdf_bytes = fetch_selected_document_bytes(
                    st.session_state.document_id
                )
            elif any(filename_lower.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp")):
                st.session_state.image_bytes = fetch_selected_document_bytes(
                    st.session_state.document_id
                )


    except requests.exceptions.RequestException:
        st.session_state.documents = []
        st.session_state.documents_needs_refresh = False


def delete_document(document_id: str):
    try:
        response = requests.delete(
            f"{BACKEND_URL}/api/documents/{document_id}",
            timeout=30,
        )
        response.raise_for_status()

        if st.session_state.document_id == document_id:
            st.session_state.document_id = None
            st.session_state.filename = None
            reset_document_viewer()

        st.session_state.documents_needs_refresh = True
        refresh_documents()
        st.rerun()

    except requests.exceptions.RequestException as error:
        st.error(f"Document removal failed: {error}")


def clear_all_documents():
    try:
        response = requests.delete(
            f"{BACKEND_URL}/api/documents",
            timeout=30,
        )
        response.raise_for_status()

        st.session_state.document_id = None
        st.session_state.filename = None
        st.session_state.documents = []
        st.session_state.processed_file_fingerprints = set()
        st.session_state.upload_statuses = []
        reset_document_viewer()

        st.session_state.documents_needs_refresh = True
        refresh_documents()
        st.rerun()

    except requests.exceptions.RequestException as error:
        st.error(f"Workspace clear failed: {error}")


def activate_document(document: dict):
    document_id = document.get("document_id")
    filename = document.get("filename", "Document")
    st.session_state.document_id = document_id
    st.session_state.filename = filename
    st.session_state.total_pages = document.get("total_pages", 0)
    st.session_state.total_chunks = document.get("total_chunks", 0)
    reset_document_viewer()

    filename_lower = filename.lower()
    if filename_lower.endswith(".pdf"):
        st.session_state.pdf_bytes = fetch_selected_document_bytes(document_id)
    elif any(filename_lower.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp")):
        st.session_state.image_bytes = fetch_selected_document_bytes(document_id)



# ============================================================================
# GOOGLE DRIVE API & HELPERS
# ============================================================================

def fetch_drive_status():
    try:
        response = requests.get(f"{BACKEND_URL}/api/drive/status", timeout=15)
        if response.ok:
            data = response.json()
            st.session_state.drive_status = data
            return data
    except Exception as err:
        LOGGER.warning("Could not fetch Google Drive status: %s", err)
        st.session_state.drive_status = {
            "connected": False,
            "authenticated": False,
            "message": f"Backend connection error: {err}",
        }
    return st.session_state.drive_status


def fetch_drive_files(query: str = ""):
    try:
        params = {}
        if query and query.strip():
            params["query"] = query.strip()
        response = requests.get(f"{BACKEND_URL}/api/drive/files", params=params, timeout=45)
        if response.ok:
            data = response.json()
            st.session_state.drive_files = data.get("files", [])
            st.session_state.drive_error = None
            st.session_state.drive_loaded = True
            return data.get("files", [])
        else:
            err_msg = "Failed to list Google Drive files."
            try:
                err_msg = response.json().get("detail", err_msg)
            except Exception:
                pass
            st.session_state.drive_error = err_msg
    except Exception as err:
        LOGGER.error("Error fetching Google Drive files: %s", err)
        st.session_state.drive_error = f"Error communicating with Drive: {err}"
    return []


def import_drive_file(file_item: dict):
    file_id = file_item.get("id")
    filename = file_item.get("name")
    mime_type = file_item.get("mime_type", "")

    with st.spinner(f"Importing & indexing '{filename}' from Google Drive..."):
        try:
            payload = {
                "file_id": file_id,
                "filename": filename,
                "mime_type": mime_type,
            }
            response = requests.post(f"{BACKEND_URL}/api/drive/import", json=payload, timeout=240)
            if response.ok:
                result = response.json()
                document_id = result.get("document_id")

                if result.get("is_duplicate"):
                    st.info(f"'{filename}' is already in your workspace.")
                else:
                    st.success(f"'{filename}' imported successfully!")

                # Refresh workspace documents
                refresh_documents()

                # Activate the imported document
                for doc in st.session_state.documents:
                    if doc.get("document_id") == document_id:
                        activate_document(doc)
                        break

                load_conversations()
                if not result.get("is_duplicate"):
                    start_new_chat()

                st.session_state.documents_needs_refresh = True
                st.rerun()
            else:
                err_detail = "Import failed."
                try:
                    err_detail = response.json().get("detail", err_detail)
                except Exception:
                    err_detail = response.text or err_detail
                st.error(f"Google Drive import error: {err_detail}")
        except Exception as err:
            st.error(f"Failed to import from Google Drive: {err}")


def _render_selected_drive_file_card(file_item: dict):
    file_id = file_item.get("id")
    name = file_item.get("name", "Unnamed file")
    mime = file_item.get("mime_type", "")
    ext = Path(name).suffix.lower()
    is_supported = file_item.get("is_supported", False)
    is_imported = file_item.get("is_imported", False)
    imported_doc_id = file_item.get("imported_document_id")

    # Determine badge label
    if file_item.get("is_gdoc") or mime == "application/vnd.google-apps.document":
        badge = "📑 Google Doc → PDF"
    elif ext == ".pdf" or mime == "application/pdf":
        badge = "📄 PDF Document"
    elif ext == ".docx" or "wordprocessing" in mime:
        badge = "📝 Word Document (DOCX)"
    elif ext in (".png", ".jpg", ".jpeg", ".webp") or "image" in mime:
        badge = f"🖼️ Image ({ext.upper().lstrip('.') or 'IMAGE'})"
    else:
        badge = f"📁 Unsupported ({ext or 'file'})"

    modified = file_item.get("modified", "")
    mod_str = f" · Modified: {modified[:10]}" if modified else ""

    card_border = "#10b981" if is_imported else ("#6366f1" if is_supported else "#ef4444")
    card_bg = "rgba(16, 185, 129, 0.08)" if is_imported else ("rgba(99, 102, 241, 0.08)" if is_supported else "rgba(239, 68, 68, 0.08)")

    st.markdown(
        f"""
        <div style="
            background:{card_bg};
            border:1px solid {card_border};
            border-radius:10px;
            padding:10px 12px;
            margin-top:8px;
            margin-bottom:8px;
        ">
            <div style="font-size:12.5px;font-weight:600;color:#f1f5f9;word-break:break-word;line-height:1.4;">
                {escape_html(name)}
            </div>
            <div style="font-size:10.5px;color:#a5b4fc;margin-top:4px;">
                {escape_html(badge)}{escape_html(mod_str)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if is_imported:
        st.markdown(
            """
            <div style="font-size:11.5px;color:#86efac;margin-bottom:6px;font-weight:500;">
                ✓ In Workspace
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Use", key=f"use_drive_selected_{file_id}", use_container_width=True, type="primary"):
            for doc in st.session_state.documents:
                if doc.get("document_id") == imported_doc_id or doc.get("google_drive_file_id") == file_id:
                    activate_document(doc)
                    break
            st.session_state.drive_browser_open = False
            st.rerun()
    elif is_supported:
        if st.button("📥 Import & Process", key=f"import_drive_selected_{file_id}", use_container_width=True, type="primary"):
            import_drive_file(file_item)
    else:
        st.markdown(
            """
            <div style="font-size:11px;color:#fca5a5;margin-bottom:6px;">
                ⚠️ Unsupported format. DocuMind AI supports PDF, DOCX, Images, and Google Docs.
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.button("📥 Import & Process", key=f"import_drive_dis_{file_id}", use_container_width=True, disabled=True)


def render_google_drive_section():
    # Fetch status if not yet loaded
    if st.session_state.drive_status is None:
        fetch_drive_status()

    drive_status = st.session_state.drive_status or {}
    is_connected = drive_status.get("connected", False)
    is_authenticated = drive_status.get("authenticated", False)
    identity = drive_status.get("identity") or drive_status.get("display_name")

    if is_connected and is_authenticated:
        st.markdown(
            f"""
            <div style="
                display:flex;
                align-items:center;
                gap:7px;
                padding:6px 10px;
                background:rgba(16, 185, 129, 0.12);
                border:1px solid rgba(16, 185, 129, 0.3);
                border-radius:8px;
                margin-bottom:10px;
                font-size:11px;
                color:#6ee7b7;
            ">
                <span style="width:7px;height:7px;background:#10b981;border-radius:50%;display:inline-block;"></span>
                <span><strong>Connected:</strong> {escape_html(identity or 'Google Account')}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif is_connected and not is_authenticated:
        st.warning("Google Drive connected, but authentication token is missing or expired.")
        return
    else:
        st.error(f"Drive MCP server unavailable: {drive_status.get('message', 'Not connected')}")
        return

    # Check if the browser UI is currently open
    browser_open = st.session_state.get("drive_browser_open", False)

    if not browser_open:
        # Check if a file was previously selected
        selected_file = None
        selected_id = st.session_state.get("selected_drive_file_id")
        drive_files = st.session_state.get("drive_files", [])
        if selected_id and drive_files:
            for f in drive_files:
                if f.get("id") == selected_id:
                    selected_file = f
                    break

        if selected_file:
            _render_selected_drive_file_card(selected_file)
            if st.button("🔍 Change / Browse Google Drive", key="open_drive_browse_btn", use_container_width=True):
                st.session_state.drive_browser_open = True
                if not st.session_state.drive_loaded:
                    fetch_drive_files(st.session_state.drive_search_query)
                st.rerun()
        else:
            st.caption("Select a document from your Google Drive to import into DocuMind AI.")
            if st.button("🔍 Browse Google Drive", key="open_drive_browse_btn", use_container_width=True, type="primary"):
                st.session_state.drive_browser_open = True
                if not st.session_state.drive_loaded:
                    fetch_drive_files(st.session_state.drive_search_query)
                st.rerun()
        return

    # Browser UI is OPEN
    top_col1, top_col2 = st.columns([3, 1])
    with top_col1:
        st.markdown("<div style='font-size:12px;font-weight:600;color:#c7d2fe;padding-top:4px;'>🔍 Google Drive Explorer</div>", unsafe_allow_html=True)
    with top_col2:
        if st.button("✕ Close", key="close_drive_browse_btn", use_container_width=True):
            st.session_state.drive_browser_open = False
            st.rerun()

    # Search and refresh bar
    search_col, btn_col = st.columns([4, 1])
    with search_col:
        search_query = st.text_input(
            "Search Drive",
            value=st.session_state.drive_search_query,
            placeholder="Search by filename...",
            label_visibility="collapsed",
            key="drive_search_box",
        )
    with btn_col:
        if st.button("🔄", key="refresh_drive_btn", help="Refresh Google Drive files"):
            st.session_state.drive_search_query = search_query
            fetch_drive_files(search_query)
            st.rerun()

    if search_query != st.session_state.drive_search_query:
        st.session_state.drive_search_query = search_query
        fetch_drive_files(search_query)

    # Initial file load when opened
    if not st.session_state.drive_loaded:
        fetch_drive_files(st.session_state.drive_search_query)

    if st.session_state.drive_error:
        st.caption(f"⚠️ {st.session_state.drive_error}")

    drive_files = st.session_state.drive_files or []

    if not drive_files:
        if st.session_state.drive_loaded:
            st.caption("No files found matching your query in Google Drive.")
        return

    def _file_display_name(file_item: dict) -> str:
        name = file_item.get("name", "Unnamed file")
        mime = file_item.get("mime_type", "")
        ext = Path(name).suffix.lower()
        is_imported = file_item.get("is_imported", False)
        is_supported = file_item.get("is_supported", False)

        if file_item.get("is_gdoc") or mime == "application/vnd.google-apps.document":
            icon = "📑 [G-Doc]"
        elif ext == ".pdf" or mime == "application/pdf":
            icon = "📄 [PDF]"
        elif ext == ".docx" or "wordprocessing" in mime:
            icon = "📝 [DOCX]"
        elif ext in (".png", ".jpg", ".jpeg", ".webp") or "image" in mime:
            icon = "🖼️ [Image]"
        else:
            icon = "📁 [Other]"

        status_tag = ""
        if is_imported:
            status_tag = " · ✓ In Workspace"
        elif not is_supported:
            status_tag = " · ⚠️ Unsupported"

        return f"{icon} {name}{status_tag}"

    current_selected_id = st.session_state.get("selected_drive_file_id")
    current_index = 0
    if current_selected_id:
        for idx, f in enumerate(drive_files):
            if f.get("id") == current_selected_id:
                current_index = idx
                break

    selected_file = st.selectbox(
        "Select Google Drive file",
        options=drive_files,
        index=current_index,
        format_func=_file_display_name,
        key="drive_file_selectbox",
        label_visibility="collapsed",
    )

    if selected_file:
        st.session_state.selected_drive_file_id = selected_file.get("id")
        _render_selected_drive_file_card(selected_file)

    if st.button("✓ Done Browsing", key="done_browsing_drive_btn", use_container_width=True):
        st.session_state.drive_browser_open = False
        st.rerun()


# ============================================================================
# CONVERSATION API
# ============================================================================

def load_conversations():
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/conversations",
            timeout=30,
        )
        response.raise_for_status()
        conversations = response.json() or []
        st.session_state.conversations = conversations
        return conversations
    except requests.exceptions.RequestException:
        st.session_state.conversations = []
        return []


def create_conversation_record(title: str = "New chat"):
    document_ids = [
        item.get("document_id")
        for item in st.session_state.documents
        if isinstance(item, dict) and item.get("document_id")
    ]

    payload = {
        "title": title,
        "document_ids": document_ids,
    }

    try:
        response = requests.post(
            f"{BACKEND_URL}/api/conversations",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()

        st.session_state.conversation_id = data.get("conversation_id")
        st.session_state.conversation_title = data.get("title", title)
        st.session_state.messages = data.get("messages", [])

        clear_highlight()
        load_conversations()
        return data

    except requests.exceptions.RequestException as error:
        st.error(f"Could not create conversation: {error}")
        return None


def start_new_chat():
    active = st.session_state.get("conversation_id")
    if active:
        current = next(
            (
                conv
                for conv in st.session_state.conversations
                if conv.get("conversation_id") == active
            ),
            None,
        )
        # Reuse an existing empty chat instead of creating duplicates
        # across Streamlit reruns.
        if current and not current.get("messages"):
            st.session_state.messages = []
            st.session_state.conversation_title = (
                current.get("title") or "New chat"
            )
            clear_highlight()
            return

    create_conversation_record(title="New chat")
    clear_highlight()


def open_conversation(conversation_id: str):
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/conversations/{conversation_id}",
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()

        st.session_state.conversation_id = conversation_id
        st.session_state.conversation_title = data.get("title", "New chat")
        st.session_state.messages = data.get("messages", [])
        clear_highlight()

        document_ids = data.get("document_ids") or []

        if document_ids:
            selected_id = document_ids[0]
            selected_document = next(
                (
                    item
                    for item in st.session_state.documents
                    if item.get("document_id") == selected_id
                ),
                None,
            )

            if selected_document:
                activate_document(selected_document)

        return data

    except requests.exceptions.RequestException as error:
        st.error(f"Could not open conversation: {error}")
        return None


def save_current_conversation():
    conversation_id = st.session_state.get("conversation_id")

    if not conversation_id:
        return None

    document_ids = [
        item.get("document_id")
        for item in st.session_state.documents
        if isinstance(item, dict) and item.get("document_id")
    ]

    if (
        st.session_state.document_id
        and st.session_state.document_id not in document_ids
    ):
        document_ids.insert(0, st.session_state.document_id)

    payload = {
        "title": st.session_state.get("conversation_title", "New chat"),
        "messages": st.session_state.get("messages", []),
        "document_ids": document_ids,
    }

    try:
        response = requests.patch(
            f"{BACKEND_URL}/api/conversations/{conversation_id}",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        load_conversations()
        return response.json()

    except requests.exceptions.RequestException:
        return None


def delete_conversation(conversation_id: str):
    try:
        response = requests.delete(
            f"{BACKEND_URL}/api/conversations/{conversation_id}",
            timeout=30,
        )
        response.raise_for_status()

        input_key = f"rename_input_{conversation_id}"
        if input_key in st.session_state:
            del st.session_state[input_key]

        if st.session_state.conversation_id == conversation_id:
            st.session_state.conversation_id = None
            st.session_state.conversation_title = "New chat"
            st.session_state.messages = []
            clear_highlight()

        load_conversations()
        st.rerun()

    except requests.exceptions.RequestException as error:
        st.error(f"Conversation delete failed: {error}")


def rename_conversation(conversation_id: str, title: str):
    try:
        response = requests.patch(
            f"{BACKEND_URL}/api/conversations/{conversation_id}",
            json={"title": title},
            timeout=30,
        )
        response.raise_for_status()

        input_key = f"rename_input_{conversation_id}"
        if input_key in st.session_state:
            del st.session_state[input_key]

        if st.session_state.conversation_id == conversation_id:
            st.session_state.conversation_title = title

        load_conversations()
        st.rerun()

    except requests.exceptions.RequestException as error:
        st.error(f"Rename failed: {error}")


# ============================================================================
# PDF SECTION HIGHLIGHTING (BLOCK BASED)
# ============================================================================

SECTION_PADDING = 4.0
MIN_ANCHOR_WORDS = 4
MAX_SECTION_BLOCKS = 8
CONFIDENCE_MIN = 0.30
HEADING_LINK_GAP = 45.0
PARAGRAPH_CONTINUATION_GAP = 22.0
PARAGRAPH_REL_GAP = 1.3

_MAJOR_HEADING_RE = re.compile(r"^\d+(\.\d+)*[.`:]\s+\S")
_CHILD_HEADING_RE = re.compile(r"^\d+\.\d+[.`:]*\s+\S")
_QUESTION_HEADING_RE = re.compile(
    r"^(?:q[-.\s]?\d+|question)\b", re.IGNORECASE
)
_CODE_FONT_RE = re.compile(
    r"(?i)(mono|courier|consolas|code|fira|menlo|inconsolata|"
    r"sourcecode|jetbrains|dejavu)"
)

_BULLET_CHARS = "\u25cf\u2022\uf0b7\ufffd\u2219\u25e6\u2023\u2043\u00b7•·►▪*"
_PUNCT_TO_STRIP = ".,;:!?()[]{}<>|\\/\"'`“”‘’…"


def normalize_block_text(text: str) -> str:
    """
    Normalizes a block or the source passage for reliable matching:

    - Collapses line breaks and runs of spaces into single spaces.
    - Removes soft-hyphens and normalizes dash variants.
    - Treats hyphens as space-separated so "multi-agent" and
      "multi-\nagent" (broken across a PDF line) both normalize
      to the same token sequence.
    - Strips bullet markers and punctuation attached to word
      edges (so "step," and "step" both become "step").
    """
    if not text:
        return ""

    value = str(text)
    value = value.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    value = value.replace("\u00ad", "")
    value = value.replace("\u2010", " ")
    value = value.replace("\u2013", " ")
    value = value.replace("\u2014", " ")
    for marker in _BULLET_CHARS:
        value = value.replace(marker, " ")
    value = value.replace("-", " ")
    value = " ".join(value.split())
    value = " ".join(
        token.strip(_PUNCT_TO_STRIP)
        for token in value.split()
        if token.strip(_PUNCT_TO_STRIP)
    )
    value = value.strip(_PUNCT_TO_STRIP)
    return value.lower()


def _is_title_case_line(text: str) -> bool:
    """
    True for short Title Case / ALL CAPS heading lines such as
    "Memory Management in OS" or "MEMORY MANAGEMENT".
    Sentence-fragment continuation lines ("Edges define which node
    executes next") are rejected because only their first word is
    capitalized.
    """
    compact = " ".join(str(text or "").split())
    words = compact.split()
    if not (1 <= len(words) <= 10):
        return False
    alpha = [w for w in words if any(c.isalpha() for c in w)]
    if not alpha:
        return False
    capitalized = sum(1 for w in alpha if w[0] and w[0].isupper())
    if capitalized / len(alpha) < 0.5:
        return False
    if compact[0] and not compact[0].isupper():
        return False
    return len(compact) <= 70


def is_child_heading(text: str) -> bool:
    """
    True for numbered sub-section headings such as "10.1 Installation",
    "10.2 Minimal Graph" or "11.1 Sequential Research and Review
    Workflow".
    """
    compact = " ".join(str(text or "").split())
    if not compact:
        return False
    return bool(_CHILD_HEADING_RE.match(compact))


def is_heading(text: str) -> bool:
    """
    True when the block text is a section heading:
    - numbered major headings ("10. LangGraph Fundamentals")
    - numbered child headings ("10.1 Installation")
    - question headings ("Q1 ...", "Question 2 ...")
    - short colon lead-ins ("The functions are:")
    - Title Case / ALL CAPS heading lines

    Bullet points and mid-sentence continuation lines are deliberately
    rejected.
    """
    compact = " ".join(str(text or "").split())
    if not compact:
        return False
    if is_child_heading(compact):
        return True
    if compact[0] in _BULLET_CHARS:
        return False
    if _MAJOR_HEADING_RE.match(compact):
        return True
    if _QUESTION_HEADING_RE.match(compact):
        return True
    if 2 <= len(compact) <= 90 and compact.endswith(":"):
        return True
    return _is_title_case_line(compact)


def _is_code_block(raw_text: str) -> bool:
    """
    Textual heuristics used to detect code blocks when the font
    information is inconclusive.
    """
    text = str(raw_text or "")
    if re.search(
        r"(?m)^\s*(def|class|import|from|return|print|"
        r"if __name__|public (static )?|private |const |let |var |"
        r"function |async |await )\b",
        text,
    ):
        return True
    if re.search(r"(?m)^\s*(>>>|\.\.\.)\s", text):
        return True
    stripped = "\n".join(
        line.strip() for line in text.splitlines() if line.strip()
    )
    if ";" in stripped and "{" in stripped:
        return True
    return False


def _extract_text_blocks(page) -> list[dict]:
    """
    Returns a list of text blocks from the page, sorted top-to-bottom,
    left-to-right, each with 'rect', 'raw', 'norm' and 'is_code' keys.

    Uses ``page.get_text("dict")`` so code blocks can be detected from
    monospace fonts in addition to text heuristics.
    """
    try:
        page_dict = page.get_text("dict")
    except Exception:
        return []

    blocks = []
    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        lines = block.get("lines") or []
        raw_lines = []
        x0 = y0 = float("inf")
        x1 = y1 = float("-inf")
        code_chars = 0
        total_chars = 0

        for line in lines:
            parts = []
            for span in line.get("spans") or []:
                span_text = span.get("text") or ""
                if not span_text:
                    continue
                parts.append(span_text)
                total_chars += len(span_text)
                if _CODE_FONT_RE.search(span.get("font") or ""):
                    code_chars += len(span_text)
                bbox = span.get("bbox")
                if bbox and len(bbox) >= 4:
                    x0 = min(x0, bbox[0])
                    y0 = min(y0, bbox[1])
                    x1 = max(x1, bbox[2])
                    y1 = max(y1, bbox[3])
            if parts:
                raw_lines.append("".join(parts))

        raw = "\n".join(raw_lines).strip()
        if not raw or total_chars == 0 or x0 > x1:
            continue

        norm = normalize_block_text(raw)
        if not norm:
            continue

        is_code = (code_chars / total_chars) >= 0.6 or _is_code_block(raw)

        blocks.append({
            "rect": fitz.Rect(x0, y0, x1, y1),
            "raw": raw,
            "norm": norm,
            "is_code": is_code,
        })

    blocks.sort(
        key=lambda blk: (round(blk["rect"].y0, 1),
                         round(blk["rect"].x0, 1))
    )
    return blocks


def _overlap_words(source_words: list[str],
                   block_words: list[str]) -> int:
    """
    Number of source words that also occur in the block text
    (bag overlap, order-independent).
    """
    remaining = _word_counts(source_words)
    before = _remaining_count(remaining)
    _consume_words(remaining, " ".join(block_words))
    return before - _remaining_count(remaining)


def _word_counts(words: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for word in words:
        counts[word] = counts.get(word, 0) + 1
    return counts


def _consume_words(remaining: dict[str, int],
                   block_norm: str) -> None:
    for word in block_norm.split():
        if remaining.get(word, 0) > 0:
            remaining[word] -= 1


def _remaining_count(remaining: dict[str, int]) -> int:
    return sum(remaining.values())


def _padded_rect(rect: fitz.Rect, pad: float) -> fitz.Rect:
    return fitz.Rect(rect.x0 - pad, rect.y0 - pad,
                     rect.x1 + pad, rect.y1 + pad)


def find_best_matching_block(page, source_text):
    """
    Finds the block with the highest text overlap against the
    normalized source_text and estimates a confidence score.

    Returns (blocks, matched_index, confidence).  matched_index is -1
    when no reliable match exists.
    """
    blocks = _extract_text_blocks(page)
    source_norm = normalize_block_text(source_text)
    source_words = source_norm.split() if source_norm else []

    if not source_words:
        return blocks, -1, 0.0

    best_index = -1
    best_score = -1.0
    best_overlap = 0
    best_block_ratio = 0.0
    best_source_ratio = 0.0

    for index, block in enumerate(blocks):
        block_words = block["norm"].split()
        if not block_words:
            continue
        overlap = _overlap_words(source_words, block_words)
        if overlap <= 0:
            continue

        block_ratio = overlap / len(block_words)
        source_ratio = overlap / len(source_words)
        score = (0.7 * block_ratio) + (0.3 * source_ratio)

        if score > best_score or (score == best_score
                                  and overlap > best_overlap):
            best_index = index
            best_score = score
            best_overlap = overlap
            best_block_ratio = block_ratio
            best_source_ratio = source_ratio

    if best_index < 0:
        return blocks, -1, 0.0

    confidence = best_block_ratio
    matched_is_heading = is_heading(blocks[best_index]["raw"])

    if matched_is_heading:
        reliable = best_overlap >= 2 and best_block_ratio >= 0.5
    else:
        reliable = (best_overlap >= MIN_ANCHOR_WORDS
                    and (best_block_ratio >= 0.35 or best_source_ratio >= 0.20))

    if not reliable:
        return blocks, -1, confidence

    return blocks, best_index, confidence


def get_related_heading(blocks, matched_index):
    """
    Returns the index of the heading block immediately above the
    matched paragraph, or None when there is no directly connected
    heading.

    Only the single previous block is considered: a parent section
    heading is NOT included when a child heading sits in between.
    """
    if matched_index is None or matched_index <= 0:
        return None

    previous = blocks[matched_index - 1]
    if previous.get("is_code"):
        return None
    if not is_heading(previous["raw"]):
        return None

    gap = blocks[matched_index]["rect"].y0 - previous["rect"].y1
    if gap < -2 or gap > HEADING_LINK_GAP:
        return None
    return matched_index - 1


def find_source_rectangles(page,
                           source_text: str) -> list[fitz.Rect]:
    """
    Finds exact line-level or sentence-level highlight rectangles on the page.
    1. First tries exact sentence / phrase searches using PyMuPDF page.search_for()
       with sliding-window matching for long or multi-line citations.
    2. Falls back to block-level overlap matching if text extraction variations
       prevent exact match.
    Never highlights the entire page or unrelated sections.
    """
    LOGGER.debug("find_source_rectangles start")
    if not source_text or page is None:
        return []

    rects: list[fitz.Rect] = []

    # 1. Exact sentence/phrase search via page.search_for()
    cleaned_source = source_text.strip()
    if len(cleaned_source) < 120:
        clean_full = " ".join(cleaned_source.split())
        r_list = page.search_for(clean_full)
        if r_list:
            rects.extend(r_list)

    if not rects:
        # Split into sentences or clauses
        raw_chunks = re.split(r'(?<=[.!?])\s+|\n+', cleaned_source)
        candidate_phrases = []
        for s in raw_chunks:
            c = " ".join(s.split()).strip()
            # Strip leading bullet symbols or list numerals
            c = re.sub(r'^[•\-\*\u25cf\uf0b7\ufffd\u2219\u25e6\u2023\u2043\u00b7·►▪\d+\.\s]+', '', c).strip()
            if len(c) >= 10:
                candidate_phrases.append(c)

        for phrase in candidate_phrases:
            # Try full phrase first
            r_list = page.search_for(phrase)
            if r_list:
                rects.extend(r_list)
            else:
                # Sliding window of 5-8 words if phrase is broken across lines or formatted
                words = phrase.split()
                if len(words) >= 5:
                    step = 4
                    window_size = 6
                    for i in range(0, len(words) - 3, step):
                        sub = " ".join(words[i : i + window_size])
                        if len(sub) >= 12:
                            sub_r = page.search_for(sub)
                            if sub_r:
                                rects.extend(sub_r)

    if rects:
        # Deduplicate and slightly pad line rectangles
        unique_rects: list[fitz.Rect] = []
        for r in rects:
            padded = fitz.Rect(r.x0 - 2.0, r.y0 - 1.5, r.x1 + 2.0, r.y1 + 1.5)
            duplicate = False
            for ex in unique_rects:
                if abs(ex.y0 - padded.y0) < 3.0 and abs(ex.y1 - padded.y1) < 3.0:
                    if ex.x0 <= padded.x0 + 2.0 and ex.x1 >= padded.x1 - 2.0:
                        duplicate = True
                        break
                    elif padded.x0 <= ex.x0 + 2.0 and padded.x1 >= ex.x1 - 2.0:
                        ex.x0 = min(ex.x0, padded.x0)
                        ex.x1 = max(ex.x1, padded.x1)
                        duplicate = True
                        break
            if not duplicate:
                unique_rects.append(padded)

        LOGGER.debug("find_source_rectangles: found %d exact/phrase rects", len(unique_rects))
        return unique_rects

    # 2. Fallback: block-level matching
    blocks, matched_index, confidence = find_best_matching_block(
        page, source_text
    )

    if matched_index < 0:
        LOGGER.debug("no reliable matching block "
                     "(confidence_score=%.2f)", confidence)
        LOGGER.debug("selected_block_indices: []")
        LOGGER.debug("selected_rectangle_count: 0")
        return []

    matched = blocks[matched_index]
    selected = [matched_index]

    LOGGER.debug("matched_block_index: %d", matched_index)
    LOGGER.debug("matched_block_text: %r", matched["raw"].strip())
    LOGGER.debug("confidence_score: %.2f", confidence)

    if is_heading(matched["raw"]):
        # Rule: heading + the directly following paragraph only.
        LOGGER.debug("matched block is a heading; adding the "
                     "directly following paragraph")
        if matched_index + 1 < len(blocks):
            following = blocks[matched_index + 1]
            gap = following["rect"].y0 - matched["rect"].y1
            if (not is_heading(following["raw"])
                    and not following.get("is_code")
                    and -2 <= gap <= HEADING_LINK_GAP):
                selected.append(matched_index + 1)
        LOGGER.debug("matched_heading: %r", matched["raw"].strip())
    else:
        related_heading = get_related_heading(blocks, matched_index)
        if related_heading is not None:
            selected.append(related_heading)
            LOGGER.debug("matched_heading: %r",
                         blocks[related_heading]["raw"].strip())
        else:
            LOGGER.debug("matched_heading: None")

        # Directly connected continuation blocks that belong to the same
        # paragraph and still contain source words.
        source_norm = normalize_block_text(source_text)
        remaining = _word_counts(source_norm.split())
        _consume_words(remaining, matched["norm"])
        previous_rect = matched["rect"]

        for index in range(matched_index + 1, len(blocks)):
            if len(selected) >= MAX_SECTION_BLOCKS:
                break
            candidate = blocks[index]
            if is_heading(candidate["raw"]) or candidate.get("is_code"):
                LOGGER.debug("paragraph ends before block %d "
                             "(heading or code)", index)
                break
            if (candidate["raw"].lstrip()
                    and candidate["raw"].lstrip()[0] in _BULLET_CHARS):
                LOGGER.debug("paragraph ends before block %d "
                             "(new bullet point)", index)
                break
            gap = candidate["rect"].y0 - previous_rect.y1
            height = previous_rect.y1 - previous_rect.y0
            max_gap = max(PARAGRAPH_CONTINUATION_GAP,
                          PARAGRAPH_REL_GAP * max(height, 8.0))
            if gap < -2 or gap > max_gap:
                LOGGER.debug("paragraph ends before block %d "
                             "(unrelated block)", index)
                break
            before = _remaining_count(remaining)
            _consume_words(remaining, candidate["norm"])
            added = before - _remaining_count(remaining)
            if added <= 0:
                LOGGER.debug("paragraph ends before block %d "
                             "(no source words added)", index)
                break
            selected.append(index)
            previous_rect = candidate["rect"]

    selected.sort()

    rectangles = [_padded_rect(blocks[index]["rect"], SECTION_PADDING)
                  for index in selected]

    LOGGER.debug("selected_block_indices: %s", selected)
    LOGGER.debug("selected_rectangle_count: %d", len(rectangles))
    LOGGER.debug("find_source_rectangles done")

    return rectangles


# ============================================================================
# PDF RENDERING
# ============================================================================

def render_pdf_page(
    pdf_bytes: bytes,
    page_number: int,
    highlight_text: str = "",
):
    """
    Renders a PDF page as PNG and applies the highlight when a reliable
    match is found.  Returns (image_bytes, highlight_applied).
    """
    if not pdf_bytes:
        return None, False

    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")

    try:
        total_pages = len(pdf_document)

        if total_pages == 0:
            return None, False

        page_number = max(
            1,
            min(page_number, total_pages),
        )

        page = pdf_document[page_number - 1]

        highlight_applied = False

        if highlight_text:
            rectangles = find_source_rectangles(page, highlight_text)

            for rectangle in rectangles:
                page.draw_rect(
                    rectangle,
                    color=(0.92, 0.70, 0.0),
                    fill=(1.0, 0.90, 0.20),
                    width=1.0,
                    fill_opacity=0.42,
                    overlay=True,
                )

            highlight_applied = bool(rectangles)

        matrix = fitz.Matrix(1.45, 1.45)
        pixmap = page.get_pixmap(
            matrix=matrix,
            alpha=False,
        )

        return pixmap.tobytes("png"), highlight_applied

    finally:
        pdf_document.close()


# ============================================================================
# SOURCES
# ============================================================================

def open_source(source: dict, source_key: str):
    # Clear the previous highlight first.
    clear_highlight()

    # If this source belongs to another document in workspace, switch to it:
    target_doc_id = source.get("document_id")
    if target_doc_id and target_doc_id != st.session_state.get("document_id"):
        for doc in st.session_state.get("documents", []):
            if doc.get("document_id") == target_doc_id:
                activate_document(doc)
                break

    page = source.get("page")
    if page is None:
        page = source.get("page_number")

    if page is not None:
        try:
            page = int(page)
        except (TypeError, ValueError):
            page = None

    if page is not None:
        st.session_state.pending_page = page

    exact = (
        source.get("exact_text")
        or source.get("text")
        or source.get("preview")
        or ""
    )

    if exact:
        st.session_state.highlight_text = exact
        st.session_state.active_source_key = source_key

    # Save image OCR source highlights
    st.session_state.selected_source_bbox = source.get("bbox")
    st.session_state.selected_source_bboxes = source.get("bboxes", [])
    st.session_state.selected_source_dimensions = (
        source.get("image_width"),
        source.get("image_height"),
    )
    st.session_state.selected_source_confidence = source.get("confidence")
    st.session_state.selected_source_match_type = source.get("match_type")
    if source.get("all_ocr_bboxes"):
        st.session_state.all_ocr_bboxes = source.get("all_ocr_bboxes", [])


def render_sources(sources, message_id):
    if not sources:
        return

    st.markdown(
        f"""
        <div class="sources-container-header">
            <span class="sources-title">📌 Sources & Citations</span>
            <span class="sources-count">{len(sources)} reference{'s' if len(sources) != 1 else ''}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for source_index, source in enumerate(sources):
        page_number = source.get("page")
        if page_number is None:
            page_number = source.get("page_number")

        file_type = str(source.get("file_type", "")).lower()
        title = source.get("title")

        if file_type in ("png", "jpg", "jpeg", "webp"):
            btn_label = f"🔍 View Image Source · {source.get('filename') or 'Image'}"
            btn_help = "Highlight the exact source text region in the image"
            page_badge_text = "Image Source"
        elif file_type == "docx":
            btn_label = f"📖 Open source · {title or 'Section'}"
            btn_help = "Inspect source section text"
            page_badge_text = title or "DOCX Section"
        else:
            p_label = f"Page {page_number}" if page_number is not None else (title or "Source")
            btn_label = f"📖 Open source · {p_label}"
            btn_help = "Navigate to this page and highlight the exact source text"
            page_badge_text = f"Page {page_number}" if page_number is not None else "Document Source"

        source_key = f"source_{message_id}_{source_index}"
        is_active = (
            st.session_state.get("active_source_key") == source_key
        )

        button_type = "primary" if is_active else "secondary"

        active_card_cls = " active-source-card" if is_active else ""
        active_chip_html = '<span class="source-active-pill">● VIEWING</span>' if is_active else ''

        st.markdown(
            f"""
            <div class="source-card-wrap{active_card_cls}">
                <div class="source-card-header">
                    <span class="source-badge-pill">📍 {escape_html(page_badge_text)}</span>
                    {active_chip_html}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button(
            btn_label,
            key=f"open_{source_key}",
            use_container_width=True,
            type=button_type,
            help=btn_help,
        ):
            open_source(source, source_key)
            st.rerun()

        preview = (
            source.get("preview")
            or source.get("exact_text")
            or source.get("text")
            or ""
        )

        if preview:
            st.markdown(
                f'<div class="source-preview">{escape_html(preview)}</div>',
                unsafe_allow_html=True,
            )


# ============================================================================
# UPLOAD DOCUMENTS
# ============================================================================

def upload_documents(uploaded_files):
    files_to_upload = []

    for uploaded_file in uploaded_files:
        fingerprint = compute_file_fingerprint(uploaded_file)

        if fingerprint not in st.session_state.processed_file_fingerprints:
            files_to_upload.append(uploaded_file)

    if not files_to_upload:
        st.info("These files are already uploaded.")
        return

    st.session_state.upload_statuses = [
        {
            "name": uploaded_file.name,
            "status": "Pending",
        }
        for uploaded_file in files_to_upload
    ]

    uploaded_document_ids = []

    with st.spinner("Processing your documents..."):
        for uploaded_file in files_to_upload:
            try:
                response = requests.post(
                    f"{BACKEND_URL}/api/upload",
                    files={
                        "files": (
                            uploaded_file.name,
                            uploaded_file.getvalue(),
                            uploaded_file.type,
                        )
                    },
                    timeout=240,
                )

                if response.status_code == 409:
                    status = "Already uploaded"
                    document_ids = []

                else:
                    response.raise_for_status()
                    data = response.json()
                    document_ids = []

                    if isinstance(data, dict) and "documents" in data:
                        for item in data["documents"]:
                            document_id = item.get("document_id")
                            if document_id:
                                document_ids.append(document_id)

                    elif isinstance(data, dict):
                        document_id = data.get("document_id")
                        if document_id:
                            document_ids.append(document_id)

                    status = "Uploaded"

                uploaded_document_ids.extend(document_ids)

                fingerprint = compute_file_fingerprint(uploaded_file)
                st.session_state.processed_file_fingerprints.add(fingerprint)

                for item in st.session_state.upload_statuses:
                    if item["name"] == uploaded_file.name:
                        item["status"] = status

            except requests.exceptions.RequestException as error:
                detail_msg = ""
                if getattr(error, "response", None) is not None:
                    try:
                        detail_msg = error.response.json().get("detail", "")
                    except Exception:
                        detail_msg = getattr(error.response, "text", "")
                error_display = detail_msg or str(error)

                for item in st.session_state.upload_statuses:
                    if item["name"] == uploaded_file.name:
                        item["status"] = "Failed"

                st.error(
                    f"Upload failed for {uploaded_file.name}: {error_display}"
                )


    if uploaded_document_ids:
        st.session_state.document_id = uploaded_document_ids[-1]
        st.session_state.filename = files_to_upload[-1].name
        st.session_state.messages = []
        reset_document_viewer()
        st.session_state.documents_needs_refresh = True

    refresh_documents()
    load_conversations()

    if uploaded_document_ids:
        start_new_chat()

    st.success("Document processing completed.")
    st.rerun()


# ============================================================================
# LOAD DATA ON STARTUP
# ============================================================================

if st.session_state.documents_needs_refresh:
    refresh_documents()

load_conversations()


# ============================================================================
# WORKSPACE HEADER
# ============================================================================

def render_workspace_header():
    """Render the workspace header using native Streamlit primitives.

    The previous version used one large custom HTML fragment. Keeping the header
    native avoids HTML leakage in Streamlit markdown while preserving the same
    document/source/status information.
    """
    active_filename = st.session_state.get("filename")
    active_doc = next(
        (
            doc for doc in st.session_state.documents
            if doc.get("document_id") == st.session_state.document_id
        ),
        None,
    ) if st.session_state.get("document_id") else None

    is_drive = bool(
        active_doc
        and (
            active_doc.get("source_type") == "google_drive"
            or active_doc.get("google_drive_file_id")
        )
    )
    file_type = str((active_doc or {}).get("file_type", "PDF")).upper()
    page_count = st.session_state.get("total_pages") or 0
    doc_count = len(st.session_state.get("documents", []))

    drive_status = st.session_state.get("drive_status") or {}
    drive_connected = bool(
        drive_status.get("connected") and drive_status.get("authenticated")
    )

    st.markdown('<div class="workspace-native-header">', unsafe_allow_html=True)
    left, center, right = st.columns([1.0, 2.3, 1.0], gap="medium", vertical_alignment="center")

    with left:
        st.markdown(
            '<div class="workspace-native-label">Workspace</div>'
            '<div class="workspace-native-name">📘 DocuMind AI</div>'
            '<div class="workspace-native-meta">AI document intelligence</div>',
            unsafe_allow_html=True,
        )

    with center:
        if active_filename:
            source_class = "drive" if is_drive else "local"
            source_label = "☁ Google Drive" if is_drive else "● Local File"
            meta = f"{page_count} pages" if page_count else file_type
            safe_name = escape_html(truncate_display(active_filename, 48))
            st.markdown(
                f'<div class="workspace-native-label">Active document</div>'
                f'<div class="workspace-native-name">{safe_name}</div>'
                f'<div class="workspace-native-meta">'
                f'<span class="workspace-native-chip {source_class}">{source_label}</span>'
                f' &nbsp; {escape_html(meta)}'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="workspace-native-label">Active document</div>'
                '<div class="workspace-native-name">No document selected</div>'
                '<div class="workspace-native-meta">Upload a file or import one from Google Drive</div>',
                unsafe_allow_html=True,
            )

    with right:
        status_class = "ready" if drive_connected else "ready"
        status_label = "Drive Connected" if drive_connected else "Ready"
        st.markdown(
            f'<div style="text-align:right">'
            f'<span class="workspace-native-chip {status_class}"><span class="dot"></span>{status_label}</span>'
            f'<div class="workspace-native-meta">{doc_count} document{"s" if doc_count != 1 else ""} in workspace</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown('</div>', unsafe_allow_html=True)


render_workspace_header()


# ============================================================================
# SIDEBAR
# ============================================================================

with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand-wrapper">
            <div class="sidebar-logo">📘</div>
            <div>
                <div class="sidebar-brand-title">DocuMind AI</div>
                <div class="sidebar-brand-desc">AI-powered document workspace</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button(
        "＋ New Chat",
        key="new_chat_sidebar_btn",
        use_container_width=True,
        type="primary",
    ):
        start_new_chat()
        st.rerun()

    st.markdown(
        '<div class="sidebar-section-header"><span>CHATS</span></div>',
        unsafe_allow_html=True,
    )

    if st.session_state.conversations:
        with (st.container(height=240) if len(st.session_state.conversations) > 4 else st.container()):
            for conversation in st.session_state.conversations:
                conversation_id = conversation.get("conversation_id")

                if not conversation_id:
                    continue

                title = conversation.get("title") or "New chat"
                display_title = truncate_display(title, 26)
                is_active = (
                    conversation_id == st.session_state.conversation_id
                )

                chat_col, menu_col = st.columns([4.2, 1.2])

                with chat_col:
                    chat_btn_label = f"💬 {display_title}"
                    if st.button(
                        chat_btn_label,
                        key=f"chat_{conversation_id}",
                        use_container_width=True,
                        type="primary" if is_active else "secondary",
                        help=title,
                    ):
                        open_conversation(conversation_id)
                        clear_highlight()
                        st.rerun()

                with menu_col:
                    with st.popover("⋯"):
                        st.caption("Chat options")

                        new_title = st.text_input(
                            "Rename chat",
                            key=f"rename_input_{conversation_id}",
                            value=title,
                        )

                        if st.button(
                            "Rename",
                            key=f"rename_button_{conversation_id}",
                            use_container_width=True,
                        ):
                            if new_title.strip():
                                rename_conversation(
                                    conversation_id,
                                    new_title.strip(),
                                )

                        if st.button(
                            "Delete chat",
                            key=f"delete_button_{conversation_id}",
                            use_container_width=True,
                        ):
                            delete_conversation(conversation_id)
    else:
        st.caption("No conversations yet. Start a new chat.")

    st.markdown(
        '<div class="sidebar-section-header"><span>DOCUMENTS</span></div>',
        unsafe_allow_html=True,
    )

    if st.session_state.documents:
        with (st.container(height=240) if len(st.session_state.documents) > 2 else st.container()):
            for document in st.session_state.documents:
                document_id = document.get("document_id")

                if not document_id:
                    continue

                filename = document.get("filename", "Document")
                is_active = document_id == st.session_state.document_id
                card_class = "sidebar-doc-card active" if is_active else "sidebar-doc-card"

                file_type = str(document.get("file_type", "file")).lower()
                is_drive = document.get("source_type") == "google_drive" or bool(document.get("google_drive_file_id"))

                if is_drive:
                    source_label = "Google Drive"
                else:
                    source_label = "Local"

                if file_type in ("png", "jpg", "jpeg", "webp"):
                    doc_glyph = "🖼️"
                    meta_label = f"{file_type.upper()} · {source_label}"
                elif file_type == "docx":
                    doc_glyph = "📝"
                    meta_label = f"DOCX · {source_label}"
                else:
                    doc_glyph = "📄"
                    total_p = document.get('total_pages', 0)
                    meta_label = f"PDF · {total_p}p · {source_label}"

                active_pill = '<span class="doc-active-pill">SELECTED</span>' if is_active else ''

                st.markdown(
                    f"""
                    <div class="{card_class}">
                        <div class="sidebar-doc-top">
                            <span class="sidebar-doc-glyph">{doc_glyph}</span>
                            <div class="sidebar-doc-info">
                                <div class="sidebar-doc-name" title="{escape_html(filename)}">{escape_html(truncate_display(filename, 28))}</div>
                                <div class="sidebar-doc-meta">{escape_html(meta_label)}</div>
                            </div>
                            {active_pill}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                doc_col1, doc_col2 = st.columns([1, 1])

                with doc_col1:
                    if not is_active:
                        if st.button(
                            "Select",
                            key=f"use_document_{document_id}",
                            use_container_width=True,
                        ):
                            activate_document(document)
                            st.rerun()
                    else:
                        st.button(
                            "Active",
                            key=f"active_doc_btn_{document_id}",
                            use_container_width=True,
                            disabled=True,
                        )

                with doc_col2:
                    if st.button(
                        "Remove",
                        key=f"remove_document_{document_id}",
                        use_container_width=True,
                    ):
                        delete_document(document_id)

        if st.button(
            "Clear all documents",
            key="clear_all_documents_btn",
            use_container_width=True,
        ):
            clear_all_documents()
    else:
        st.caption("No documents in workspace yet.")

    st.markdown(
        '<div class="sidebar-section-header"><span>ADD DOCUMENT</span></div>',
        unsafe_allow_html=True,
    )

    tab_local, tab_drive = st.tabs(["📁 Local Files", "☁️ Google Drive"])

    with tab_local:
        upload_key = f"file_uploader_{st.session_state.upload_key}"

        uploaded_files = st.file_uploader(
            "Choose files",
            type=["pdf", "docx", "png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            key=upload_key,
            help="Supported: PDF, DOCX, PNG, JPG, WEBP",
            label_visibility="collapsed",
        )

        if uploaded_files:
            if st.button(
                "Upload and process",
                key="upload_local_btn",
                use_container_width=True,
                type="primary",
            ):
                upload_documents(uploaded_files)

    with tab_drive:
        render_google_drive_section()

    if st.session_state.upload_statuses:
        st.markdown(
            '<div class="sidebar-section-header"><span>UPLOAD STATUS</span></div>',
            unsafe_allow_html=True,
        )

        for item in st.session_state.upload_statuses:
            status = item.get("status", "Pending")

            status_color = {
                "Uploaded": "#10b981",
                "Already uploaded": "#f59e0b",
                "Failed": "#ef4444",
                "Pending": "#94a3b8",
            }.get(status, "#94a3b8")

            st.markdown(
                f"""
                <div style="
                    padding:7px 10px;
                    border-left:3px solid {status_color};
                    border-radius:6px;
                    background:rgba(15,23,42,0.65);
                    margin-bottom:6px;
                    font-size:11px;
                ">
                    <div style="font-weight:600;color:#f1f5f9;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                        {escape_html(item.get("name", "Unknown file"))}
                    </div>
                    <div style="color:{status_color};font-size:10px;font-weight:700;margin-top:2px;">
                        {escape_html(status)}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if st.session_state.document_id:
        st.markdown(
            '<div class="sidebar-section-header"><span>WORKSPACE STATS</span></div>',
            unsafe_allow_html=True,
        )

        metric_col1, metric_col2 = st.columns(2)

        with metric_col1:
            st.markdown(
                f"""
                <div style="background:#0f172f;border:1px solid #1e2b4d;border-radius:8px;padding:8px 10px;text-align:center;">
                    <div style="color:#64748b;font-size:10px;text-transform:uppercase;font-weight:700;">Pages</div>
                    <div style="color:#f8fafc;font-size:18px;font-weight:800;margin-top:2px;">{st.session_state.total_pages or "—"}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with metric_col2:
            st.markdown(
                f"""
                <div style="background:#0f172f;border:1px solid #1e2b4d;border-radius:8px;padding:8px 10px;text-align:center;">
                    <div style="color:#64748b;font-size:10px;text-transform:uppercase;font-weight:700;">Chunks</div>
                    <div style="color:#f8fafc;font-size:18px;font-weight:800;margin-top:2px;">{st.session_state.total_chunks or "—"}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.write("")
        c_clear, c_reset = st.columns([1, 1])
        with c_clear:
            if st.button("Clear chat", key="clear_chat_sidebar_btn", use_container_width=True):
                st.session_state.messages = []
                clear_highlight()
                st.session_state.pending_page = None
                save_current_conversation()
                st.rerun()
        with c_reset:
            if st.button("Reset All", key="reset_workspace_btn", use_container_width=True):
                st.session_state.document_id = None
                st.session_state.filename = None
                st.session_state.documents = []
                st.session_state.upload_key += 1
                st.session_state.upload_statuses = []
                st.session_state.processed_file_fingerprints = set()
                reset_document_viewer()
                st.session_state.documents_needs_refresh = True
                st.rerun()

    st.markdown(
        """
        <div style="margin-top:20px;padding-top:12px;border-top:1px solid rgba(255,255,255,0.06);font-size:10.5px;color:#475569;text-align:center;">
            DocuMind AI · Enterprise Document Workspace
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================================
# MAIN LAYOUT
# ============================================================================

left_column, right_column = st.columns(
    [1.0, 1.0],
    gap="medium",
)


# ============================================================================
# DOCUMENT VIEWER
# ============================================================================

with left_column:
    is_drive = False
    if st.session_state.document_id:
        for doc in st.session_state.documents:
            if doc.get("document_id") == st.session_state.document_id:
                is_drive = doc.get("source_type") == "google_drive" or bool(doc.get("google_drive_file_id"))
                break

    if st.session_state.filename:
        source_badge_text = "☁ Google Drive" if is_drive else "● Local"
        source_badge_cls = "badge-drive" if is_drive else "badge-local"
        pages_badge = f'<span class="panel-badge badge-pages">{st.session_state.total_pages} pages</span>' if st.session_state.total_pages else ''
        st.markdown(
            f"""
            <div class="panel-header-wrap">
                <div>
                    <div class="panel-kicker">DOCUMENT VIEWER</div>
                    <div class="panel-heading">{escape_html(truncate_display(st.session_state.filename, 42))}</div>
                </div>
                <div class="panel-badges">
                    <span class="panel-badge {source_badge_cls}">{source_badge_text}</span>
                    {pages_badge}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="panel-header-wrap">
                <div>
                    <div class="panel-kicker">DOCUMENT VIEWER</div>
                    <div class="panel-heading">Document Canvas</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with st.container(height=720, border=True):
        if st.session_state.pdf_bytes:
            pdf_document = fitz.open(
                stream=st.session_state.pdf_bytes,
                filetype="pdf",
            )
            total_pages = len(pdf_document)
            pdf_document.close()

            if st.session_state.pending_page is not None:
                requested_page = int(st.session_state.pending_page)
                requested_page = max(
                    1,
                    min(requested_page, total_pages),
                )
                st.session_state.current_page = requested_page
                st.session_state.page_input = requested_page
                st.session_state.pending_page = None

            current_page = max(
                1,
                min(
                    st.session_state.current_page,
                    total_pages,
                ),
            )

            nav_prev_col, nav_page_col, nav_next_col, nav_hl_col = st.columns([1.1, 1.6, 1.1, 1.4])

            with nav_prev_col:
                if st.button(
                    "← Prev",
                    key="prev_page",
                    use_container_width=True,
                    disabled=current_page <= 1,
                ):
                    st.session_state.page_input = max(1, current_page - 1)
                    st.rerun()

            with nav_page_col:
                selected_page = st.number_input(
                    "Page",
                    min_value=1,
                    max_value=total_pages,
                    step=1,
                    key="page_input",
                    label_visibility="collapsed",
                )
                st.session_state.current_page = int(selected_page)

            with nav_next_col:
                if st.button(
                    "Next →",
                    key="next_page",
                    use_container_width=True,
                    disabled=current_page >= total_pages,
                ):
                    st.session_state.page_input = min(
                        total_pages,
                        current_page + 1,
                    )
                    st.rerun()

            with nav_hl_col:
                if st.session_state.highlight_text:
                    if st.button(
                        "✕ Clear",
                        key="clear_highlight_btn",
                        use_container_width=True,
                        help="Clear active highlight",
                    ):
                        clear_highlight()
                        st.rerun()
                else:
                    st.markdown(
                        f'<div class="page-counter-badge">Page {current_page} of {total_pages}</div>',
                        unsafe_allow_html=True,
                    )

            page_image, highlight_applied = render_pdf_page(
                pdf_bytes=st.session_state.pdf_bytes,
                page_number=st.session_state.current_page,
                highlight_text=st.session_state.highlight_text,
            )

            if st.session_state.highlight_text:
                if highlight_applied:
                    st.markdown(
                        f"""
                        <div class="source-highlight-banner active">
                            <span>✨ Source section highlighted on <strong>Page {st.session_state.current_page}</strong></span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f"""
                        <div class="source-highlight-banner warning">
                            <span>⚠️ Source text not found directly on Page {st.session_state.current_page}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            if page_image:
                st.markdown('<div class="pdf-canvas-wrapper"><div class="pdf-paper">', unsafe_allow_html=True)
                st.image(
                    page_image,
                    use_container_width=True,
                )
                st.markdown('</div></div>', unsafe_allow_html=True)

        elif st.session_state.image_bytes or (
            st.session_state.filename
            and any(st.session_state.filename.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp"))
        ):
            if not st.session_state.image_bytes and st.session_state.document_id:
                st.session_state.image_bytes = fetch_selected_document_bytes(
                    st.session_state.document_id
                )

            if st.session_state.image_bytes:
                has_active_highlight = bool(
                    st.session_state.get("highlight_text")
                    or st.session_state.get("selected_source_bbox")
                    or st.session_state.get("selected_source_bboxes")
                )
                img_c1, img_c2 = st.columns([1, 1])
                with img_c1:
                    show_all_ocr = st.checkbox(
                        "Show all OCR text regions",
                        value=st.session_state.get("show_all_ocr_regions", False),
                        key="toggle_all_ocr_regions",
                    )
                    st.session_state.show_all_ocr_regions = show_all_ocr
                with img_c2:
                    if has_active_highlight:
                        if st.button(
                            "✕ Clear highlight",
                            key="clear_image_highlight_btn",
                            use_container_width=True,
                        ):
                            clear_highlight()
                            st.rerun()

                orig_dims = st.session_state.get("selected_source_dimensions")
                orig_w, orig_h = (None, None)
                if orig_dims and isinstance(orig_dims, (list, tuple)) and len(orig_dims) == 2:
                    orig_w, orig_h = orig_dims[0], orig_dims[1]

                if not orig_w or not orig_h:
                    try:
                        with Image.open(BytesIO(st.session_state.image_bytes)) as pil_img:
                            orig_w, orig_h = pil_img.size
                    except Exception:
                        orig_w, orig_h = 1000, 1000

                fname_lower = (st.session_state.filename or "").lower()
                if fname_lower.endswith(".jpg") or fname_lower.endswith(".jpeg"):
                    mime_type = "image/jpeg"
                elif fname_lower.endswith(".webp"):
                    mime_type = "image/webp"
                else:
                    mime_type = "image/png"

                img_b64 = base64.b64encode(st.session_state.image_bytes).decode("utf-8")

                all_boxes = st.session_state.get("all_ocr_bboxes", [])
                selected_box = st.session_state.get("selected_source_bbox")
                selected_boxes = st.session_state.get("selected_source_bboxes", [])

                selected_boxes_json = json.dumps(selected_boxes or ([selected_box] if selected_box else []))
                overall_box_json = json.dumps(selected_box or {})
                all_ocr_boxes_json = json.dumps(all_boxes if show_all_ocr else [])

                aspect_ratio = orig_h / max(1, orig_w)
                estimated_height = int(680 * aspect_ratio) + 25
                viewer_height = min(900, max(280, estimated_height))

                component_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: transparent;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    overflow-x: hidden;
  }}
  .image-container {{
    position: relative;
    width: 100%;
    display: inline-block;
    border-radius: 8px;
    overflow: hidden;
    background: #080c1a;
    border: 1px solid rgba(99, 102, 241, 0.25);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
  }}
  .doc-image {{
    display: block;
    width: 100%;
    height: auto;
    user-select: none;
  }}
  .highlight-overlay {{
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
  }}
  .ocr-box {{
    fill: rgba(56, 189, 248, 0.08);
    stroke: rgba(56, 189, 248, 0.5);
    stroke-width: 1.5px;
    stroke-dasharray: 4,2;
    rx: 2px;
  }}
  .source-box {{
    fill: rgba(99, 102, 241, 0.38);
    stroke: #818cf8;
    stroke-width: 2.5px;
    rx: 4px;
    filter: drop-shadow(0 0 6px rgba(99, 102, 241, 0.7));
  }}
  .enclosing-box {{
    fill: none;
    stroke: #c084fc;
    stroke-width: 2px;
    stroke-dasharray: 6,3;
    rx: 6px;
    filter: drop-shadow(0 0 8px rgba(192, 132, 252, 0.6));
  }}
</style>
</head>
<body>

<div class="image-container" id="container">
  <img id="doc-image" class="doc-image" src="data:{mime_type};base64,{img_b64}" alt="Document Image" />
  <svg id="svg-overlay" class="highlight-overlay" xmlns="http://www.w3.org/2000/svg">
  </svg>
</div>

<script>
  const origW = {orig_w};
  const origH = {orig_h};
  const selectedBoxes = {selected_boxes_json};
  const overallBox = {overall_box_json};
  const allOcrBoxes = {all_ocr_boxes_json};

  const img = document.getElementById('doc-image');
  const svg = document.getElementById('svg-overlay');
  const container = document.getElementById('container');

  function renderHighlights() {{
    const dispW = img.clientWidth || img.offsetWidth;
    const dispH = img.clientHeight || img.offsetHeight;
    if (!dispW || !dispH || !origW || !origH) return;

    const scaleX = dispW / origW;
    const scaleY = dispH / origH;

    svg.innerHTML = '';
    svg.setAttribute('viewBox', '0 0 ' + dispW + ' ' + dispH);

    if (allOcrBoxes && allOcrBoxes.length > 0) {{
      allOcrBoxes.forEach(function(b) {{
        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('x', (b.x * scaleX));
        rect.setAttribute('y', (b.y * scaleY));
        rect.setAttribute('width', Math.max(2, b.width * scaleX));
        rect.setAttribute('height', Math.max(2, b.height * scaleY));
        rect.setAttribute('class', 'ocr-box');
        svg.appendChild(rect);
      }});
    }}

    let firstSourceEl = null;

    if (selectedBoxes && selectedBoxes.length > 0) {{
      selectedBoxes.forEach(function(b, idx) {{
        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        const sx = b.x * scaleX;
        const sy = b.y * scaleY;
        const sw = Math.max(3, b.width * scaleX);
        const sh = Math.max(3, b.height * scaleY);
        rect.setAttribute('x', sx);
        rect.setAttribute('y', sy);
        rect.setAttribute('width', sw);
        rect.setAttribute('height', sh);
        rect.setAttribute('class', 'source-box');
        rect.id = 'source-rect-' + idx;
        svg.appendChild(rect);
        if (!firstSourceEl) firstSourceEl = rect;
      }});

      if (overallBox && overallBox.x !== undefined && selectedBoxes.length > 1) {{
        const enc = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        const padX = 4 * scaleX;
        const padY = 4 * scaleY;
        enc.setAttribute('x', Math.max(0, overallBox.x * scaleX - padX));
        enc.setAttribute('y', Math.max(0, overallBox.y * scaleY - padY));
        enc.setAttribute('width', overallBox.width * scaleX + padX * 2);
        enc.setAttribute('height', overallBox.height * scaleY + padY * 2);
        enc.setAttribute('class', 'enclosing-box');
        svg.appendChild(enc);
      }}
    }}

    if (firstSourceEl) {{
      const targetY = parseFloat(firstSourceEl.getAttribute('y')) || 0;
      window.scrollTo({{ top: Math.max(0, targetY - 60), behavior: 'smooth' }});
    }}
  }}

  img.addEventListener('load', renderHighlights);
  if (img.complete) renderHighlights();

  window.addEventListener('resize', renderHighlights);
  if (window.ResizeObserver) {{
    new ResizeObserver(renderHighlights).observe(container);
  }}
</script>
</body>
</html>"""
                components.html(component_html, height=viewer_height, scrolling=True)

                if selected_box or selected_boxes:
                    conf = st.session_state.get("selected_source_confidence")
                    conf_badge = f" · Confidence: {int(conf * 100)}%" if conf else ""
                    match_type = st.session_state.get("selected_source_match_type")
                    type_badge = f" ({match_type} match)" if match_type else ""
                    st.markdown(
                        f"""
                        <div style="
                            margin-top: 6px;
                            margin-bottom: 10px;
                            padding: 8px 12px;
                            border-radius: 8px;
                            background: rgba(99, 102, 241, 0.14);
                            border: 1px solid rgba(99, 102, 241, 0.35);
                            font-size: 12px;
                            color: #c7d2fe;
                        ">
                            ✓ <strong>Source highlighted in image</strong>{type_badge}{conf_badge}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                elif st.session_state.get("highlight_text"):
                    st.markdown(
                        """
                        <div style="
                            margin-top: 6px;
                            margin-bottom: 10px;
                            padding: 8px 12px;
                            border-radius: 8px;
                            background: rgba(239, 68, 68, 0.12);
                            border: 1px solid rgba(239, 68, 68, 0.35);
                            font-size: 12px;
                            color: #fca5a5;
                        ">
                            ⚠️ <strong>Source location could not be identified in this image.</strong>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        """
                        <div style="
                            margin-top: 6px;
                            margin-bottom: 10px;
                            padding: 8px 12px;
                            border-radius: 8px;
                            background: rgba(99, 102, 241, 0.10);
                            border: 1px solid rgba(99, 102, 241, 0.25);
                            font-size: 11.5px;
                            color: #c7d2fe;
                        ">
                            ✓ <strong>OCR text extracted & indexed</strong>: Click any source citation or ask questions about this image in the AI Assistant panel.
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown(
                    """
                    <div class="workspace-empty-card">
                        <div class="empty-card-glyph">🖼️</div>
                        <div class="empty-card-title">Image preview unavailable</div>
                        <div class="empty-card-subtitle">
                            Preview unavailable / OCR text available.<br>
                            You can ask questions about this image in the chat panel.
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        elif st.session_state.filename and st.session_state.filename.lower().endswith(".docx"):
            st.markdown(
                """
                <div class="workspace-empty-card">
                    <div class="empty-card-glyph">📝</div>
                    <div class="empty-card-title">Word Document Active</div>
                    <div class="empty-card-subtitle">
                        DOCX content extracted and fully indexed.<br>
                        Ask questions in the AI Assistant panel to retrieve answers with section citations.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        elif st.session_state.filename:
            st.markdown(
                """
                <div class="workspace-empty-card">
                    <div class="empty-card-glyph">📄</div>
                    <div class="empty-card-title">Document Ready</div>
                    <div class="empty-card-subtitle">
                        Text extracted and indexed for Q&A.<br>
                        Ask questions in the AI Assistant panel.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        else:
            st.markdown(
                """
                <div class="workspace-empty-card">
                    <div class="empty-card-glyph">📚</div>
                    <div class="empty-card-title">Your document workspace</div>
                    <div class="empty-card-subtitle">
                        Upload a document or import one from Google Drive to start asking questions.
                    </div>
                    <div class="empty-card-formats">
                        <span class="format-pill">PDF</span>
                        <span class="format-pill">DOCX</span>
                        <span class="format-pill">PNG</span>
                        <span class="format-pill">JPG</span>
                        <span class="format-pill">WEBP</span>
                    </div>
                    <div class="empty-card-tip">
                        💡 Features: OCR text detection, Semantic Search, Page Highlighting & Google Drive MCP
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ============================================================================
# AI CHAT
# ============================================================================

with right_column:
    st.markdown(
        """
        <div class="panel-header-wrap">
            <div>
                <div class="panel-kicker">AI ASSISTANT</div>
                <div class="panel-heading">Ask questions about your document</div>
            </div>
            <div class="panel-badges">
                <span class="panel-badge badge-ready"><span class="pulse-dot"></span> Ready</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(height=720, border=True):
        if not st.session_state.document_id:
            st.markdown(
                """
                <div class="chat-empty-state">
                    <div class="chat-empty-icon">✨</div>
                    <div class="chat-empty-title">Start a conversation</div>
                    <div class="chat-empty-desc">
                        Upload or select a document from the workspace to begin asking grounded questions with AI.
                    </div>
                    <div class="chat-suggestions">
                        <div class="suggestion-chip">💡 "What is the main summary of this document?"</div>
                        <div class="suggestion-chip">💡 "What are the key technical concepts?"</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        elif not st.session_state.messages:
            st.markdown(
                f"""
                <div class="chat-empty-state">
                    <div class="chat-empty-icon">💬</div>
                    <div class="chat-empty-title">Ready to assist</div>
                    <div class="chat-empty-desc">
                        Ask any question about <strong>{escape_html(st.session_state.filename or "your document")}</strong>.<br>
                        Answers include verifiable source citations and page highlights.
                    </div>
                    <div class="chat-suggestions">
                        <div class="suggestion-chip">💡 "Provide an overview of this document"</div>
                        <div class="suggestion-chip">💡 "Explain the architecture and key concepts"</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        else:
            for message_index, message in enumerate(
                st.session_state.messages
            ):
                role = message.get("role", "assistant")
                content = message.get("content", "")

                with st.chat_message(role):
                    st.markdown(content)

                    render_sources(
                        sources=message.get("sources", []),
                        message_id=message_index,
                    )

    question = st.chat_input(
        "Ask anything about this document...",
        disabled=not bool(st.session_state.document_id),
    )

    if question:
        question = question.strip()

        if not question:
            st.stop()

        # ------------------------------------------------------------
        # 1. Ensure a conversation exists (no duplicates on reruns).
        # ------------------------------------------------------------
        if not st.session_state.get("conversation_id"):
            create_conversation_record(title=auto_title(question))
        elif (
            not st.session_state.get("conversation_title")
            or st.session_state.conversation_title == "New chat"
        ):
            new_title = auto_title(question)
            st.session_state.conversation_title = new_title

            try:
                requests.patch(
                    f"{BACKEND_URL}/api/conversations/{st.session_state.conversation_id}",
                    json={"title": new_title},
                    timeout=30,
                ).raise_for_status()
            except requests.exceptions.RequestException:
                pass

            load_conversations()

        # Clear any previous highlight from an earlier question.
        clear_highlight()

        # ------------------------------------------------------------
        # 2. Store the user message.
        # ------------------------------------------------------------
        current_count = len(st.session_state.messages)
        user_message_id = current_count + 1

        st.session_state.messages.append(
            {
                "id": user_message_id,
                "role": "user",
                "content": question,
                "sources": [],
            }
        )

        save_current_conversation()

        with st.chat_message("user"):
            st.markdown(question)

        # ------------------------------------------------------------
        # 3. Ask the backend and store the assistant message.
        # ------------------------------------------------------------
        assistant_message_id = current_count + 2

        with st.chat_message("assistant"):
            with st.spinner("Analyzing your document..."):
                payload = {
                    "question": question,
                }

                if st.session_state.document_id:
                    payload["document_id"] = st.session_state.document_id

                document_ids = [
                    doc.get("document_id")
                    for doc in st.session_state.documents
                    if isinstance(doc, dict) and doc.get("document_id")
                ]

                if document_ids:
                    payload["document_ids"] = document_ids

                if getattr(st.session_state, "conversation_id", None):
                    payload["conversation_id"] = st.session_state.conversation_id

                try:
                    response = requests.post(
                        f"{BACKEND_URL}/api/chat",
                        json=payload,
                        timeout=240,
                    )
                    response.raise_for_status()

                    data = response.json()

                    answer = (
                        data.get("answer")
                        or data.get("response")
                        or data.get("message")
                        or ""
                    )

                    sources = data.get("sources", [])

                    if not answer:
                        raise RuntimeError(
                            "Backend returned an empty answer."
                        )

                    st.markdown(answer)

                    render_sources(
                        sources=sources,
                        message_id=assistant_message_id,
                    )

                    st.session_state.messages.append(
                        {
                            "id": assistant_message_id,
                            "role": "assistant",
                            "content": answer,
                            "sources": sources,
                        }
                    )

                except Exception as error:
                    server_detail = None
                    if hasattr(error, "response") and getattr(error, "response", None) is not None:
                        try:
                            error_json = error.response.json()
                            server_detail = error_json.get("detail")
                        except Exception:
                            server_detail = getattr(error.response, "text", None)

                    if server_detail:
                        error_message = f"I couldn't get an answer: {server_detail}"
                    else:
                        error_message = f"I couldn't get an answer: {error}"

                    st.error(error_message)

                    st.session_state.messages.append(
                        {
                            "id": assistant_message_id,
                            "role": "assistant",
                            "content": error_message,
                            "sources": [],
                        }
                    )

                save_current_conversation()

        st.rerun()