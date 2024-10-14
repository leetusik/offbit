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

    # Celery Configuration
    REDIS_URL = os.environ.get("REDIS_URL")
    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND")

    # Add your default values here
    MEMBERSHIP_DEFAULT_DURATION_DAYS = 30  # Default 30 days for membership
    MEMBERSHIP_DEFAULT_EXTEND_DAYS = 30  # Default 30 days for membership extension


# {
#     "DEBUG": False,
#     "TESTING": False,
#     "PROPAGATE_EXCEPTIONS": None,
#     "SECRET_KEY": "you-will-never-guess",
#     "PERMANENT_SESSION_LIFETIME": datetime.timedelta(days=31),
#     "USE_X_SENDFILE": False,
#     "SERVER_NAME": None,
#     "APPLICATION_ROOT": "/",
#     "SESSION_COOKIE_NAME": "session",
#     "SESSION_COOKIE_DOMAIN": None,
#     "SESSION_COOKIE_PATH": None,
#     "SESSION_COOKIE_HTTPONLY": True,
#     "SESSION_COOKIE_SECURE": False,
#     "SESSION_COOKIE_SAMESITE": None,
#     "SESSION_REFRESH_EACH_REQUEST": True,
#     "MAX_CONTENT_LENGTH": None,
#     "SEND_FILE_MAX_AGE_DEFAULT": None,
#     "TRAP_BAD_REQUEST_ERRORS": None,
#     "TRAP_HTTP_EXCEPTIONS": False,
#     "EXPLAIN_TEMPLATE_LOADING": False,
#     "PREFERRED_URL_SCHEME": "http",
#     "TEMPLATES_AUTO_RELOAD": None,
#     "MAX_COOKIE_SIZE": 4093,
#     "ADMINS": ["leetusik@gmail.com", "swangle2100@gmail.com"],
#     "CELERY_BROKER_URL": None,
#     "CELERY_RESULT_BACKEND": None,
#     "MAIL_PASSWORD": None,
#     "MAIL_PORT": 25,
#     "MAIL_SERVER": None,
#     "MAIL_USERNAME": None,
#     "MAIL_USE_TLS": False,
#     "MEMBERSHIP_DEFAULT_DURATION_DAYS": 30,
#     "MEMBERSHIP_DEFAULT_EXTEND_DAYS": 30,
#     "PRIVATE_KEY_PATH": None,
#     "PUBLIC_KEY_PATH": None,
#     "REDIS_URL": None,
#     "SQLALCHEMY_DATABASE_URI": "sqlite:////Users/sugang/Desktop/projects/offbit/app.db",
#     "SQLALCHEMY_ENGINE_OPTIONS": {},
#     "SQLALCHEMY_ECHO": False,
#     "SQLALCHEMY_BINDS": {},
#     "SQLALCHEMY_RECORD_QUERIES": False,
#     "SQLALCHEMY_TRACK_MODIFICATIONS": False,
# }
