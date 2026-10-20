from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0002_add_last_correct_code"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade():
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("action_log")}
    if "last_correct_code" not in columns:
        op.add_column("action_log", sa.Column("last_correct_code", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("action_log", "last_correct_code")
