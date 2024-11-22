from datetime import datetime

import sqlalchemy as sa
from flask_login import current_user
from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    FloatField,
    HiddenField,
    IntegerField,
    PasswordField,
    RadioField,
    SelectField,
    StringField,
    SubmitField,
)
from wtforms.fields import DateTimeLocalField, TimeField
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    NumberRange,
    Optional,
    Regexp,
    ValidationError,
)

from app import db
from app.models import User


class UserResetPasswordForm(FlaskForm):
    before_password = PasswordField(
        ("현재 비밀번호"), validators=[DataRequired("비밀번호를 입력해 주세요")]
    )
    password = PasswordField(
        ("새로운 비밀번호"), validators=[DataRequired("비밀번호를 입력해 주세요")]
    )
    confirm_password = PasswordField(
        "새로운 비밀번호 확인",
        validators=[
            DataRequired("비밀번호를 다시 입력해 일치하는지 확인해 주세요"),
            EqualTo("password", message="비밀번호가 일치하지 않습니다"),
        ],
    )
    submit = SubmitField("등록하기")

    def validate_before_password(self, before_password):
        password_check = current_user.check_password(before_password.data)
        if not password_check:
            raise ValidationError("현재 비밀번호가 올바르지 않습니다.")


# api_key validate feature add later.
class SetAPIKeyForm(FlaskForm):
    platform = SelectField(
        "Platform",
        choices=[("upbit", "Upbit")],
        default="upbit",
        validators=[DataRequired()],
    )
    api_key_access = StringField("API Key Access", validators=[DataRequired()])
    api_key_secret = StringField("API Key Secret", validators=[DataRequired()])
    # Use DateTimeLocalField from wtforms.fields
    expiration = DateTimeLocalField(
        "API Key Expiration",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired()],
    )

    submit = SubmitField("Submit")


class SetOneParamUserStrategyForm(FlaskForm):
    currency = SelectField(
        "매매 종목 선택",
        choices=[],  # This will be populated dynamically
        validators=[DataRequired(message="매매 종목을 선택해주세요.")],
    )
    investing_limit = IntegerField(
        "전략 투자금 한도",
        validators=[
            DataRequired(),
            NumberRange(
                min=100000, message="투자금은 100,000원 이상부터 설정 가능합니다."
            ),
        ],
    )
    execution_time = TimeField(
        "투자 기준 시간",
        validators=[DataRequired(message="Execution time is required")],
    )
    param1 = IntegerField(
        "파라미터 1",
        validators=[DataRequired(message="파라미터 1을 입력해주세요.")],
    )
    stop_loss = IntegerField(
        "손절 기준 (%)",
        validators=[Optional()],
    )
    submit = SubmitField("전략 설정하기")

    def __init__(self, *args, strategy=None, **kwargs):
        super().__init__(*args, **kwargs)
        if strategy:
            # Populate currency choices with available coins in strategy
            self.currency.choices = [(coin.name, coin.name) for coin in strategy.coins]


class SetTwoParamUserStrategyForm(FlaskForm):
    currency = SelectField(
        "매매 종목 선택",
        choices=[],  # This will be populated dynamically
        validators=[DataRequired(message="매매 종목을 선택해주세요.")],
    )
    investing_limit = IntegerField(
        "전략 투자금 한도",
        validators=[
            DataRequired(),
            NumberRange(
                min=100000, message="투자금은 100,000원 이상부터 설정 가능합니다."
            ),
        ],
    )
    execution_time = TimeField(
        "투자 기준 시간",
        validators=[DataRequired(message="Execution time is required")],
    )
    param1 = IntegerField(
        "파라미터 1",
        validators=[DataRequired(message="파라미터 1을 입력해주세요.")],
    )
    param2 = IntegerField(
        "파라미터 2",
        validators=[DataRequired(message="파라미터 2를 입력해주세요.")],
    )
    stop_loss = IntegerField(
        "손절 기준 (%)",
        validators=[Optional()],
    )
    submit = SubmitField("전략 설정하기")

    def __init__(self, *args, strategy=None, **kwargs):
        super().__init__(*args, **kwargs)
        if strategy:
            # Populate currency choices with available coins in strategy
            self.currency.choices = [(coin.name, coin.name) for coin in strategy.coins]


class StartUserStrategyForm(FlaskForm):
    strategy_id = HiddenField("Strategy ID")
    choice = RadioField(
        "해당 전략을 통해 이미 코인을 보유중이신가요?",
        choices=[("현금 보유", "현금 보유 옵션"), ("코인 보유", "코인 보유 옵션")],
        validators=[DataRequired()],
        default="현금 보유",
    )
    coin_amount = FloatField("보유한 코인 수량", validators=[Optional()])
    submit = SubmitField("투자 시작하기")

    def __init__(self, *args, user_strategy=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Check if user_strategy is provided and has the expected structure
        if (
            user_strategy
            and hasattr(user_strategy, "target_currency")
            and hasattr(user_strategy.target_currency, "name")
        ):
            # Set the currency based on the user_strategy
            self.currency = user_strategy.target_currency.name
            # Update the label of coin_amount to include currency
            self.coin_amount.label.text = f"보유한 코인 수량 ({self.currency})"
        else:
            # For debugging: print a message if user_strategy or its attributes are missing
            print("user_strategy or target_currency.name not found in provided data.")


class EmptyForm(FlaskForm):
    submit = SubmitField("Submit")
