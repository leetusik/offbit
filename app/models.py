from datetime import datetime, timedelta, timezone
from typing import Optional

import sqlalchemy as sa
import sqlalchemy.orm as so
from flask import current_app

from app import db, login
from app.utils.crypto_utils import decrypt_api_key, encrypt_api_key
from app.utils.key_manager import load_private_key, load_public_key


class User(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(
        sa.String(64),
        index=True,
        unique=True,
    )
    email: so.Mapped[str] = so.mapped_column(
        sa.String(120),
        index=True,
        unique=True,
    )
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    open_api_key_upbit: so.Mapped[Optional[bytes]] = so.mapped_column(sa.LargeBinary)

    def set_open_api_key(self, api_key: str):
        """Encrypt and store the Upbit API key."""
        public_key = load_public_key(current_app.config["PUBLIC_KEY_PATH"])
        self.open_api_key_upbit = encrypt_api_key(public_key, api_key)

    def get_open_api_key(self) -> str:
        """Decrypt and retrieve the Upbit API key."""
        private_key = load_private_key(current_app.config["PRIVATE_KEY_PATH"])
        if self.open_api_key_upbit:
            return decrypt_api_key(private_key, self.open_api_key_upbit).decode("utf-8")
        return None

    @login.user_loader
    def load_user(id):
        return db.session.get(User, int(id))

    def __repr__(self):
        return f"<User {self.username}>"
