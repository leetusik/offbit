from datetime import datetime, timedelta, timezone

import pandas as pd
import pytz
import redis
import sqlalchemy as sa
import sqlalchemy.orm as so
from flask import (
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required

from app import db
from app.main import bp
from app.main.forms import (
    EmptyForm,
    MakeStrategyForm,
    SetBacktestOneParamForm,
    SetBacktestTwoParamsForm,
)
from app.models import Coin, Strategy, UserStrategy
from app.utils.performance_utils import get_backtest, get_performance


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

    coins = db.session.scalars(sa.select(Coin)).all()
    coin_performance_data = {}
    REDIS_URL = current_app.config["REDIS_URL"]
    redis_client = redis.StrictRedis.from_url(REDIS_URL)

    for coin in coins:
        # Fetch performance metrics from Redis
        performance_24h = redis_client.hget(f"coin:{coin.id}:performance", "24h")
        performance_30d = redis_client.hget(f"coin:{coin.id}:performance", "30d")
        performance_1y = redis_client.hget(f"coin:{coin.id}:performance", "1y")

        last_update_str = redis_client.hget(f"coin:{coin.id}:update", "last_update")

        if last_update_str:
            last_update_str = last_update_str.decode()
            last_update_datetime = datetime.strptime(
                last_update_str, "%Y-%m-%d %H:%M:%S"
            )
            last_update_datetime = last_update_datetime.replace(tzinfo=timezone.utc)

        coin_performance_data[coin.id] = {
            "name": coin.name,
            "last_update": last_update_datetime if last_update_str else "N/A",
            "24h": (
                f"{float(performance_24h.decode()):.2f}" if performance_24h else "N/A"
            ),
            "30d": (
                f"{float(performance_30d.decode()):.2f}" if performance_30d else "N/A"
            ),
            "1y": f"{float(performance_1y.decode()):.2f}" if performance_1y else "N/A",
        }

    strategies = db.session.scalars(sa.select(Strategy)).all()
    strategy_performance_data = {}
    for strategy in strategies:
        # Fetch performance metrics from Redis
        performance_24h = redis_client.hget(
            f"strategy:{strategy.id}:performance", "24h"
        )
        performance_30d = redis_client.hget(
            f"strategy:{strategy.id}:performance", "30d"
        )
        performance_1y = redis_client.hget(f"strategy:{strategy.id}:performance", "1y")

        last_update_str = redis_client.hget(
            f"strategy:{strategy.id}:update", "last_update"
        )

        if last_update_str:
            last_update_str = last_update_str.decode()
            last_update_datetime = datetime.strptime(
                last_update_str, "%Y-%m-%d %H:%M:%S"
            )
            last_update_datetime = last_update_datetime.replace(tzinfo=timezone.utc)

        strategy_performance_data[strategy.id] = {
            "name": strategy.name,
            "last_update": last_update_datetime if last_update_str else "N/A",
            "24h": (
                f"{float(performance_24h.decode()):.2f}" if performance_24h else "N/A"
            ),
            "30d": (
                f"{float(performance_30d.decode()):.2f}" if performance_30d else "N/A"
            ),
            "1y": f"{float(performance_1y.decode()):.2f}" if performance_1y else "N/A",
        }
        # print(strategy.id)
        # print(type(float(strategy_performance_data[strategy.id]["24h"])))

    form = EmptyForm()

    return render_template(
        "strategies.html",
        title="전략랭킹",
        strategies=strategies,
        form=form,
        strategy_performance_data=strategy_performance_data,
        coin_performance_data=coin_performance_data,
        coins=coins,
    )


@bp.route("/strategy/<strategy_id>", methods=["GET", "POST"])
def strategy(strategy_id):

    strategy = db.first_or_404(sa.select(Strategy).where(Strategy.id == strategy_id))

    # Retrieve the strategy object from the database
    # execution_time = session.get("execution_time", strategy.base_execution_time)
    # param1 = session.get("param1", strategy.base_param1)
    # param2 = session.get("param2", strategy.base_param2)
    execution_time = (
        datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0).time()
    )
    param1 = strategy.base_param1
    param2 = strategy.base_param2
    stop_loss = session.get("stop_loss", None)

    if execution_time:
        # Convert to a datetime.time object
        execution_time = datetime.strptime(str(execution_time), "%H:%M:%S").time()
    if param1:
        param1 = int(param1)
    if param2:
        param2 = int(param2)

    pre_data = {
        "execution_time": execution_time,
        "param1": param1,
        "param2": param2,
        "stop_loss": stop_loss,
    }

    if strategy.base_param2:
        form = SetBacktestTwoParamsForm(data=pre_data)
    else:
        form = SetBacktestOneParamForm(data=pre_data)

    # get selected_coin
    selected_coin = request.args.get("coin")  # No need for a default value here
    sorted_coins = sorted(strategy.coins, key=lambda coin: coin.id)
    # Check if the selected coin is provided or if it's not in the strategy's coins
    if selected_coin is None:
        selected_coin = sorted_coins[0].name  # Set to the first coin if not provided
    elif selected_coin not in [coin.name for coin in sorted_coins]:
        abort(404)  # Abort if the selected coin is not in the strategy's coins

    # If the form is submitted and valid, pass the execution time as an argument
    if form.validate_on_submit():
        execution_time = form.execution_time.data
        param1 = form.param1.data
        stop_loss = form.stop_loss.data
        if strategy.base_param2:
            param2 = form.param2.data
            session["param2"] = str(
                form.param2.data
            )  # Convert int to string for session storage
        if stop_loss:
            session["stop_loss"] = str(stop_loss)

        session["execution_time"] = str(form.execution_time.data)
        session["param1"] = str(form.param1.data)

        # change execution_time to utc #
        user_timezone = session.get("timezone", "UTC")
        user_timezone = pytz.timezone(user_timezone)
        # Create a datetime object for today with the given time
        local_datetime = datetime.combine(datetime.today(), execution_time)

        # Localize the time to the given timezone
        localized_time = user_timezone.localize(local_datetime)
        # Convert to UTC
        utc_time = localized_time.astimezone(pytz.utc)
        df = get_backtest(
            strategy=strategy,
            selected_coin=selected_coin,
            param1=param1,
            param2=param2,
            stop_loss=stop_loss,
            execution_time=datetime(1970, 1, 1, utc_time.hour, utc_time.minute),
        )

    else:
        execution_time = form.execution_time.data
        param1 = form.param1.data
        if strategy.base_param2:
            param2 = form.param2.data
        else:
            param2 = None
        stop_loss = form.stop_loss.data

        user_timezone = session.get("timezone", "UTC")
        user_timezone = pytz.timezone(user_timezone)
        # Create a datetime object for today with the given time
        local_datetime = datetime.combine(datetime.today(), execution_time)

        # Localize the time to the given timezone
        localized_time = user_timezone.localize(local_datetime)
        # Convert to UTC
        utc_time = localized_time.astimezone(pytz.utc)
        df = get_backtest(
            strategy=strategy,
            selected_coin=selected_coin,
            param1=param1,
            param2=param2,
            stop_loss=stop_loss,
            execution_time=datetime(1970, 1, 1, utc_time.hour, utc_time.minute),
        )

    # Convert the time_utc column from string to datetime (assumed to be in UTC)
    df["time_utc"] = pd.to_datetime(df["time_utc"], utc=True)  # Ensure it's tz-aware

    # Handle time range selection before localizing the time to the user's timezone
    time_range = request.args.get(
        "range", "all"
    )  # Get the time range from the URL, default to 'all'

    # Get current UTC time for range filtering
    now_utc = datetime.now(pytz.UTC)

    if time_range == "30d":
        start_date = now_utc - timedelta(days=30)
        df = df[df["time_utc"] >= start_date]
    elif time_range == "1y":
        start_date = now_utc - timedelta(days=365)
        df = df[df["time_utc"] >= start_date]
    # No need for an "all" case, as that's the default behavior

    # Localize the time to UTC first (as your times are in UTC), then convert to the user's local timezone
    user_timezone = pytz.timezone(session.get("timezone", "UTC"))
    df["time_localized"] = df["time_utc"].dt.tz_convert(user_timezone)

    # Format the localized time back to ISO 8601 format for Chart.js
    times = df["time_localized"].dt.strftime("%Y-%m-%dT%H:%M:%S").tolist()

    cumulative_returns2 = df[
        "cumulative_returns2"
    ].tolist()  # Convert cumulative returns to list
    close_prices = df["close"].tolist()  # Convert close prices to list

    # Remove the first data point if necessary (as in your example)
    times = times[1:]
    cumulative_returns2 = cumulative_returns2[1:]
    close_prices = close_prices[1:]
    # Normalize both datasets to start from 100
    start_value = 100
    close_prices_normalized = [
        price / close_prices[0] * start_value for price in close_prices
    ]
    cumulative_returns2_normalized = [
        ret / cumulative_returns2[0] * start_value for ret in cumulative_returns2
    ]
    performance_dict = get_performance(df)
    # Pass data to the template

    return render_template(
        "strategy.html",
        strategy=strategy,
        sorted_coins=sorted_coins,
        times=times,
        cumulative_returns2_normalized=cumulative_returns2_normalized,
        close_prices_normalized=close_prices_normalized,
        form=form,
        performance_dict=performance_dict,
    )


@bp.route("/make_strategy", methods=["GET", "POST"])
@login_required
def make_strategy():
    form = MakeStrategyForm()
    if form.validate_on_submit():
        name = form.name.data
        description = form.description.data
        base_execution_time = form.base_execution_time.data
        base_param1 = form.base_param1.data
        base_param2 = form.base_param2.data
        strategy = Strategy(
            name=name,
            description=description,
            base_execution_time=base_execution_time,
            base_param1=base_param1,
            base_param2=base_param2,
        )
        coins = form.coins.data
        for coin in coins:
            strategy.coins.append(coin)
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


@bp.route("/set_timezone", methods=["POST"])
def set_timezone():
    data = request.get_json()
    timezone = data.get("timezone")
    # Store the timezone in the session or the current user object
    session["timezone"] = timezone
    return "", 204  # Empty response with HTTP status 204 (No Content)
