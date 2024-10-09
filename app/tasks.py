from datetime import datetime, timezone

import sqlalchemy as sa
from flask import current_app

from app import celery, db
from app.models import UserStrategy


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
    now = datetime.now(timezone.utc).replace(microsecond=0)

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
