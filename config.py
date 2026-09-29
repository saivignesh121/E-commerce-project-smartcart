import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Flask
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-this-secret")

# MySQL / Railway MySQL
DB_HOST = os.getenv("MYSQLHOST") or os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("MYSQLPORT") or os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("MYSQLUSER") or os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("MYSQLPASSWORD") or os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("MYSQLDATABASE") or os.getenv("DB_NAME", "smartcart_db")

# Email SMTP
MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() in {"1", "true", "yes", "on"}
MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")

# Razorpay
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")
