import enum
import random
import re
import time
from datetime import datetime, timedelta, timezone
from hashlib import md5
from typing import Optional

import pandas as pd
import pyupbit
import sqlalchemy as sa
import sqlalchemy.orm as so
from flask import current_app, flash, redirect, url_for
from flask_login import UserMixin

# from sqlalchemy import Enum
from werkzeug.security import check_password_hash, generate_password_hash

from app import db, login
from app.utils.crypto_utils import decrypt_api_key, encrypt_api_key
from app.utils.df_utils import get_dataframe_from_pickle, save_dataframe_as_pickle
from app.utils.handle_candle import concat_candles, get_candles
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
    membership_type: so.Mapped[Optional[MembershipType]] = so.mapped_column(
        sa.Enum(MembershipType), nullable=False, default=MembershipType.BIKE
    )
    membership_expiration: so.Mapped[Optional[datetime]] = so.mapped_column(sa.DateTime)
    # Add available balance field
    available: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False, default=0)

    strategies: so.Mapped[list["UserStrategy"]] = so.relationship(
        "UserStrategy",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select",  # Ensure this returns a list of UserStrategy objects
    )

    # Add a property to return the upper limit based on membership type
    @property
    def upper_limit(self):
        if self.membership_type == MembershipType.BIKE:
            return 100000
        elif self.membership_type == MembershipType.MOTORCYCLE:
            return 1000000
        elif self.membership_type == MembershipType.CAR:
            return 10000000
        elif self.membership_type == MembershipType.AIRPLANE:
            return 100000000
        return 0  # Default, if needed

    # Method to update available balance based on strategies
    def update_available(self):
        total_allocated = sum(
            strategy.investing_limit
            for strategy in list(self.strategies)
            if strategy.active
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
        self.open_api_key_access_upbit = encrypt_api_key(public_key, api_key_access)
        self.open_api_key_secret_upbit = encrypt_api_key(public_key, api_key_secret)
        self.open_api_key_expiration = expiration_date

    def get_open_api_key(self) -> str:
        """Decrypt and retrieve the Upbit API key."""
        private_key = load_private_key(current_app.config["PRIVATE_KEY_PATH"])
        if self.open_api_key_access_upbit and self.open_api_key_secret_upbit:
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

    def is_my_strategy(self, strategy):
        return (
            db.session.scalar(
                sa.select(UserStrategy).where(
                    UserStrategy.user_id == self.id,
                    UserStrategy.strategy_id == strategy.id,
                )
            )
            is not None
        )

    @login.user_loader
    def load_user(id):
        return db.session.get(User, int(id))


class Strategy(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(
        sa.String(64),
        index=True,
        unique=True,
    )
    description: so.Mapped[Optional[str]] = so.mapped_column(
        sa.String(255),
        nullable=True,
    )
    # Field to store pickled DataFrame data
    historical_data: so.Mapped[Optional[bytes]] = so.mapped_column(
        sa.LargeBinary,
        nullable=True,
    )

    # Field to store pickled DataFrame data
    short_historical_data: so.Mapped[Optional[bytes]] = so.mapped_column(
        sa.LargeBinary,
        nullable=True,
    )

    # Many-to-many relationship via UserStrategy
    users: so.Mapped["UserStrategy"] = so.relationship(
        "UserStrategy",
        back_populates="strategy",
        cascade="all, delete-orphan",
    )

    def save_historical_data(self, df: pd.DataFrame):
        """Save the historical data as binary pickle data."""
        # Use df_utils to convert DataFrame to pickle format
        self.historical_data = save_dataframe_as_pickle(df)
        self.short_historical_data = save_dataframe_as_pickle(df.tail(28000))
        db.session.commit()
        print(f"Historical data successfully saved to strategy {self.name}.")

    def get_historical_data(self) -> pd.DataFrame:
        """Retrieve the historical data as a DataFrame."""
        if self.historical_data:
            # Use df_utils to convert binary pickle data back to a DataFrame
            df = get_dataframe_from_pickle(self.historical_data)
            return df
        else:
            print(f"No historical data available for strategy {self.name}.")
            return None

    def get_short_historical_data(self) -> pd.DataFrame:
        """Retrieve the historical data as a DataFrame."""
        if self.short_historical_data:
            # Use df_utils to convert binary pickle data back to a DataFrame
            df = get_dataframe_from_pickle(self.short_historical_data)
            return df
        else:
            print(f"No historical data available for strategy {self.name}.")
            return None

    def make_historical_data(self):
        if not self.historical_data:
            # get historical data from the 2021/04/01 every minutes
            long_df = get_candles()
        else:
            long_df = get_dataframe_from_pickle(self.historical_data)

            # check if long_df is outdated. if it is, then get fresh long_df
            # Assuming formatted_now is a datetime object without seconds (formatted_now = datetime.now().replace(second=0, microsecond=0))
            formatted_now = datetime.now(timezone.utc).replace(
                second=0, microsecond=0
            )  # Convert formatted_now to naive if it has timezone info
            formatted_now_naive = formatted_now.replace(tzinfo=None)
            last_row = long_df.iloc[-1]
            # Convert the 'time_utc' column value from the last row to a datetime object
            last_time_utc = pd.to_datetime(last_row["time_utc"])

            # Compare the two naive datetime objects
            if last_time_utc + timedelta(hours=3) < formatted_now_naive:
                long_df = get_candles()

        now_minus_320 = datetime.now(timezone.utc) - timedelta(hours=3, minutes=20)
        now_minus_320 = now_minus_320.strftime("%Y-%m-%d %H:%M:%S")
        short_df = get_candles(start=now_minus_320)
        final_df = concat_candles(long_df=long_df, short_df=short_df)

        # add feature if final_df(concated df) has a time gap a lot.

        self.save_historical_data(final_df)
        pass

    def execute_logic_for_user(self, user_strategy):
        """The core strategy logic, executed for a specific user."""
        # check if the historical data is updated.
        while True:
            # Assuming formatted_now is a datetime object without seconds (formatted_now = datetime.now().replace(second=0, microsecond=0))
            formatted_now = datetime.now(timezone.utc).replace(
                second=0, microsecond=0
            )  # Convert formatted_now to naive if it has timezone info
            formatted_now_naive = formatted_now.replace(tzinfo=None)

            short_historical_data = self.get_short_historical_data()
            # Get the last row of the DataFrame
            last_row = short_historical_data.iloc[-1]

            # Convert the 'time_utc' column value from the last row to a datetime object
            last_time_utc = pd.to_datetime(last_row["time_utc"])

            # Compare the two naive datetime objects
            if last_time_utc == formatted_now_naive:
                break
            else:
                time.sleep(0.1)
                current_app.logger.info(
                    f"User: {user_strategy.user.username}, no historical data updated. try again."
                )

        try:
            upbit = user_strategy.user.create_upbit_client()
            # Fetch the initial balance to check for unexpected changes
            if user_strategy.holding_position:
                coin_balance: float = upbit.get_balance("KRW-BTC")
                sell_needed: float = min(coin_balance, user_strategy.sell_needed)
                # if coin_balance < sell_needed:
                #     send_email(
                #         "[Offibit] No sufficient coin is there to automated trading",
                #         user_strategy.user,
                #     )
                #     user_strategy.deactivate()
                #     return  # Stop execution if there's an unexpected balance change
            else:
                krw_balance: float = upbit.get_balance()
                buy_needed: float = min(
                    krw_balance * 0.9995, user_strategy.investing_limit
                )

            # Buy & sell condition check and execute order
            condition = get_condition(
                self.name,
                user_strategy.execution_time,
                user_strategy.holding_position,
                short_historical_data,
            )  # Pseudo-function to get the buy/sell signal

            if condition == "buy":
                buy = upbit.buy_market_order("KRW-BTC", buy_needed)
                # get order data
                order = upbit.get_order(buy["uuid"])
                trades = order.get("trades")
                while not trades:
                    time.sleep(1)
                    order = upbit.get_order(buy["uuid"])
                    trades = order.get("trades")
                buy_krw = float(order["price"])
                fee = float(order["reserved_fee"])
                executed_volume = float(order["executed_volume"])
                # buy_price = round((buy_krw + fee) / executed_volume)

                user_strategy.sell_needed = executed_volume
                user_strategy.holding_position = True
                db.session.commit()

            elif condition == "sell":
                sell = upbit.sell_market_order("KRW-BTC", sell_needed)
                user_strategy.holding_position = False
                db.session.commit()

            # # Save data
            # save_data()

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

    execution_time: so.Mapped[Optional[datetime.time]] = so.mapped_column(
        sa.Time, nullable=True
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
    # Field to store pickled DataFrame data
    historical_data_resampled: so.Mapped[bytes] = so.mapped_column(
        sa.LargeBinary,
        nullable=True,
    )
    ## those are for later save data and showing data
    # def save_historical_data_resampled(self, df: pd.DataFrame):
    #     """Save the historical data as binary pickle data."""
    #     # Use df_utils to convert DataFrame to pickle format
    #     self.historical_data_resampled = save_dataframe_as_pickle(df)
    #     db.session.commit()
    #     print(f"Historical data successfully saved to strategy {self.strategy.name}.")

    # def get_historical_data_resampled(self) -> pd.DataFrame:
    #     """Retrieve the historical data as a DataFrame."""
    #     if self.historical_data_resampled:
    #         # Use df_utils to convert binary pickle data back to a DataFrame
    #         df = get_dataframe_from_pickle(self.historical_data_resampled)
    #         return df
    #     else:
    #         print(f"No historical data available for strategy {self.strategy.name}.")
    #         return None

    @property
    def investing_limit(self):
        # Public getter for _investing_limit
        return self._investing_limit

    @investing_limit.setter
    def investing_limit(self, value):
        # Allow setting any value, even if it exceeds available balance
        self._investing_limit = value
        # No validation for now, commit changes directly
        db.session.commit()

    def check_investing_limit(self):
        # Check if the new investing limit exceeds the user's available balance
        self.user.update_available()
        if self.investing_limit > self.user.available:
            raise ValueError(
                f"Investing limit {self.investing_limit} exceeds user's available balance of {self.user.available}"
            )
        return True

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
        time_obj = (
            datetime.strptime(time_str, time_format)
            .replace(microsecond=0, tzinfo=None)
            .time()
        )

        self.execution_time = time_obj
        print(time_obj)
        print(self.execution_time)
        db.session.commit()

    def activate(self):
        """activate a strategy and update the user's available balance."""
        data_ready = self.strategy.get_short_historical_data()
        if not data_ready:
            # Flash error message directly (if in route context)
            # return redirect(url_for("user.dashboard"))
            return (False, f"no data")
        # Recalculate the user's available balance
        if self.check_investing_limit():
            self.active = True
            db.session.commit()
            self.user.update_available()
            return (True, "success")
        else:
            return (False, f"no money")

    def deactivate(self):
        """Deactivate a strategy and update the user's available balance."""
        self.active = False
        db.session.commit()
        # Recalculate the user's available balance
        self.user.update_available()

    def __repr__(self):
        return f"<UserStrategy user_id={self.user_id}, strategy_id={self.strategy_id}>"
