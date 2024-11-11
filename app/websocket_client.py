# app/websocket_client.py

import asyncio
import json

import redis
import websockets
from flask import current_app

from app import create_app

app = create_app()

with app.app_context():
    REDIS_URL = current_app.config["REDIS_URL"]
    redis_client = redis.StrictRedis.from_url(REDIS_URL)


async def upbit_websocket():
    """Connect to Upbit WebSocket and publish coin prices to Redis."""
    uri = "wss://api.upbit.com/websocket/v1"
    async with websockets.connect(uri) as websocket:
        subscribe_message = [
            {"ticket": "test"},
            {
                "type": "ticker",
                "codes": ["KRW-BTC", "KRW-ETH"],
                # "isOnlyRealtime": True,
            },  # Add more coins as needed
            {"format": "SIMPLE"},
        ]
        await websocket.send(json.dumps(subscribe_message))

        while True:
            response = await websocket.recv()
            data = json.loads(response)
            ticker = data.get("cd")
            price = data.get("tp")

            # Publish the price update to Redis
            redis_client.publish(
                "coin_prices", json.dumps({"ticker": ticker, "price": price})
            )


def run_websocket_client():
    """Run the WebSocket client."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(upbit_websocket())
