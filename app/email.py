# from threading import Thread

# from flask import current_app
# from flask_mail import Message

# from app import mail


# def send_async_email(app, msg):
#     with app.app_context():  #
#         mail.send(msg)


# def send_email(subject, sender, recipients, text_body, html_body):
#     msg = Message(subject, sender=sender, recipients=recipients)
#     msg.body = text_body
#     msg.html = html_body
#     Thread(
#         target=send_async_email, args=(current_app._get_current_object(), msg)
#     ).start()


# def send_email(subject, sender, recipients, text_body, html_body):
#     """Schedule an email to be sent asynchronously with Celery."""
#     from app.tasks import send_async_email

#     send_async_email.delay(subject, sender, recipients, text_body, html_body)


from flask import current_app


def send_email(subject, sender, recipients, text_body, html_body):
    """Schedule an email to be sent asynchronously with Celery."""
    current_app.extensions["celery"].send_task(
        "app.tasks.send_async_email",  # Task name as a string
        args=[subject, sender, recipients, text_body, html_body],
    )
