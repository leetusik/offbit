from datetime import datetime, timezone

import redis
import sqlalchemy as sa
import sqlalchemy.orm as so
from flask import current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app import db
from app.main import bp
from app.main.forms import EmptyForm, MakeStrategyForm
from app.models import Strategy, UserStrategy
from config import Config

# app = create_app()

# with current_app.app_context():
REDIS_URL = Config.REDIS_URL
redis_client = redis.StrictRedis.from_url(REDIS_URL)


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
    performance_data = {}
    for strategy in strategies:
        # Fetch performance metrics from Redis
        performance_24h = redis_client.hget(
            f"strategy:{strategy.id}:performance", "24h"
        )
        performance_30d = redis_client.hget(
            f"strategy:{strategy.id}:performance", "30d"
        )
        performance_1y = redis_client.hget(f"strategy:{strategy.id}:performance", "1y")

        last_update_str = redis_client.hget("strategy performance check", "last_update")

        if last_update_str:
            last_update_str = last_update_str.decode()
            last_update_datetime = datetime.strptime(
                last_update_str, "%Y-%m-%d %H:%M:%S"
            )
            last_update_datetime = last_update_datetime.replace(tzinfo=timezone.utc)

        performance_data[strategy.id] = {
            "name": strategy.name,
            "last_update": last_update_datetime if last_update_str else "N/A",
            "24h": performance_24h.decode() if performance_24h else "N/A",
            "30d": performance_30d.decode() if performance_30d else "N/A",
            "1y": performance_1y.decode() if performance_1y else "N/A",
        }

    form = EmptyForm()

    return render_template(
        "strategies.html",
        title="전략랭킹",
        strategies=strategies,
        form=form,
        performance_data=performance_data,
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
        return redirect(url_for("main.strategies"))
    else:
        return redirect(url_for("main.index"))


@bp.route("/notice")
def notice():
    pass


@bp.route("/faq")
def faq():
    pass
