import os


def load_env(path=".env"):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


load_env()

DB_PATH = os.environ.get("OLMS_DB_PATH", "olms.db")
HOST = os.environ.get("OLMS_HOST", "127.0.0.1")
PORT = int(os.environ.get("OLMS_PORT", "8000"))
LOAN_DAYS = int(os.environ.get("OLMS_LOAN_DAYS", "14"))
DAILY_FINE_INR = int(os.environ.get("OLMS_DAILY_FINE_INR", "5"))
MAX_ACTIVE_LOANS = int(os.environ.get("OLMS_MAX_ACTIVE_LOANS", "3"))
