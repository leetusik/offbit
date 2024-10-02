from flask import redirect, render_template, url_for

from app.auth import bp


@bp.route("/login", methods=["GET", "POST"])
def login():
    pass


@bp.route("/logout")
def logout():
    # logout_user()
    return redirect(url_for("main.index"))
