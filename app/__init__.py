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
    # print(celery_app.conf)
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
                {"app.tasks.update_strategies_historical_data": {"queue": "offbit"}},
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
        file_handler = RotatingFileHandler(
            "logs/offbit.log",
            maxBytes=10240,
            backupCount=10,
        )
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
            )
        )
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

        app.logger.setLevel(logging.INFO)
        app.logger.info("Offbit startup")

    # Add this to check that the config is loaded properly
    print(f"PRIVATE_KEY_PATH: {app.config.get('PRIVATE_KEY_PATH')}")

    return app


from app import models

# Settings(
#     Settings(
#         {"deprecated_settings": set()},
#         {
#             "broker_url": "redis://192.168.0.13:6379",
#             "result_backend": "redis://192.168.0.13:6379",
#             "task_ignore_result": True,
#         },
#         {
#             "accept_content": ("json",),
#             "result_accept_content": None,
#             "enable_utc": True,
#             "imports": (),
#             "include": (),
#             "timezone": None,
#             "beat_max_loop_interval": 0,
#             "beat_schedule": {},
#             "beat_scheduler": "celery.beat:PersistentScheduler",
#             "beat_schedule_filename": "celerybeat-schedule",
#             "beat_sync_every": 0,
#             "beat_cron_starting_deadline": None,
#             "broker_url": None,
#             "broker_read_url": None,
#             "broker_write_url": None,
#             "broker_transport": None,
#             "broker_transport_options": {},
#             "broker_connection_timeout": 4,
#             "broker_connection_retry": True,
#             "broker_connection_retry_on_startup": None,
#             "broker_connection_max_retries": 100,
#             "broker_channel_error_retry": False,
#             "broker_failover_strategy": None,
#             "broker_heartbeat": 120,
#             "broker_heartbeat_checkrate": 3.0,
#             "broker_login_method": None,
#             "broker_pool_limit": 10,
#             "broker_use_ssl": False,
#             "broker_host": None,
#             "broker_port": None,
#             "broker_user": None,
#             "broker_password": None,
#             "broker_vhost": None,
#             "cache_backend": None,
#             "cache_backend_options": {},
#             "cassandra_entry_ttl": None,
#             "cassandra_keyspace": None,
#             "cassandra_port": None,
#             "cassandra_read_consistency": None,
#             "cassandra_servers": None,
#             "cassandra_bundle_path": None,
#             "cassandra_table": None,
#             "cassandra_write_consistency": None,
#             "cassandra_auth_provider": None,
#             "cassandra_auth_kwargs": None,
#             "cassandra_options": {},
#             "s3_access_key_id": None,
#             "s3_secret_access_key": None,
#             "s3_bucket": None,
#             "s3_base_path": None,
#             "s3_endpoint_url": None,
#             "s3_region": None,
#             "azureblockblob_container_name": "celery",
#             "azureblockblob_retry_initial_backoff_sec": 2,
#             "azureblockblob_retry_increment_base": 2,
#             "azureblockblob_retry_max_attempts": 3,
#             "azureblockblob_base_path": "",
#             "azureblockblob_connection_timeout": 20,
#             "azureblockblob_read_timeout": 120,
#             "gcs_bucket": None,
#             "gcs_project": None,
#             "gcs_base_path": "",
#             "gcs_ttl": 0,
#             "control_queue_ttl": 300.0,
#             "control_queue_expires": 10.0,
#             "control_exchange": "celery",
#             "couchbase_backend_settings": None,
#             "arangodb_backend_settings": None,
#             "mongodb_backend_settings": None,
#             "cosmosdbsql_database_name": "celerydb",
#             "cosmosdbsql_collection_name": "celerycol",
#             "cosmosdbsql_consistency_level": "Session",
#             "cosmosdbsql_max_retry_attempts": 9,
#             "cosmosdbsql_max_retry_wait_time": 30,
#             "event_queue_expires": 60.0,
#             "event_queue_ttl": 5.0,
#             "event_queue_prefix": "celeryev",
#             "event_serializer": "json",
#             "event_exchange": "celeryev",
#             "redis_backend_use_ssl": None,
#             "redis_db": None,
#             "redis_host": None,
#             "redis_max_connections": None,
#             "redis_username": None,
#             "redis_password": None,
#             "redis_port": None,
#             "redis_socket_timeout": 120.0,
#             "redis_socket_connect_timeout": None,
#             "redis_retry_on_timeout": False,
#             "redis_socket_keepalive": False,
#             "result_backend": None,
#             "result_cache_max": -1,
#             "result_compression": None,
#             "result_exchange": "celeryresults",
#             "result_exchange_type": "direct",
#             "result_expires": datetime.timedelta(days=1),
#             "result_persistent": None,
#             "result_extended": False,
#             "result_serializer": "json",
#             "result_backend_transport_options": {},
#             "result_chord_retry_interval": 1.0,
#             "result_chord_join_timeout": 3.0,
#             "result_backend_max_sleep_between_retries_ms": 10000,
#             "result_backend_max_retries": inf,
#             "result_backend_base_sleep_between_retries_ms": 10,
#             "result_backend_always_retry": False,
#             "elasticsearch_retry_on_timeout": None,
#             "elasticsearch_max_retries": None,
#             "elasticsearch_timeout": None,
#             "elasticsearch_save_meta_as_text": True,
#             "security_certificate": None,
#             "security_cert_store": None,
#             "security_key": None,
#             "security_key_password": None,
#             "security_digest": "sha256",
#             "database_url": None,
#             "database_engine_options": None,
#             "database_short_lived_sessions": False,
#             "database_table_schemas": None,
#             "database_table_names": None,
#             "task_acks_late": False,
#             "task_acks_on_failure_or_timeout": True,
#             "task_always_eager": False,
#             "task_annotations": None,
#             "task_compression": None,
#             "task_create_missing_queues": True,
#             "task_inherit_parent_priority": False,
#             "task_default_delivery_mode": 2,
#             "task_default_queue": "celery",
#             "task_default_exchange": None,
#             "task_default_exchange_type": "direct",
#             "task_default_routing_key": None,
#             "task_default_rate_limit": None,
#             "task_default_priority": None,
#             "task_eager_propagates": False,
#             "task_ignore_result": False,
#             "task_store_eager_result": False,
#             "task_protocol": 2,
#             "task_publish_retry": True,
#             "task_publish_retry_policy": {
#                 "max_retries": 3,
#                 "interval_start": 0,
#                 "interval_max": 1,
#                 "interval_step": 0.2,
#             },
#             "task_queues": None,
#             "task_queue_max_priority": None,
#             "task_reject_on_worker_lost": None,
#             "task_remote_tracebacks": False,
#             "task_routes": None,
#             "task_send_sent_event": False,
#             "task_serializer": "json",
#             "task_soft_time_limit": None,
#             "task_time_limit": None,
#             "task_store_errors_even_if_ignored": False,
#             "task_track_started": False,
#             "task_allow_error_cb_on_chord_header": False,
#             "worker_agent": None,
#             "worker_autoscaler": "celery.worker.autoscale:Autoscaler",
#             "worker_cancel_long_running_tasks_on_connection_loss": False,
#             "worker_concurrency": None,
#             "worker_consumer": "celery.worker.consumer:Consumer",
#             "worker_direct": False,
#             "worker_disable_rate_limits": False,
#             "worker_deduplicate_successful_tasks": False,
#             "worker_enable_remote_control": True,
#             "worker_hijack_root_logger": True,
#             "worker_log_color": None,
#             "worker_log_format": "[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
#             "worker_lost_wait": 10.0,
#             "worker_max_memory_per_child": None,
#             "worker_max_tasks_per_child": None,
#             "worker_pool": "prefork",
#             "worker_pool_putlocks": True,
#             "worker_pool_restarts": False,
#             "worker_proc_alive_timeout": 4.0,
#             "worker_prefetch_multiplier": 4,
#             "worker_enable_prefetch_count_reduction": True,
#             "worker_redirect_stdouts": True,
#             "worker_redirect_stdouts_level": "WARNING",
#             "worker_send_task_events": False,
#             "worker_state_db": None,
#             "worker_task_log_format": "[%(asctime)s: %(levelname)s/%(processName)s] %(task_name)s[%(task_id)s]: %(message)s",
#             "worker_timer": None,
#             "worker_timer_precision": 1.0,
#             "deprecated_settings": None,
#         },
#     )
# )
