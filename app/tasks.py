from datetime import datetime, timezone

import redis
import sqlalchemy as sa
from celery import shared_task
from flask import current_app

from app import celery, db
from app.models import Strategy, UserStrategy

REDIS_URL = current_app.config["REDIS_URL"]
redis_client = redis.StrictRedis.from_url(REDIS_URL)


@celery.task(bind=True, default_retry_delay=60, max_retries=5)
def execute_user_strategy(self, user_strategy_id):
    try:
        user_strategy = db.session.get(UserStrategy, user_strategy_id)
        if user_strategy and user_strategy.active:
            user_strategy.execute()
            db.session.commit()
    except Exception as exc:
        raise self.retry(exc=exc)


@celery.task
def execute_strategies():
    """Launch a Celery task for each user's strategy that needs to be executed."""
    now = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)

    # Query active UserStrategies that match the current execution time (HH:MM:SS)
    user_strategies = db.session.scalars(
        sa.select(UserStrategy)
        .where(UserStrategy.active == True)
        .where(UserStrategy.execution_time != None)
        .where(sa.func.time(UserStrategy.execution_time) == now.time())
    ).all()

    # Launch a separate task for each UserStrategy
    for user_strategy in user_strategies:
        execute_user_strategy.delay(user_strategy.id)  # Launch each task concurrently

        # Log the execution
    current_app.logger.info(
        f"Scheduled {len(user_strategies)} strategies to execute at {now}."
    )


# need to handle speed. it would slow down as make strategies
@shared_task(bind=True)
def update_strategies_historical_data():
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
