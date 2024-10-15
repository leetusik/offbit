from datetime import datetime, timezone

import redis
import sqlalchemy as sa
from celery import chain, shared_task
from flask import current_app

from app import create_app, db
from app.models import Strategy, UserStrategy

app = create_app()

with app.app_context():
    REDIS_URL = current_app.config["REDIS_URL"]
    redis_client = redis.StrictRedis.from_url(REDIS_URL)


@shared_task
def update_and_execute():
    update_strategies_historical_data()
    execute_strategies.delay()


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
