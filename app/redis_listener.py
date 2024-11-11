import json

import redis
import sqlalchemy as sa
from flask import current_app

from app import create_app, db
from app.models import Coin, UserStrategy  # Import your models

app = create_app()

with app.app_context():
    REDIS_URL = current_app.config["REDIS_URL"]
    redis_client = redis.StrictRedis.from_url(REDIS_URL)

ticker_to_coin = {"KRW-BTC": "bitcoin", "KRW-ETH": "ethereum"}


def handle_price_update(message):
    """Process price update messages and execute strategies if conditions are met."""

    try:
        # The message data may need to be decoded from binary
        data = json.loads(message["data"].decode("utf-8"))

        # Extract ticker and price from the data
        ticker = data.get("ticker")  # Make sure to use the correct key
        current_price = data.get("price")

        print("Ticker:", ticker, "Price:", current_price)  # Debug: Check values

        # Fetch active strategies for the given ticker
        user_strategies = db.session.scalars(
            sa.select(UserStrategy)
            .join(UserStrategy.target_currency)  # Join with the Coin table
            .where(UserStrategy.active == True)
            .where(Coin.name == ticker_to_coin.get(ticker))  # Use Coin.name
        ).all()

        for user_strategy in user_strategies:
            if user_strategy.should_execute(current_price):
                # Trigger a Celery task for user_strategy execution
                app.extensions["celery"].send_task(
                    "app.tasks.execute_user_strategy", args=[user_strategy.id]
                )

    except Exception as e:
        # Print any exceptions for debugging
        print("Error parsing message:", e)


def listen_to_redis_channel():
    """Listen to the Redis Pub/Sub channel for coin price updates."""
    pubsub = redis_client.pubsub()
    pubsub.subscribe(**{"coin_prices": handle_price_update})

    for message in pubsub.listen():
        if message and message["type"] == "message":
            handle_price_update(message)
