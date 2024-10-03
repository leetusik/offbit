from datetime import datetime, timezone
from urllib.parse import urlsplit

import sqlalchemy as sa
from flask import flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_user, logout_user

from app import db
from app.auth import bp
from app.auth.email import send_password_reset_email
from app.auth.forms import (
    LoginForm,
    RegistrationForm,
    ResetPasswordForm,
    ResetPasswordRequestForm,
    VerificationCodeForm,
)
from app.models import User


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(User).where(User.email == form.email.data))
        if user is None or not user.check_password(form.password.data):
            flash("유효하지 않은 이메일 혹은 비밀번호 입니다")
            return redirect(url_for("auth.login"))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get("next")
        if not next_page or urlsplit(next_page).netloc != "":
            next_page = url_for("main.index")
        return redirect(next_page)
    return render_template("auth/login.html", title="로그인", form=form)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("축하합니다, 가입에 성공했습니다!")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html", title="가입하기", form=form)


@bp.route("/reset_password_request", methods=["GET", "POST"])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(User).where(User.email == form.email.data))
        if user:
            send_password_reset_email(user)
        flash("비밀번호 변경을 위한 이메일이 발송되었습니다.")
        return redirect(url_for("auth.reset_password", email=user.email))
    return render_template(
        "auth/reset_password_request.html", title="비밀번호 변경", form=form
    )


# 무지성 삽입 공격 대응 해야함
# 보안코드시간 만료 다시 보내기 구현
@bp.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    email = request.args.get("email")
    if not email:
        flash("잘못된 접근입니다.")
        return redirect(url_for("auth.reset_password_request"))

    user = db.session.scalar(sa.select(User).where(User.email == email))
    if not user:
        flash("사용자를 찾을 수 없습니다.")
        return redirect(url_for("auth.reset_password_request"))

    # Ensure that verification_code_expiration is timezone-aware
    if (
        user.verification_code_expiration
        and user.verification_code_expiration.tzinfo is None
    ):
        # If the datetime is naive, make it UTC-aware
        user.verification_code_expiration = user.verification_code_expiration.replace(
            tzinfo=timezone.utc
        )

    # Check if the code has been verified by checking session
    code_verified = session.get("code_verified", False)

    # Initialize forms
    code_form = VerificationCodeForm()
    reset_form = ResetPasswordForm() if code_verified else None

    # If reset_form is being submitted
    if reset_form and reset_form.validate_on_submit():
        user.set_password(reset_form.password.data)
        db.session.commit()
        flash("비밀번호가 성공적으로 변경되었습니다.", "success")
        # Clear the session
        session.pop("code_verified", None)
        return redirect(url_for("auth.login"))

    # If code_form is being submitted
    if not code_verified and code_form.validate_on_submit():
        if code_form.code.data == str(user.verification_code):
            # Mark code as verified in session
            if (
                user.verification_code_expiration
                and user.verification_code_expiration > datetime.now(timezone.utc)
            ):
                # Store code verification status in the session.
                session["code_verified"] = True
                flash("보안코드가 확인되었습니다. 비밀번호를 변경해주세요.", "success")
                return redirect(
                    url_for("auth.reset_password", email=email)
                )  # Redirect to show the reset form
            else:
                flash(
                    "보안코드가 만료되었습니다. 다시 요청해주세요.", "danger"
                )  # Code is expired
        else:
            flash("보안코드가 일치하지 않습니다.", "danger")

    return render_template(
        "auth/reset_password.html",
        title="비밀번호 변경",
        code_form=code_form if not code_verified else None,
        reset_form=reset_form,
    )


@bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("main.index"))
