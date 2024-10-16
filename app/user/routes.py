from datetime import datetime

import pytz
import sqlalchemy as sa
from flask import flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, logout_user

from app import db
from app.models import User, UserStrategy
from app.user import bp
from app.user.forms import (
    SetAPIKeyForm,
    SetUserStrategyForm,
    StartUserStrategyForm,
    UserResetPasswordForm,
)

# from app.user.forms import


@bp.route("/info")
@login_required
def user_info():
    return render_template("user/info.html", user=current_user)


@bp.route("/reset_password", methods=["GET", "POST"])
@login_required
def user_reset_password():
    form = UserResetPasswordForm()
    if form.validate_on_submit():
        current_user.set_password(form.password.data)
        db.session.commit()
        logout_user()
        flash("비밀번호가 성공적으로 변경되었습니다! 다시 로그인해주세요.")
        return redirect(url_for("auth.login"))

    return render_template("user/reset_password.html", form=form)


@bp.route("/set_api_key", methods=["GET", "POST"])
@login_required
def set_api_key():
    form = SetAPIKeyForm()
    if form.validate_on_submit():
        upbit_selected = form.platform.data == "upbit"
        if upbit_selected:
            api_key_access = form.api_key_access.data
            api_key_secret = form.api_key_secret.data
            expiration_date = form.expiration.data
            # Update the current user's API key and expiration date
            current_user.set_open_api_key(
                api_key_access=api_key_access,
                api_key_secret=api_key_secret,
                expiration_date=expiration_date,
            )

            # Save changes to the database
            db.session.commit()

            flash("API가 성공적으로 연동되었습니다.")
        return redirect(url_for("user.user_info"))
    return render_template("user/set_api_key.html", form=form)


@bp.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    # Get all strategies for the current user
    user_strategies = list(
        db.session.scalars(
            sa.select(UserStrategy).where(UserStrategy.user_id == current_user.id)
        )
    )

    forms = {}

    # Iterate over each strategy and create a form for each one
    for user_strategy in user_strategies:
        form = StartUserStrategyForm()

        # Set the hidden field with the user strategy ID
        form.strategy_id.data = user_strategy.id
        # Process the form if it's submitted
        if form.validate_on_submit() and form.strategy_id.data == user_strategy.id:
            if form.choice.data == "코인 보유":
                user_strategy.sell_needed = form.coin_amount.data
                user_strategy.holding_position = True
                db.session.commit()

            status, message = (
                user_strategy.activate()
            )  # Activate strategy after selling is set
            if status:
                flash(
                    f"{user_strategy.strategy.name} 전략이 성공적으로 활성화 되었습니다."
                )
            elif message == "no data":
                flash(
                    f"{user_strategy.strategy.name} 전략의 데이터가 아직 준비되지 않았어요. 잠시 후에 다시 시도해주세요."
                )
            elif message == "no money":
                flash(
                    f"{user_strategy.strategy.name} 전략을 실행하기 위한 전략 투자금이 현재 투자 가능한 잔액보다 높아요."
                )
            else:
                flash(
                    f"{user_strategy.strategy.name} 전략이 알 수 없는 오류로 활성화에 실패했습니다."
                )

            return redirect(url_for("user.dashboard"))

        # Store the form associated with the strategy ID
        forms[user_strategy.id] = form

    return render_template(
        "user/dashboard.html",
        title="대시보드",
        user_strategies=user_strategies,
        forms=forms,
    )


@bp.route("/set_strategy/<name>", methods=["GET", "POST"])
@login_required
def set_strategy(name):
    user_strategy = db.first_or_404(
        sa.select(UserStrategy).where(UserStrategy.strategy.has(name=name))
    )
    pre_data = {
        "investing_limit": user_strategy.investing_limit,
        "execution_time": user_strategy.execution_time,
    }

    form = SetUserStrategyForm(data=pre_data)

    if form.validate_on_submit():
        investing_limit = form.investing_limit.data
        execution_time = form.execution_time.data

        # change execution_time to utc #
        user_timezone = session.get("timezone", "UTC")
        user_timezone = pytz.timezone(user_timezone)
        # Create a datetime object for today with the given time
        local_datetime = datetime.combine(datetime.today(), execution_time)

        # Localize the time to the given timezone
        localized_time = user_timezone.localize(local_datetime)
        # Convert to UTC
        utc_time = localized_time.astimezone(pytz.utc)
        # change execution_time to utc #

        user_strategy.investing_limit = investing_limit
        user_strategy.set_execution_time(str(utc_time.time()))
        flash(f"{user_strategy.strategy.name} 전략 투자 설정이 완료되었습니다.")
        return redirect(url_for("user.dashboard"))
    return render_template(
        "user/set_strategy.html",
        title="전략별 투자 설정",
        form=form,
    )


@bp.route("/set_timezone", methods=["POST"])
@login_required
def set_timezone():
    data = request.get_json()
    timezone = data.get("timezone")

    # Store the timezone in the session or the current user object
    session["timezone"] = timezone

    return "", 204  # Empty response with HTTP status 204 (No Content)
