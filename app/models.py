import random
import re
from datetime import datetime, timedelta, timezone
from hashlib import md5
from typing import Optional

import sqlalchemy as sa
import sqlalchemy.orm as so
from flask import current_app
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db, login
from app.utils.crypto_utils import decrypt_api_key, encrypt_api_key
from app.utils.key_manager import load_private_key, load_public_key


class User(UserMixin, db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(
        sa.String(64),
        index=True,
        unique=False,
    )
    email: so.Mapped[str] = so.mapped_column(
        sa.String(120),
        index=True,
        unique=True,
    )
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    open_api_key_upbit: so.Mapped[Optional[bytes]] = so.mapped_column(sa.LargeBinary)
    open_api_key_expiration: so.Mapped[Optional[datetime]] = so.mapped_column(
        sa.DateTime
    )
    verification_code: so.Mapped[Optional[int]] = so.mapped_column(sa.Integer)
    verification_code_expiration: so.Mapped[Optional[datetime]] = so.mapped_column(
        sa.DateTime
    )
    # Membership-related fields
    membership_type: so.Mapped[Optional[str]] = so.mapped_column(sa.String(64))
    membership_expiration: so.Mapped[Optional[datetime]] = so.mapped_column(sa.DateTime)

    strategies: so.Mapped["UserStrategy"] = so.relationship(
        "UserStrategy",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<User {self.username}>"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def avatar(self, size):
        digest = md5(self.email.lower().encode("utf-8")).hexdigest()
        return f"https://www.gravatar.com/avatar/{digest}?d=identicon&s={size}"

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def set_open_api_key(self, api_key: str, expiration_date):
        """Encrypt and store the Upbit API key."""
        public_key = load_public_key(current_app.config["PUBLIC_KEY_PATH"])
        self.open_api_key_upbit = encrypt_api_key(public_key, api_key)
        self.open_api_key_expiration = expiration_date

    def get_open_api_key(self) -> str:
        """Decrypt and retrieve the Upbit API key."""
        private_key = load_private_key(current_app.config["PRIVATE_KEY_PATH"])
        if self.open_api_key_upbit:
            return decrypt_api_key(private_key, self.open_api_key_upbit).decode("utf-8")
        return None

    def generate_verification_code(self):
        return random.randint(100000, 999999)

    def set_verification_code(self):
        self.verification_code = self.generate_verification_code()
        self.verification_code_expiration = datetime.now(timezone.utc) + timedelta(
            minutes=1
        )
        db.session.commit()

    def set_membership(
        self, membership_type: str = "basic", duration_days: Optional[int] = None
    ):
        """Sets membership type and expiration with optional duration."""
        # Use default from config if no duration is provided
        duration_days = (
            duration_days or current_app.config["MEMBERSHIP_DEFAULT_DURATION_DAYS"]
        )
        self.membership_type = membership_type
        self.membership_expiration = datetime.now(timezone.utc) + timedelta(
            days=duration_days
        )
        db.session.commit()

    def is_membership_active(self) -> bool:
        """Returns True if membership is still active, False otherwise."""
        if self.membership_expiration:
            return self.membership_expiration > datetime.now(timezone.utc)
        return False

    def extend_membership(self, extra_days: Optional[int] = None):
        """Extend the membership by a given number of days, default from config."""
        extra_days = extra_days or current_app.config["MEMBERSHIP_DEFAULT_EXTEND_DAYS"]
        if self.membership_expiration and self.is_membership_active():
            self.membership_expiration += timedelta(days=extra_days)
        else:
            self.membership_expiration = datetime.now(timezone.utc) + timedelta(
                days=extra_days
            )
        db.session.commit()

    def mask_email(self):
        """Mask the email address for privacy."""
        email_pattern = r"(^[^@]{3})[^@]*(@.*$)"
        masked_email = re.sub(email_pattern, r"\1***\2", self.email)
        return masked_email

    @login.user_loader
    def load_user(id):
        return db.session.get(User, int(id))


class Strategy(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(
        sa.String(64),
        index=True,
        unique=False,
    )
    description: so.Mapped[Optional[str]] = so.mapped_column(
        sa.String(255),
        nullable=True,
    )
    # Many-to-many relationship via UserStrategy
    users: so.Mapped["UserStrategy"] = so.relationship(
        "UserStrategy",
        back_populates="strategy",
        cascade="all, delete-orphan",
    )

    def execute_logic_for_user(self, user):
        """The core strategy logic, executed for a specific user."""
        current_app.logger.info(
            f"Executing logic of {self.name} for user {user.username}"
        )

        # # Example of core logic: a trend-following strategy
        # if self.name == "Trend Following":
        #     # Example logic for buying/selling based on some conditions
        #     market_trend = get_current_market_trend()  # Pseudo-function to get market data
        #     if market_trend == "upward":
        #         print(f"{user.username} buys due to upward trend.")
        #         place_buy_order(user)
        #     elif market_trend == "downward":
        #         print(f"{user.username} sells due to downward trend.")
        #         place_sell_order(user)

    def __repr__(self):
        return f"<Strategy {self.name}>"


class UserStrategy(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    user_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("user.id"),
        nullable=False,
    )
    strategy_id: so.Mapped[int] = so.mapped_column(
        sa.ForeignKey("strategy.id"),
        nullable=False,
    )
    active: so.Mapped[bool] = so.mapped_column(
        sa.Boolean,
        default=False,
        nullable=False,
    )

    execution_time: so.Mapped[Optional[datetime]] = so.mapped_column(
        sa.DateTime, nullable=True
    )

    # Relationships
    user: so.Mapped["User"] = so.relationship(
        "User",
        back_populates="strategies",
    )
    strategy: so.Mapped["Strategy"] = so.relationship(
        "Strategy",
        back_populates="users",
    )

    def execute(self):
        """Execute the strategy for the specific user with execution_time logic."""
        if self.execution_time:
            print(
                f"Executing {self.strategy.name} for {self.user.username} at {self.execution_time}"
            )
        else:
            print(f"Executing {self.strategy.name} for {self.user.username} now")

        # Call the core strategy logic and apply it to the user
        self.strategy.execute_logic_for_user(self.user)

    def __repr__(self):
        return f"<UserStrategy user_id={self.user_id}, strategy_id={self.strategy_id}>"
