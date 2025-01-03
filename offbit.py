import sqlalchemy as sa
import sqlalchemy.orm as so

from app import create_app, db
from app.models import Coin, Strategy, User, UserStrategy

app = create_app()


@app.shell_context_processor
def make_shell_context():
    return {
        "sa": sa,
        "so": so,
        "db": db,
        "User": User,
        "Strategy": Strategy,
        "UserStrategy": UserStrategy,
        "Coin": Coin,
    }
