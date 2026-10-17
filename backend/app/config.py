import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
# Look for .env in backend directory, then project root
load_dotenv(BASE_DIR / ".env")
load_dotenv()

class Settings:
    app_name = os.getenv("APP_NAME", "Voice Banking Agent Demo")
    database_url = os.getenv("DATABASE_URL", "sqlite:///./voice_banking.db")
    cors_origins = [x.strip() for x in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173").split(",") if x.strip()]
    payment_threshold = int(os.getenv("PAYMENT_THRESHOLD", "5000"))
    per_payment_limit = int(os.getenv("PER_PAYMENT_LIMIT", "10000"))
    daily_limit = int(os.getenv("DAILY_LIMIT", "20000"))
    confidence_threshold = float(os.getenv("CONFIDENCE_THRESHOLD", "0.78"))
    secret_key = os.getenv("SECRET_KEY", "voice-banking-dev-secret-key-32chars")
    spoof_provider = os.getenv("SPOOF_PROVIDER", "disabled")
    spoof_api_url = os.getenv("SPOOF_API_URL", "")
    spoof_api_key = os.getenv("SPOOF_API_KEY", "")

settings = Settings()
