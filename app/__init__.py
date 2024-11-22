import logging
import os
from logging.handlers import RotatingFileHandler, SMTPHandler

from celery import Celery, Task
from celery.schedules import crontab
from dotenv import load_dotenv
from flask import Flask
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_moment import Moment
from flask_sqlalchemy import SQLAlchemy

from config import Config


def celery_init_app(app: Flask) -> Celery:

    class FlaskTask(Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(app.name, task_cls=FlaskTask)
    celery_app.config_from_object(app.config["CELERY"])
    celery_app.set_default()
    celery_app.autodiscover_tasks(["app.tasks"])
    app.extensions["celery"] = celery_app
    return celery_app


db = SQLAlchemy()
migrate = Migrate()
login = LoginManager()
login.login_view = "auth.login"
mail = Mail()
moment = Moment()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    mail.init_app(app)
    moment.init_app(app)
    app.config.from_mapping(
        CELERY=dict(
            broker_url=app.config["CELERY_BROKER_URL"],
            result_backend=app.config["CELERY_RESULT_BACKEND"],
            task_ignore_result=False,
            beat_schedule={
                "update_and_execute": {
                    "task": "app.tasks.update_and_execute",
                    "schedule": crontab(minute="*"),
                },
            },
            task_routes=[
                {"app.tasks.update_and_execute": {"queue": "offbit"}},
                {"app.tasks.execute_strategies": {"queue": "offbit"}},
                {"app.tasks.execute_user_strategy": {"queue": "offbit"}},
                {"app.tasks.update_coins_historical_data": {"queue": "offbit"}},
                {"app.tasks.update_strategies_performance": {"queue": "offbit"}},
                {"app.tasks.update_coins_performance": {"queue": "offbit"}},
                {"app.tasks.send_async_email": {"queue": "offbit"}},
                {"app.tasks.start_redis_listener": {"queue": "offbit"}},
                {"app.tasks.start_websocket_client": {"queue": "offbit"}},
            ],
        ),
    )
    celery_init_app(app)

    # Register routes and models
    from app.errors import bp as errors_bp

    app.register_blueprint(errors_bp)

    from app.main import bp as routes_bp

    app.register_blueprint(routes_bp)

    from app.auth import bp as auth_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")

    from app.user import bp as user_bp

    app.register_blueprint(user_bp, url_prefix="/my")

    if not app.debug and not app.testing:
        if app.config["MAIL_SERVER"]:
            auth = None
            if app.config["MAIL_USERNAME"] and app.config["MAIL_PASSWORD"]:
                auth = (
                    app.config["MAIL_USERNAME"],
                    app.config["MAIL_PASSWORD"],
                )
            secure = None
            if app.config["MAIL_USE_TLS"]:
                secure = ()
            mail_handler = SMTPHandler(
                mailhost=(app.config["MAIL_SERVER"], app.config["MAIL_PORT"]),
                fromaddr="no-reply@" + app.config["MAIL_SERVER"],
                toaddrs=app.config["ADMINS"],
                subject="Offbit Failure",
                credentials=auth,
                secure=secure,
            )
            mail_handler.setLevel(logging.ERROR)
            app.logger.addHandler(mail_handler)

        if not os.path.exists("logs"):
            os.mkdir("logs")
        # file_handler = RotatingFileHandler(
        #     "logs/offbit.log",
        #     maxBytes=10240,
        #     backupCount=10,
        # )
        file_handler = logging.FileHandler("logs/offbit.log")

        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
            )
        )
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

        app.logger.setLevel(logging.INFO)
        app.logger.info("Offbit startup")

    # # Start the Redis listener using a Celery task
    # app.extensions["celery"].send_task("app.tasks.start_redis_listener")
    # app.extensions["celery"].send_task("app.tasks.start_websocket_client")

    return app


from app import models
