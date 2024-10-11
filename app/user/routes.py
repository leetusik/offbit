import sqlalchemy as sa
from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required, logout_user

from app import db
from app.models import User, UserStrategy
from app.user import bp
from app.user.forms import SetAPIKeyForm, SetUserStrategyForm, UserResetPasswordForm

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
    form = SetAPIKey()
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


@bp.route("/dashboard")
@login_required
def dashboard():
    user_strategies = db.session.scalars(
        sa.select(UserStrategy).where(UserStrategy.user_id == current_user.id)
    )
    return render_template(
        "user/dashboard.html",
        title="대시보드",
        user_strategies=user_strategies,
    )


@bp.route("/set_strategy/<name>", methods=["GET", "POST"])
@login_required
def set_strategy(name):
    user_strategy = db.first_or_404(
        sa.select(UserStrategy).where(UserStrategy.strategy.has(name=name))
    )
    form = SetUserStrategyForm()
    if form.validate_on_submit():
        investing_limit = form.investing_limit.data
        execution_time = str(form.execution_time.data)
        # print(execution_time)
        user_strategy.investing_limit = investing_limit
        user_strategy.set_execution_time(execution_time)
        flash(f"{user_strategy.strategy.name} 전략 투자 설정이 완료되었습니다.")
        return redirect(url_for("user.dashboard"))
    return render_template(
        "user/set_strategy.html",
        title="전략별 투자 설정",
        form=form,
    )
