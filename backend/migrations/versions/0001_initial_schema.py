from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    existing_tables = set(inspect(op.get_bind()).get_table_names())

    if "users" not in existing_tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("username", sa.String(length=255), nullable=False, unique=True),
            sa.Column("password", sa.String(length=255), nullable=False),
            sa.Column("group_name", sa.String(length=255), nullable=False),
        )

    if "action_log" not in existing_tables:
        op.create_table(
            "action_log",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("timestamp", sa.Text(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("exercise", sa.String(length=255), nullable=False),
            sa.Column("action", sa.String(length=255), nullable=False),
            sa.Column("previous_code", sa.Text(), nullable=True),
            sa.Column("current_code", sa.Text(), nullable=True),
            sa.Column("code_status", sa.String(length=255), nullable=True),
            sa.Column("feedback", sa.Text(), nullable=True),
            sa.Column("hint_tree", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        )


# def downgrade():
#     op.drop_table("action_log")
#     op.drop_table("users")

def downgrade():
    raise NotImplementedError("The initial schema migration is intentionally irreversible.")