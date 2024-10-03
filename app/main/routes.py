from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import db
from app.main import bp


@bp.route("/")
@bp.route("/index")
def index():
    return render_template(
        "index.html",
    )


@bp.route("/explain")
def explain():
    pass


@bp.route("/strategies")
def strategies():
    pass


@bp.route("/notice")
def notice():
    pass


@bp.route("/faq")
def faq():
    pass


@bp.route("/user")
def user():
    pass
