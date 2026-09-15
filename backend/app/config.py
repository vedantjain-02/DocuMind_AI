import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
XAI_API_KEY = os.getenv("XAI_API_KEY", "").strip()