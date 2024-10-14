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
        choices=[("upbit", "Upbit"), ("bithumb", "Bithumb")],
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


class SetUserStrategyForm(FlaskForm):
    investing_limit = IntegerField("전략 투자금 한도", validators=[DataRequired()])
    execution_time = TimeField(
        "투자 기준 시간",
        # format="%H:%M:%S",  # This ensures input is in HH:MM:SS format
        validators=[DataRequired(message="Execution time is required")],
    )
    submit = SubmitField("Set Strategy")


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
