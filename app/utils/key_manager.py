import base64
import hashlib

from cryptography.fernet import Fernet


def get_fernet(app):
    """Generate a Fernet encryption key based on the Flask app's SECRET_KEY."""
    # Derive a 32-byte encryption key from the app's SECRET_KEY
    key = base64.urlsafe_b64encode(
        hashlib.sha256(app.config["SECRET_KEY"].encode()).digest()
    )
    return Fernet(key)
