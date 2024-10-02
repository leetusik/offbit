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
