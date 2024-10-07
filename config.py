import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "you-will-never-guess"

    # Fetch the private and public key paths from environment variables
    PRIVATE_KEY_PATH = os.environ.get("PRIVATE_KEY_PATH")
    PUBLIC_KEY_PATH = os.environ.get("PUBLIC_KEY_PATH")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL"
    ) or "sqlite:///" + os.path.join(basedir, "app.db")
    MAIL_SERVER = os.environ.get("MAIL_SERVER")
    MAIL_PORT = int(os.environ.get("MAIL_PORT") or 25)
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS") is not None
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    ADMINS = ["leetusik@gmail.com", "swangle2100@gmail.com"]

    # Add your default values here
    MEMBERSHIP_DEFAULT_DURATION_DAYS = 30  # Default 30 days for membership
    MEMBERSHIP_DEFAULT_EXTEND_DAYS = 30  # Default 30 days for membership extension
