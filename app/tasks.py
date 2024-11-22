from datetime import datetime, timedelta, timezone

import redis
import sqlalchemy as sa
from celery import shared_task
from flask import current_app
from flask_mail import Message

from app import create_app, db, mail
from app.models import Coin, Strategy, UserStrategy
from app.redis_listener import listen_to_redis_channel
from app.utils.performance_utils import (
    calculate_coin_performance,
    calculate_strategy_performance,
)
from app.websocket_client import run_websocket_client

app = create_app()

with app.app_context():
    REDIS_URL = current_app.config["REDIS_URL"]
    redis_client = redis.StrictRedis.from_url(REDIS_URL)


@shared_task
def start_websocket_client():
    """Celery task to start the WebSocket client."""
    # Create a Redis lock object
    lock = redis_client.lock("start_websocket_client", timeout=3600)  # Lock for 1 hour

    # Attempt to acquire the lock
    if lock.acquire(blocking=False):  # Non-blocking acquire
        try:
            # Only one task will proceed to run this
            run_websocket_client()
        finally:
            # Ensure the lock is released when done
            lock.release()


@shared_task
def start_redis_listener():
    """Celery task to start the Redis Pub/Sub listener."""
    # Create a Redis lock object
    lock = redis_client.lock("start_redis_listener", timeout=3600)  # Lock for 1 hour

    # Attempt to acquire the lock
    if lock.acquire(blocking=False):  # Non-blocking acquire
        try:
            # Only one task will proceed to run this
            listen_to_redis_channel()
        finally:
            # Ensure the lock is released when done
            lock.release()


@shared_task
def send_async_email(subject, sender, recipients, text_body, html_body):
    """Background task to send an email with Celery."""
    msg = Message(subject, sender=sender, recipients=recipients)
    msg.body = text_body
    msg.html = html_body

    with app.app_context():
        mail.send(msg)


@shared_task
def update_strategies_performance():
    strategies = db.session.scalars(sa.select(Strategy)).all()

    for strategy in strategies:
        (
            performance_24h,
            performance_30d,
            performance_1y,
        ) = calculate_strategy_performance(
            strategy=strategy, time_period=timedelta(days=450)
        )
        last_update = str(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
        redis_client.hset(f"strategy:{strategy.id}:update", "last_update", last_update)
        redis_client.hset(f"strategy:{strategy.id}:performance", "24h", performance_24h)
        redis_client.hset(f"strategy:{strategy.id}:performance", "30d", performance_30d)
        redis_client.hset(f"strategy:{strategy.id}:performance", "1y", performance_1y)


@shared_task
def update_coins_performance():
    coins = db.session.scalars(sa.select(Coin)).all()

    for coin in coins:
        (
            coin_24h,
            coin_30d,
            coin_1y,
        ) = calculate_coin_performance(coin=coin)
        last_update = str(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
        redis_client.hset(f"coin:{coin.id}:update", "last_update", last_update)
        redis_client.hset(f"coin:{coin.id}:performance", "24h", coin_24h)
        redis_client.hset(f"coin:{coin.id}:performance", "30d", coin_30d)
        redis_client.hset(f"coin:{coin.id}:performance", "1y", coin_1y)


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
        update_coins_historical_data()
        execute_strategies.delay()

        current = datetime.now()

        update_coins_performance()
        update_strategies_performance()
        # if current.minute == 0:
        #     update_coins_performance()
        #     update_strategies_performance()

    finally:
        # Ensure the lock is released when the task is done
        lock.release()


@shared_task
def execute_user_strategy(user_strategy_id, first_execution=False):
    print("task execute_user_strategy executed.")
    user_strategy = db.session.get(UserStrategy, user_strategy_id)
    print(user_strategy, user_strategy.active)
    if first_execution:
        user_strategy.active = True
    print(user_strategy, user_strategy.active)
    if user_strategy and user_strategy.active:
        user_strategy.execute()


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
def update_coins_historical_data():
    print("task update_coins_historical_data executed.")
    # Set a unique lock name for the task
    lock = redis_client.lock("update_strategies_lock", timeout=3600)  # Lock for 1 hour
    have_lock = lock.acquire(blocking=False)

    if not have_lock:
        # If another worker is running this task, exit the function
        print("Another instance of update_coins_historical_data is already running.")
        return
    try:
        coins = db.session.scalars(sa.select(Coin)).all()
        for coin in coins:
            # can't do seperate and delay bcs there are limit on the api call.
            coin.make_historical_data()
    finally:
        # Ensure the lock is released when the task is done
        lock.release()


@shared_task
def dummy_function(a, b):
    print(a)
    print(b)
    print(f"{a} + {b} = {a+b}")
    # return None
