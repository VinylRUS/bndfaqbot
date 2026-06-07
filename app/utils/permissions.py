from __future__ import annotations

from app.database.models.role import RoleEnum


ROLE_HIERARCHY = {
    RoleEnum.ADMIN: 3,
    RoleEnum.OPERATOR: 2,
    RoleEnum.USER: 1,
}


def has_permission(user_role: RoleEnum, required_role: RoleEnum) -> bool:
    return ROLE_HIERARCHY.get(user_role, 0) >= ROLE_HIERARCHY.get(required_role, 0)


def is_admin(role: RoleEnum) -> bool:
    return role == RoleEnum.ADMIN


def is_operator(role: RoleEnum) -> bool:
    return role == RoleEnum.OPERATOR


def is_user(role: RoleEnum) -> bool:
    return role == RoleEnum.USER


def can_manage_roles(user_role: RoleEnum) -> bool:
    return is_admin(user_role)


def can_manage_faq(user_role: RoleEnum) -> bool:
    return is_admin(user_role)


def can_manage_auto_answers(user_role: RoleEnum) -> bool:
    return is_admin(user_role)


def can_export(user_role: RoleEnum) -> bool:
    return is_admin(user_role)


def can_view_statistics(user_role: RoleEnum) -> bool:
    return is_admin(user_role)


def can_view_audit_logs(user_role: RoleEnum) -> bool:
    return is_admin(user_role)


def can_handle_tickets(user_role: RoleEnum) -> bool:
    return is_operator(user_role) or is_admin(user_role)
