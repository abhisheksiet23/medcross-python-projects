"""
Central configuration for the WhatsApp Campaign & Inbox Platform.

Values are loaded from environment variables (.env file) but can also be
overridden at runtime from the Settings module in the app itself — those
runtime overrides are stored in the `settings` DB table and take priority
over the .env values (see database.get_setting()).
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# --- WhatsApp Cloud API ---
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_BUSINESS_ACCOUNT_ID = os.getenv("WHATSAPP_BUSINESS_ACCOUNT_ID", "")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "changeme")
WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v21.0")

# --- Storage ---
DB_PATH = str(BASE_DIR / "platform.db")
LOG_PATH = str(BASE_DIR / "platform.log")

# --- App ---
APP_NAME = "WhatsApp Campaign & Inbox Platform"
