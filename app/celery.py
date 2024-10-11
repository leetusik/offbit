from celery import Celery
from celery.schedules import crontab


def make_celery(app):
    celery = Celery(
        app.import_name,
        backend=app.config["CELERY_RESULT_BACKEND"],
        broker=app.config["CELERY_BROKER_URL"],
    )
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    # Add periodic tasks for strategy execution and historical data updates
    celery.conf.beat_schedule = {
        "update-strategies-historical-data-daily": {
            "task": "app.tasks.update_strategies_historical_data",
            "schedule": crontab(minute="*"),  # Run every minute
        },
        "execute-strategies-every-minute": {
            "task": "app.tasks.execute_strategies",
            "schedule": crontab(minute="*"),  # Run every minute
        },
    }

    return celery
