import enum
import random
import re
from datetime import datetime, timedelta, timezone
from hashlib import md5
from typing import Optional

import pyupbit
import sqlalchemy as sa
import sqlalchemy.orm as so
from flask import current_app
from flask_login import UserMixin
from sqlalchemy import Enum
from werkzeug.security import check_password_hash, generate_password_hash

from app import db, login
from app.utils.crypto_utils import decrypt_api_key, encrypt_api_key
from app.utils.key_manager import load_private_key, load_public_key
from app.utils.trading_conditions import get_condition


class MembershipType(enum.Enum):
    BIKE = "bike"
    MOTORCYCLE = "motorcycle"
    CAR = "car"
    AIRPLANE = "airplane"


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
    open_api_key_access_upbit: so.Mapped[Optional[bytes]] = so.mapped_column(
        sa.LargeBinary, nullable=True
    )
    open_api_key_secret_upbit: so.Mapped[Optional[bytes]] = so.mapped_column(
        sa.LargeBinary, nullable=True
    )
    open_api_key_expiration: so.Mapped[Optional[datetime]] = so.mapped_column(
        sa.DateTime
    )
    verification_code: so.Mapped[Optional[int]] = so.mapped_column(sa.Integer)
    verification_code_expiration: so.Mapped[Optional[datetime]] = so.mapped_column(
        sa.DateTime
    )
    # Membership-related fields
    # Use Enum for membership type
    membership_type: sa.Mapped[Optional[MembershipType]] = sa.mapped_column(
        Enum(MembershipType), nullable=False, default=MembershipType.BIKE
    )
    membership_expiration: so.Mapped[Optional[datetime]] = so.mapped_column(sa.DateTime)
    # Add available balance field
    available: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False, default=0)

    strategies: so.Mapped["UserStrategy"] = so.relationship(
        "UserStrategy",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # Add a property to return the upper limit based on membership type
    @property
    def upper_limit(self):
        if self.membership_type == MembershipType.BIKE:
            return 10
        elif self.membership_type == MembershipType.MOTORCYCLE:
            return 100
        elif self.membership_type == MembershipType.CAR:
            return 1000
        elif self.membership_type == MembershipType.AIRPLANE:
            return 10000
        return 0  # Default, if needed

    # Method to update available balance based on strategies
    def update_available(self):
        total_allocated = sum(
            strategy.investing_limit for strategy in self.strategies if strategy.active
        )
        self.available = self.upper_limit - total_allocated
        db.session.commit()

    def __repr__(self):
        return f"<User {self.username}>"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def avatar(self, size):
        digest = md5(self.email.lower().encode("utf-8")).hexdigest()
        return f"https://www.gravatar.com/avatar/{digest}?d=identicon&s={size}"

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def set_open_api_key(
        self, api_key_access: str, api_key_secret: str, expiration_date
    ):
        """Encrypt and store the Upbit API key."""
        public_key = load_public_key(current_app.config["PUBLIC_KEY_PATH"])
        self.open_api_key_upbit_access = encrypt_api_key(public_key, api_key_access)
        self.open_api_key_upbit_secret = encrypt_api_key(public_key, api_key_secret)
        self.open_api_key_expiration = expiration_date

    def get_open_api_key(self) -> str:
        """Decrypt and retrieve the Upbit API key."""
        private_key = load_private_key(current_app.config["PRIVATE_KEY_PATH"])
        if self.open_api_key_upbit:
            return (
                decrypt_api_key(private_key, self.open_api_key_upbit_access).decode(
                    "utf-8"
                ),
                decrypt_api_key(private_key, self.open_api_key_upbit_secret).decode(
                    "utf-8"
                ),
            )
        return None

    def generate_verification_code(self):
        return random.randint(100000, 999999)

    def set_verification_code(self):
        self.verification_code = self.generate_verification_code()
        self.verification_code_expiration = datetime.now(timezone.utc) + timedelta(
            minutes=1
        )
        db.session.commit()

    def set_membership(self, membership_type, duration_days: Optional[int]):
        """Safely update membership type."""
        duration_days = (
            duration_days or current_app.config["MEMBERSHIP_DEFAULT_DURATION_DAYS"]
        )
        if membership_type in MembershipType:
            self.membership_type = membership_type
            self.membership_expiration = datetime.now(timezone.utc) + timedelta(
                days=duration_days
            )
            db.session.commit()
        else:
            raise ValueError(f"Invalid membership type: {membership_type}")

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

    def create_upbit_client(self):
        """Create and return a pyupbit Upbit client using the user's API keys."""
        api_key_access, api_key_secret = self.get_open_api_key()
        return pyupbit.Upbit(access=api_key_access, secret=api_key_secret)

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

    def execute_logic_for_user(self, user_strategy):
        """The core strategy logic, executed for a specific user."""
        try:
            upbit = user_strategy.user.create_upbit_client()
            # Fetch the initial balance to check for unexpected changes
            if user_strategy.holding_position:
                coin_balance: float = upbit.get_balance("KRW-BTC")
                sell_needed: float = user_strategy.sell_needed
                if coin_balance < sell_needed:
                    send_email(
                        "[Offibit] No sufficient coin is there to automated trading",
                        user_strategy.user,
                    )
                    user_strategy.deactivate()
                    return  # Stop execution if there's an unexpected balance change
            else:
                krw_balance: float = upbit.get_balance()
                buy_needed: float = user_strategy.investing_limit
                if krw_balance < buy_needed:
                    send_email(
                        "[Offibit] No sufficient krw is there to automated trading",
                        user_strategy.user,
                    )
                    user_strategy.deactivate()
                    return  # Stop execution if there's an unexpected balance change

            # Buy & sell condition check and execute order
            condition = get_condition(
                self.name,
                user_strategy.execution_time,
                user_strategy.holding_position,
            )  # Pseudo-function to get the buy/sell signal

            if condition == "buy":
                user_strategy.user.buy()  # Pseudo-function for placing a buy order
            elif condition == "sell":
                user_strategy.user.sell()  # Pseudo-function for placing a sell order

            # Fetch the balance again after the order to update the user's balance
            updated_balance = get_balance()

            # Update user strategy's balance after executing the trade
            user_strategy.balance = updated_balance

            # Save order and condition data
            save_order_data()  # Pseudo-function to save order data
            save_condition_data()  # Pseudo-function to save condition data

            # Commit the changes after all updates
            db.session.commit()

            # Log the successful execution
            current_app.logger.info(
                f"Executed strategy {user_strategy.strategy.name} for {user_strategy.user.username}"
            )

        except Exception as e:
            # Handle any errors during the process
            current_app.logger.error(
                f"Error executing strategy {user_strategy.strategy.name} for {user_strategy.user.username}: {str(e)}"
            )
            raise  # Re-raise the exception if necessary

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

    # Set default _investing_limit to 0, making it private
    _investing_limit: so.Mapped[int] = so.mapped_column(
        sa.Integer,
        nullable=False,
        default=0,
    )

    holding_position: so.Mapped[bool] = so.mapped_column(
        sa.Boolean,
        default=False,
        nullable=False,
    )

    sell_needed: so.Mapped[float] = so.mapped_column(
        sa.Float,
        default=0,
        nullable=False,
    )

    @property
    def investing_limit(self):
        # Public getter for _investing_limit
        return self._investing_limit

    @investing_limit.setter
    def investing_limit(self, value):
        # Check if the new investing limit exceeds the user's available balance
        if value > self.user.available:
            raise ValueError(
                f"Investing limit {value} exceeds user's available balance of {self.user.available}"
            )
        # Set the private _investing_limit if the value is valid
        self._investing_limit = value
        # Update user's available balance
        self.user.available -= value
        db.session.commit()

    def execute(self):
        """Execute the strategy for the specific user at the configured execution time."""
        if self.execution_time:
            print(
                f"Executing {self.strategy.name} for {self.user.username} at {self.execution_time}"
            )
        else:
            print(f"Executing {self.strategy.name} for {self.user.username} now")

        # Call the core strategy logic and apply it to the user
        self.strategy.execute_logic_for_user(self)

    def set_execution_time(self, time_str: str):
        """Sets the execution time based on a provided time string in hh:mm:ss format."""
        # Parse the string and store it as a timezone-aware datetime in UTC
        time_format = "%H:%M:%S"
        time_obj = datetime.strptime(time_str, time_format).time()
        now = datetime.now(timezone.utc).replace(microsecond=0)

        # Combine current date with the provided time and store it as a UTC-aware datetime
        execution_datetime = datetime.combine(now.date(), time_obj).astimezone(
            timezone.utc
        )
        self.execution_time = execution_datetime
        db.session.commit()

    def activate(self):
        """Deactivate a strategy and update the user's available balance."""
        self.active = True
        db.session.commit()
        # Recalculate the user's available balance
        self.user.update_available()

    def deactivate(self):
        """Deactivate a strategy and update the user's available balance."""
        self.active = False
        db.session.commit()
        # Recalculate the user's available balance
        self.user.update_available()

    def __repr__(self):
        return f"<UserStrategy user_id={self.user_id}, strategy_id={self.strategy_id}>"
