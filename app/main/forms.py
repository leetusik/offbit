# import sqlalchemy as sa
import sqlalchemy as sa
from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField, SubmitField, TimeField
from wtforms.validators import DataRequired, Optional, ValidationError
from wtforms_sqlalchemy.fields import QuerySelectMultipleField

from app import db
from app.models import Coin, Strategy, User


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
    base_execution_time = TimeField(
        "기본 투자 시간",
        validators=[DataRequired(message="기본 투자 시간을 입력해 주세요.")],
    )
    base_param1 = IntegerField(
        "기본 파라미터 1",
        validators=[DataRequired(message="기본 파라미터 1을 입력해 주세요.")],
    )
    base_param2 = IntegerField(
        "기본 파라미터 2",
        validators=[Optional()],
        filters=[lambda x: x or None],  # Convert empty string to None
    )
    # Multi-select field for coins
    coins = QuerySelectMultipleField(
        "적용 가능 코인",
        query_factory=lambda: db.session.scalars(
            sa.select(Coin)
        ).all(),  # Populate with available coins
        # query_factory=lambda: db.session.query(
        #     Coin
        # ).all(),  # Populate with available coins
        get_label="name",  # Assume Coin model has a `name` attribute
        allow_blank=False,
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

    def validate_base_param1(self, base_param1):
        if base_param1.data <= 0:
            raise ValidationError("기본 파라미터 1은 0보다 커야 합니다.")


class SetBacktestOneParamForm(FlaskForm):
    execution_time = TimeField(
        "투자 기준 시간",
        validators=[DataRequired(message="Execution time is required")],
    )
    param1 = IntegerField(
        "파라미터 1", validators=[DataRequired(message="파라미터 1을 입력해 주세요.")]
    )
    stop_loss = IntegerField(
        "손절 퍼센트", validators=[Optional()], filters=[lambda x: x or None]
    )
    submit = SubmitField("확인")

    def validate_param1(self, param1):
        if param1.data <= 0:
            raise ValidationError("파라미터 1은 0보다 커야 합니다.")

    def validate_stop_loss(self, stop_loss):
        if stop_loss.data and stop_loss.data <= 0:
            raise ValidationError("손절 퍼센트는 0보다 커야 합니다.")


class SetBacktestTwoParamsForm(FlaskForm):
    execution_time = TimeField(
        "투자 기준 시간",
        validators=[DataRequired(message="Execution time is required")],
    )
    param1 = IntegerField(
        "파라미터 1", validators=[DataRequired(message="파라미터 1을 입력해 주세요.")]
    )
    param2 = IntegerField(
        "파라미터 2", validators=[DataRequired(message="파라미터 2를 입력해 주세요.")]
    )
    stop_loss = IntegerField(
        "손절 퍼센트", validators=[Optional()], filters=[lambda x: x or None]
    )
    submit = SubmitField("확인")

    def validate_param2(self, param2):
        if param2.data <= self.param1.data:
            raise ValidationError("파라미터 2는 파라미터 1보다 커야 합니다.")

    def validate_param1(self, param1):
        if param1.data <= 0:
            raise ValidationError("파라미터 1은 0보다 커야 합니다.")

    def validate_param2(self, param2):
        if param2.data <= 0:
            raise ValidationError("파라미터 2는 0보다 커야 합니다.")
        if param2.data <= self.param1.data:
            raise ValidationError("파라미터 2는 파라미터 1보다 커야 합니다.")

    def validate_stop_loss(self, stop_loss):
        if stop_loss.data and stop_loss.data <= 0:
            raise ValidationError("손절 퍼센트는 0보다 커야 합니다.")


class EmptyForm(FlaskForm):
    submit = SubmitField("Submit")
