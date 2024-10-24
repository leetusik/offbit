# import sqlalchemy as sa
import sqlalchemy as sa
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TimeField
from wtforms.validators import DataRequired, ValidationError

from app import db
from app.models import Strategy, User


class MakeStrategyForm(FlaskForm):
    name = StringField(
        "이름",
        validators=[
            DataRequired(message="전략 이름을 입력해 주세요."),
        ],
    )
    description = StringField(
        "설명", validators=[DataRequired(message="전략 설명을 입력해 주세요.")]
    )
    submit = SubmitField("생성하기")

    def validate_name(self, name):
        """Custom validator to ensure the strategy name is unique."""
        strategy = db.session.scalar(
            sa.select(Strategy).where(Strategy.name == name.data)
        )
        if strategy:
            raise ValidationError(
                "이미 존재하는 전략 이름입니다. 다른 이름을 입력해 주세요."
            )


class SetBacktestExecutionTimeForm(FlaskForm):

    execution_time = TimeField(
        "투자 기준 시간",
        # format="%H:%M:%S",  # This ensures input is in HH:MM:SS format
        validators=[DataRequired(message="Execution time is required")],
    )
    submit = SubmitField("확인")


class EmptyForm(FlaskForm):
    submit = SubmitField("Submit")
