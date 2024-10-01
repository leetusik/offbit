from datetime import datetime, timedelta, timezone
from typing import Optional

import sqlalchemy as sa
import sqlalchemy.orm as so

from app import db


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

    # def set_open_api_key(self, api_key: str, public_key):
    #     """Encrypt and store the Upbit API key."""
    #     self.open_api_key_upbit = encrypt

    def __repr__(self):
        return f"<User {self.username}"
