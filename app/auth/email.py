from flask import current_app, render_template

from app.email import send_email


def send_password_reset_email(user):
    user.set_verification_code()
    send_email(
        "[Offbit] 비밀번호 변경하기",
        sender=current_app.config["ADMINS"][0],
        recipients=[user.email],
        text_body=render_template(
            "email/reset_password.txt",
            user=user,
        ),
        html_body=render_template(
            "email/reset_password.html",
            user=user,
        ),
    )
