import sqlalchemy as sa
import sqlalchemy.orm as so
from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import db
from app.main import bp
from app.main.forms import EmptyForm, MakeStrategyForm
from app.models import Strategy, UserStrategy


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
    strategies = db.session.scalars(sa.select(Strategy)).all()
    form = EmptyForm()
    return render_template(
        "strategies.html", title="전략랭킹", strategies=strategies, form=EmptyForm()
    )


@bp.route("/make_strategy", methods=["GET", "POST"])
@login_required
def make_strategy():
    form = MakeStrategyForm()
    if form.validate_on_submit():
        strategy = Strategy(name=form.name.data, description=form.description.data)
        db.session.add(strategy)
        db.session.commit()
        return redirect(url_for("main.strategies"))
    return render_template("make_strategy.html", title="전략생성", form=form)


@bp.route("/to_my_strategies/<name>", methods=["POST"])
@login_required
def to_my_strategies(name):
    form = EmptyForm()
    if form.validate_on_submit():
        strategy = db.session.scalar(sa.select(Strategy).where(Strategy.name == name))

        if strategy is None:
            flash("해당 전략을 찾을 수 없습니다.")
            return redirect(url_for("main.strategies"))
        user_strategy = UserStrategy(user_id=current_user.id, strategy_id=strategy.id)
        db.session.add(user_strategy)
        db.session.commit()
        flash(f"{strategy.name} 전략이 내 전략에 포함되었습니다!")
        return redirect(url_for("main.strategies"))
    else:
        return redirect(url_for("main.index"))


@bp.route("/notice")
def notice():
    pass


@bp.route("/faq")
def faq():
    pass
