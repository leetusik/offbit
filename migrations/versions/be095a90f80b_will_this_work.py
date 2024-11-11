"""will this work?

Revision ID: be095a90f80b
Revises: b1bd1aff0293
Create Date: 2024-10-25 01:24:56.654956

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'be095a90f80b'
down_revision = 'b1bd1aff0293'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('coin', schema=None) as batch_op:
        batch_op.add_column(sa.Column('historical_data', sa.LargeBinary(), nullable=True))
        batch_op.add_column(sa.Column('short_historical_data', sa.LargeBinary(), nullable=True))

    with op.batch_alter_table('strategy', schema=None) as batch_op:
        batch_op.drop_column('historical_data')
        batch_op.drop_column('short_historical_data')

    with op.batch_alter_table('user_strategy', schema=None) as batch_op:
        batch_op.drop_column('historical_data_resampled')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user_strategy', schema=None) as batch_op:
        batch_op.add_column(sa.Column('historical_data_resampled', sa.BLOB(), nullable=True))

    with op.batch_alter_table('strategy', schema=None) as batch_op:
        batch_op.add_column(sa.Column('short_historical_data', sa.BLOB(), nullable=True))
        batch_op.add_column(sa.Column('historical_data', sa.BLOB(), nullable=True))

    with op.batch_alter_table('coin', schema=None) as batch_op:
        batch_op.drop_column('short_historical_data')
        batch_op.drop_column('historical_data')

    # ### end Alembic commands ###
