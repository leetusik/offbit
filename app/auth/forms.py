import sqlalchemy as sa
from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField, SubmitField
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    Regexp,
    ValidationError,
)

from app import db
from app.models import User


class LoginForm(FlaskForm):
    email = StringField("이메일", validators=[DataRequired(), Email()])
    password = PasswordField("비밀번호", validators=[DataRequired()])
    remember_me = BooleanField("로그인 유지하기")
    submit = SubmitField("로그인")


class RegistrationForm(FlaskForm):
    email = StringField("이메일", validators=[DataRequired(), Email()])
    username = StringField(("이름"), validators=[DataRequired()])
    # password = PasswordField(
    #     "비밀번호",
    #     validators=[
    #         DataRequired(),
    #         Length(min=8, message="비밀번호는 8자리 이상이어야 합니다"),
    #         Regexp(
    #             r"^(?=.*[A-Z])",
    #             message="비밀번호는 하나 이상의 대문자를 포함해야 합니다",
    #         ),
    #         Regexp(
    #             r"^(?=.*[a-z])",
    #             message="비밀번호는 하나 이상의 소문자를 포함해야 합니다",
    #         ),
    #         Regexp(r"^(?=.*\d)", message="비밀번호는 하나 이상의 숫자를 포함해야 합니다"),
    #         # Allow any non-alphanumeric character as a special character
    #         Regexp(
    #             r"^(?=.*[\W_])",
    #             message="비밀번호는 하나 이상의 특수문자를 포함해야 합니다",
    #         ),
    #     ],
    # )
    password = PasswordField(("비밀번호"), validators=[DataRequired()])
    confirm_password = PasswordField(
        "비밀번호 확인",
        validators=[
            DataRequired(),
            EqualTo("password", message="비밀번호가 일치하지 않습니다"),
        ],
    )
    submit = SubmitField("등록하기")

    def validate_email(self, email):
        user = db.session.scalar(sa.select(User).where(User.email == email.data))
        if user is not None:
            raise ValidationError("다른 이메일 주소를 사용해주세요")
