from datetime import datetime

import pytz

# import requests
import sqlalchemy as sa
from flask import flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, logout_user

from app import db
from app.models import Coin, Strategy, User, UserStrategy
from app.user import bp
from app.user.forms import (
    EmptyForm,
    SetAPIKeyForm,
    SetUserStrategyForm,
    StartUserStrategyForm,
    UserResetPasswordForm,
)
from app.utils.formatter import format_integer

# # Function to get the server's public IP address
# def get_public_ip():
#     try:
#         # This service returns the public IP address of the server
#         return requests.get("https://api.ipify.org").text
#     except requests.RequestException:
#         return None  # Handle failure to get the IP


@bp.route("/info")
@login_required
def user_info():
    form_e = EmptyForm()
    return render_template("user/info.html", user=current_user, form_e=form_e)


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
    server_ip = "61.73.154.79"
    if form.validate_on_submit():
        upbit_selected = form.platform.data == "upbit"
        if upbit_selected:
            api_key_access = form.api_key_access.data
            api_key_secret = form.api_key_secret.data
            expiration_date = form.expiration.data
            # Update the current user's API key and expiration date
            # Hash the access key for comparison
            access_key_hash = User.hash_api_key(api_key_access)

            # Check if the hashed API key is already in use by another account
            existing_user = db.session.scalar(
                sa.select(User).where(
                    (User.open_api_key_access_upbit_hash == access_key_hash)
                    & (User.id != current_user.id)  # Ensure it’s not the current user
                )
            )

            if existing_user:
                flash("이 API 키는 이미 다른 계정에서 사용 중입니다.", "danger")
                return redirect(url_for("user.set_api_key"))

            current_user.set_open_api_key(
                api_key_access=api_key_access,
                api_key_secret=api_key_secret,
                expiration_date=expiration_date,
            )
            try:
                upbit = current_user.create_upbit_client()
                balance = upbit.get_balances()

                # Check if there is an error in the balance response
                if isinstance(balance, dict) and "error" in balance:
                    error_name = balance["error"]["name"]
                    if error_name == "no_authorization_ip":
                        flash(
                            "API 연동에 실패했습니다. 서버 IP 주소를 업비트 화이트리스트에 등록해주세요.",
                            "danger",
                        )
                        db.session.rollback()
                        return redirect(
                            url_for("user.set_api_key")
                        )  # Redirect or handle as needed

                flash("API가 성공적으로 연동되었습니다.")
                # Save changes to the database
                db.session.commit()
                return redirect(url_for("user.user_info"))

            except:
                flash("API가 연동에 실패했습니다. 올바른 키 값을 입력해주세요.")
                db.session.rollback()
                return redirect(url_for("user.set_api_key"))
    return render_template("user/set_api_key.html", form=form, server_ip=server_ip)


@bp.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    # Get all strategies for the current user
    membership_dic = {"bike": "🚲", "motorcycle": "🛵", "car": "🚗", "airplane": "🛩️"}
    current_user.update_available()
    user_strategies = list(
        db.session.scalars(
            sa.select(UserStrategy).where(UserStrategy.user_id == current_user.id)
        )
    )

    forms = {}
    form_e = EmptyForm()
    # Iterate over each strategy and create a form for each one
    for user_strategy in user_strategies:
        form = StartUserStrategyForm(user_strategy=user_strategy)

        # Set the hidden field with the user strategy ID
        form.strategy_id.data = user_strategy.id
        # Process the form if it's submitted
        # if form.validate_on_submit() and form.strategy_id.data == user_strategy.id:
        if form.validate_on_submit() and form.strategy_id.data == int(
            request.form.get("strategy_id")
        ):
            if form.choice.data == "코인 보유":
                user_strategy.sell_needed = form.coin_amount.data
                user_strategy.holding_position = True
                db.session.commit()
            else:
                user_strategy.sell_needed = 0
                user_strategy.holding_position = False
                db.session.commit()
            try:
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
                else:
                    flash(
                        f"{user_strategy.strategy.name} 전략이 알 수 없는 오류로 활성화에 실패했습니다."
                    )
            except ValueError as e:
                # no money
                flash(str(e))

            return redirect(url_for("user.dashboard"))

        # Store the form associated with the strategy ID
        forms[user_strategy.id] = form
    return render_template(
        "user/dashboard.html",
        title="대시보드",
        user_strategies=user_strategies,
        forms=forms,
        form_e=form_e,
        format_integer=format_integer,
        membership_dic=membership_dic,
    )


@bp.route("/set_strategy/<name>", methods=["GET", "POST"])
@login_required
def set_strategy(name):
    user_strategy = db.first_or_404(
        sa.select(UserStrategy)
        .where(UserStrategy.strategy.has(name=name))
        .where(UserStrategy.user_id == current_user.id)
    )
    pre_data = {
        "currency": user_strategy.target_currency.name,
        "investing_limit": user_strategy.investing_limit,
        "execution_time": user_strategy.execution_time,
    }

    form = SetUserStrategyForm(data=pre_data, strategy=user_strategy.strategy)

    if form.validate_on_submit():
        investing_limit = form.investing_limit.data
        execution_time = form.execution_time.data
        target_currency = form.currency.data
        target_currency = db.session.scalar(
            sa.select(Coin).where(Coin.name == target_currency)
        )

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

        user_strategy.target_currency = target_currency
        user_strategy.investing_limit = investing_limit
        user_strategy.set_execution_time(str(utc_time.time()))

        flash(f"{user_strategy.strategy.name} 전략 투자 설정이 완료되었습니다.")
        return redirect(url_for("user.dashboard"))
    return render_template(
        "user/set_strategy.html",
        title="전략별 투자 설정",
        form=form,
    )


@bp.route("/remove_from_strategies/<name>", methods=["POST"])
@login_required
def remove_from_strategies(name):
    form = EmptyForm()
    if form.validate_on_submit():
        strategy = db.session.scalar(sa.select(Strategy).where(Strategy.name == name))

        if strategy is None:
            flash("해당 전략을 찾을 수 없습니다.")
            return redirect(url_for("main.strategies"))

        user_strategy = db.session.scalar(
            sa.select(UserStrategy)
            .where(UserStrategy.user_id == current_user.id)
            .where(UserStrategy.strategy_id == strategy.id)
        )
        db.session.delete(user_strategy)
        db.session.commit()
        flash(f"{strategy.name} 전략이 내 전략에서 삭제되었습니다.")
        return redirect(url_for("user.dashboard"))
    else:
        return redirect(url_for("main.index"))


@bp.route("/no_setting_no_start", methods=["POST"])
def no_setting_no_start():
    if current_user.open_api_key_access_upbit == None:
        flash("투자를 시작하기 위해 오픈 API 키를 연동해주세요.")
        return redirect(url_for("user.user_info"))
    flash("투자를 시작하기 위해서 투자 세팅을 완료해주세요.")
    return redirect(url_for("user.dashboard"))


@bp.route("/deactivate_user_strategy/<user_strategy_id>", methods=["POST"])
def deactivate_user_strategy(user_strategy_id):
    user_strategy = db.session.scalar(
        sa.select(UserStrategy).where(UserStrategy.id == user_strategy_id)
    )
    if not user_strategy:
        flash("해당 전략을 찾지 못했습니다.")
        return redirect("user.dashboard")

    user_strategy.deactivate()
    flash(f"{user_strategy.strategy.name} 전략을 성공적으로 중지했습니다.")
    return redirect(url_for("user.dashboard"))


@bp.route("/no_setting_while_investing", methods=["POST"])
def no_setting_while_investing():
    flash(
        "투자 중에는 투자 설정을 변경할 수 없어요. 먼저 투자를 중지한 후에 설정을 변경해주세요."
    )
    return redirect(url_for("user.dashboard"))


@bp.route("/set_timezone", methods=["POST"])
def set_timezone():
    data = request.get_json()
    timezone = data.get("timezone")
    # Store the timezone in the session or the current user object
    session["timezone"] = timezone
    return "", 204  # Empty response with HTTP status 204 (No Content)


@bp.route("/unset_api_key", methods=["POST"])
@login_required
def unset_api_key():

    # Check if the current user has any active strategies
    active_strategies = db.session.scalars(
        sa.select(UserStrategy).where(
            UserStrategy.user_id == current_user.id, UserStrategy.active.is_(True)
        )
    ).all()

    if active_strategies:
        flash(
            "활성화된 전략이 있습니다. API 키를 해제하기 전에 모든 전략을 비활성화하세요.",
            "danger",
        )
        return redirect(url_for("user.user_info"))
    # Unset the API key fields for the current user
    current_user.open_api_key_access_upbit = None
    current_user.open_api_key_secret_upbit = None
    current_user.api_key_expiration_upbit = None

    # Save changes to the database
    db.session.commit()

    flash("API 연동이 성공적으로 해제되었습니다.", "success")
    return redirect(url_for("user.user_info"))
