from flask import current_app


def send_email(subject, sender, recipients, text_body, html_body):
    """Schedule an email to be sent asynchronously with Celery."""
    current_app.extensions["celery"].send_task(
        "app.tasks.send_async_email",  # Task name as a string
        args=[subject, sender, recipients, text_body, html_body],
    )
