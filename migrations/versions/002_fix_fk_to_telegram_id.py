"""Fix FK constraints: reference users.telegram_id instead of users.id

The code stores telegram_id values in author_id, operator_id, sender_id,
user_id columns, but FK constraints incorrectly referenced users.id (auto-increment).
This migration fixes all FK constraints to reference users.telegram_id.

Revision ID: 002
Revises: 001
Create Date: 2026-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # audit_logs.user_id
    op.drop_constraint("audit_logs_user_id_fkey", "audit_logs", type_="foreignkey")
    op.create_foreign_key(
        "audit_logs_user_id_fkey", "audit_logs", "users",
        ["user_id"], ["telegram_id"],
    )

    # ratings.user_id
    op.drop_constraint("ratings_user_id_fkey", "ratings", type_="foreignkey")
    op.create_foreign_key(
        "ratings_user_id_fkey", "ratings", "users",
        ["user_id"], ["telegram_id"],
    )

    # tickets.author_id
    op.drop_constraint("tickets_author_id_fkey", "tickets", type_="foreignkey")
    op.create_foreign_key(
        "tickets_author_id_fkey", "tickets", "users",
        ["author_id"], ["telegram_id"],
    )

    # tickets.operator_id
    op.drop_constraint("tickets_operator_id_fkey", "tickets", type_="foreignkey")
    op.create_foreign_key(
        "tickets_operator_id_fkey", "tickets", "users",
        ["operator_id"], ["telegram_id"],
    )

    # ticket_messages.sender_id
    op.drop_constraint("ticket_messages_sender_id_fkey", "ticket_messages", type_="foreignkey")
    op.create_foreign_key(
        "ticket_messages_sender_id_fkey", "ticket_messages", "users",
        ["sender_id"], ["telegram_id"],
    )


def downgrade() -> None:
    # Revert audit_logs.user_id
    op.drop_constraint("audit_logs_user_id_fkey", "audit_logs", type_="foreignkey")
    op.create_foreign_key(
        "audit_logs_user_id_fkey", "audit_logs", "users",
        ["user_id"], ["id"],
    )

    # Revert ratings.user_id
    op.drop_constraint("ratings_user_id_fkey", "ratings", type_="foreignkey")
    op.create_foreign_key(
        "ratings_user_id_fkey", "ratings", "users",
        ["user_id"], ["id"],
    )

    # Revert tickets.author_id
    op.drop_constraint("tickets_author_id_fkey", "tickets", type_="foreignkey")
    op.create_foreign_key(
        "tickets_author_id_fkey", "tickets", "users",
        ["author_id"], ["id"],
    )

    # Revert tickets.operator_id
    op.drop_constraint("tickets_operator_id_fkey", "tickets", type_="foreignkey")
    op.create_foreign_key(
        "tickets_operator_id_fkey", "tickets", "users",
        ["operator_id"], ["id"],
    )

    # Revert ticket_messages.sender_id
    op.drop_constraint("ticket_messages_sender_id_fkey", "ticket_messages", type_="foreignkey")
    op.create_foreign_key(
        "ticket_messages_sender_id_fkey", "ticket_messages", "users",
        ["sender_id"], ["id"],
    )
