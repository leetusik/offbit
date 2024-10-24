from datetime import datetime, timedelta, timezone

import redis
import sqlalchemy as sa
from celery import shared_task
from flask import current_app

from app import create_app, db
from app.models import Strategy, UserStrategy
from app.utils.performance_utils import calculate_performance

app = create_app()

with app.app_context():
    REDIS_URL = current_app.config["REDIS_URL"]
    redis_client = redis.StrictRedis.from_url(REDIS_URL)


@shared_task
def update_strategies_performance():
    strategies = db.session.scalars(sa.select(Strategy)).all()

    for strategy in strategies:
        (
            performance_24h,
            performance_30d,
            performance_1y,
            benchmark_24h,
            benchmark_30d,
            benchmark_1y,
        ) = calculate_performance(strategy=strategy, time_period=timedelta(days=381))
        last_update = str(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
        redis_client.hset(f"strategy performance check", "last_update", last_update)
        redis_client.hset(f"strategy:{strategy.id}:performance", "24h", performance_24h)
        redis_client.hset(f"strategy:{strategy.id}:performance", "30d", performance_30d)
        redis_client.hset(f"strategy:{strategy.id}:performance", "1y", performance_1y)
        redis_client.hset(f"benchmark:1:performance", "24h", benchmark_24h)
        redis_client.hset(f"benchmark:1:performance", "30d", benchmark_30d)
        redis_client.hset(f"benchmark:1:performance", "1y", benchmark_1y)

    # print(f"Performance metrics updated for strategy {strategy.name}")


@shared_task
def update_and_execute():
    # Set a unique lock name for the task
    lock = redis_client.lock("update_and_execute", timeout=3600)  # Lock for 1 hour
    have_lock = lock.acquire(blocking=False)

    if not have_lock:
        # If another worker is running this task, exit the function
        print("Another instance of update_and_execute is already running.")
        return
    try:
        update_strategies_historical_data()
        execute_strategies.delay()

        current = datetime.now()
        if current.minute == 0:
            update_strategies_performance.delay()
    finally:
        # Ensure the lock is released when the task is done
        lock.release()


@shared_task
def execute_user_strategy(user_strategy_id):
    print("task execute_user_strategy executed.")
    user_strategy = db.session.get(UserStrategy, user_strategy_id)
    if user_strategy and user_strategy.active:
        user_strategy.execute()
        db.session.commit()


@shared_task
def execute_strategies():
    """Launch a Celery task for each user's strategy that needs to be executed."""
    print("task execute_strategies executed.")

    now = datetime.now(timezone.utc).replace(microsecond=0, second=0, tzinfo=None)

    # Query active UserStrategies that match the current execution time (HH:MM:SS)
    user_strategies = db.session.scalars(
        sa.select(UserStrategy)
        .where(UserStrategy.active == True)
        .where(UserStrategy.execution_time == now.time())
        # .where(UserStrategy.execution_time != None)
        # .where(sa.func.time(UserStrategy.execution_time) == now.time())
    ).all()
    # print(now.time())

    # Launch a separate task for each UserStrategy
    for user_strategy in user_strategies:
        execute_user_strategy.delay(
            user_strategy_id=user_strategy.id
        )  # Launch each task concurrently

        # Log the execution
    current_app.logger.info(
        f"Scheduled {len(user_strategies)} strategies to execute at {now}."
    )


# need to handle speed. it would slow down as make strategies
@shared_task()
def update_strategies_historical_data():
    print("task update_strategies_historical_data executed.")
    # Set a unique lock name for the task
    lock = redis_client.lock("update_strategies_lock", timeout=3600)  # Lock for 1 hour
    have_lock = lock.acquire(blocking=False)

    if not have_lock:
        # If another worker is running this task, exit the function
        print(
            "Another instance of update_strategies_historical_data is already running."
        )
        return
    try:
        strategies = db.session.scalars(sa.select(Strategy)).all()
        for strategy in strategies:
            # can't do seperate and delay bcs there are limit on the api call.
            strategy.make_historical_data()
    finally:
        # Ensure the lock is released when the task is done
        lock.release()


@shared_task
def dummy_function(a, b):
    print(a)
    print(b)
    print(f"{a} + {b} = {a+b}")
    # return None
