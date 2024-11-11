"""add open api key hash

Revision ID: 9990661ac62c
Revises: 3f1ef16870f4
Create Date: 2024-10-31 09:50:13.226084

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9990661ac62c'
down_revision = '3f1ef16870f4'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('open_api_key_access_upbit_hash', sa.LargeBinary(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('open_api_key_access_upbit_hash')

    # ### end Alembic commands ###
