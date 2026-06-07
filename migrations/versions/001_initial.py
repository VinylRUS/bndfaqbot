"""Initial migration

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE role_enum AS ENUM ('admin', 'operator', 'user')")
    op.execute("CREATE TYPE ticket_status_enum AS ENUM ('NEW', 'IN_PROGRESS', 'ANSWERED', 'CLOSED')")

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.Enum("admin", "operator", "user", name="role_enum", native_enum=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("emoji", sa.String(10), nullable=False, server_default=""),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["parent_id"], ["categories.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("first_name", sa.String(255), nullable=True),
        sa.Column("last_name", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])

    op.create_table(
        "tickets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.BigInteger(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("NEW", "IN_PROGRESS", "ANSWERED", "CLOSED", name="ticket_status_enum", native_enum=True),
            nullable=False,
        ),
        sa.Column("operator_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["author_id"], ["users.telegram_id"]),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["operator_id"], ["users.telegram_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("number"),
    )
    op.create_index("ix_tickets_number", "tickets", ["number"])

    op.create_table(
        "ticket_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.ForeignKeyConstraint(["sender_id"], ["users.telegram_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ticket_messages_ticket_id", "ticket_messages", ["ticket_id"])

    op.create_table(
        "faq",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("question", sa.String(500), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "auto_answers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("keywords", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "ratings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("score", sa.SmallInteger(), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticket_id"),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("role", sa.String(50), nullable=True),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("object_type", sa.String(100), nullable=True),
        sa.Column("object_id", sa.Integer(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Seed default roles
    op.execute("INSERT INTO roles (name) VALUES ('admin'), ('operator'), ('user')")

    # Seed default auto-answers
    op.execute(
        "INSERT INTO auto_answers (keywords, answer, is_active) VALUES "
        "('зарплата,зп,когда зарплата,когда зп,когда будет зарплата', "
        "'Зарплата выплачивается 5 и 20 числа каждого месяца.', true), "
        "('аванс,когда аванс,когда будет аванс', "
        "'Аванс выплачивается 20 числа каждого месяца.', true)"
    )

    # Seed default FAQ
    op.execute(
        "INSERT INTO faq (question, answer, is_active) VALUES "
        "('Когда выплачивается зарплата?', 'Зарплата выплачивается 5 и 20 числа каждого месяца.', true), "
        "('Как взять отпуск?', 'Для оформления отпуска обратитесь к вашему руководителю или в отдел кадров.', true), "
        "('Когда можно взять больничный?', 'Больничный оформляется с первого дня заболевания. Необходимо уведомить руководителя и предоставить лист нетрудоспособности после выхода на работу.', true), "
        "('Как посмотреть расчётный лист?', 'Расчётный лист доступен в личном кабинете сотрудника или по запросу в бухгалтерии.', true)"
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("ratings")
    op.drop_table("auto_answers")
    op.drop_table("faq")
    op.drop_table("ticket_messages")
    op.drop_table("tickets")
    op.drop_table("users")
    op.drop_table("categories")
    op.drop_table("roles")
    op.execute("DROP TYPE IF EXISTS ticket_status_enum")
    op.execute("DROP TYPE IF EXISTS role_enum")
