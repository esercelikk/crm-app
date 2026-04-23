from __future__ import annotations

from typing import Any, Dict, Iterable, List, Set


ROLE_SUPER_ADMIN = "Süper Admin"
ROLE_ADMIN = "Yönetici"
ROLE_SALES_MANAGER = "Satış Müdürü"
ROLE_SALES_REP = "Satış Temsilcisi"
ROLE_SUPPORT = "Destek"
ROLE_FINANCE = "Finans"

ROLE_OPTIONS = [
    ROLE_SUPER_ADMIN,
    ROLE_ADMIN,
    ROLE_SALES_MANAGER,
    ROLE_SALES_REP,
    ROLE_SUPPORT,
    ROLE_FINANCE,
]

ROLE_ORDER = {role: index + 1 for index, role in enumerate(ROLE_OPTIONS)}

ROLE_GOALS = {
    ROLE_SUPER_ADMIN: 100000,
    ROLE_ADMIN: 75000,
    ROLE_SALES_MANAGER: 90000,
    ROLE_SALES_REP: 50000,
    ROLE_SUPPORT: 0,
    ROLE_FINANCE: 0,
}

VIEW_ORDER = [
    "dashboard",
    "contacts",
    "pipeline",
    "calls",
    "calendar",
    "mail",
    "tasks",
    "files",
    "ai",
    "reports",
    "team",
]

ALL_VIEWS = set(VIEW_ORDER)

ROLE_VIEW_ACCESS = {
    ROLE_SUPER_ADMIN: ALL_VIEWS,
    ROLE_ADMIN: ALL_VIEWS,
    ROLE_SALES_MANAGER: ALL_VIEWS,
    ROLE_SALES_REP: {
        "dashboard",
        "contacts",
        "pipeline",
        "calls",
        "calendar",
        "mail",
        "tasks",
        "files",
        "ai",
        "team",
    },
    ROLE_SUPPORT: {
        "dashboard",
        "contacts",
        "calls",
        "calendar",
        "mail",
        "tasks",
        "files",
        "ai",
        "team",
    },
    ROLE_FINANCE: {
        "dashboard",
        "contacts",
        "pipeline",
        "files",
        "reports",
        "team",
    },
}

FULL_CONTROL_PERMISSIONS = {
    "contact_create",
    "contact_edit",
    "contact_delete",
    "contact_note_create",
    "opportunity_create",
    "opportunity_edit",
    "opportunity_move",
    "opportunity_delete",
    "call_create",
    "call_edit",
    "call_delete",
    "task_create",
    "task_edit",
    "task_toggle",
    "task_delete",
    "mail_compose",
    "mail_template_use",
    "mail_automation_manage",
    "file_open",
    "file_export",
    "file_upload",
    "file_delete",
    "ai_chat",
    "ai_settings_manage",
    "report_export",
    "team_manage",
    "team_delete",
    "settings_system_manage",
}

ROLE_PERMISSIONS = {
    ROLE_SUPER_ADMIN: FULL_CONTROL_PERMISSIONS,
    ROLE_ADMIN: FULL_CONTROL_PERMISSIONS - {"team_delete"},
    ROLE_SALES_MANAGER: {
        "contact_create",
        "contact_edit",
        "contact_note_create",
        "opportunity_create",
        "opportunity_edit",
        "opportunity_move",
        "opportunity_delete",
        "call_create",
        "call_edit",
        "call_delete",
        "task_create",
        "task_edit",
        "task_toggle",
        "task_delete",
        "mail_compose",
        "mail_template_use",
        "file_open",
        "file_export",
        "file_upload",
        "ai_chat",
        "report_export",
    },
    ROLE_SALES_REP: {
        "contact_create",
        "contact_edit",
        "contact_note_create",
        "opportunity_create",
        "opportunity_edit",
        "opportunity_move",
        "call_create",
        "call_edit",
        "task_create",
        "task_edit",
        "task_toggle",
        "mail_compose",
        "mail_template_use",
        "file_open",
        "file_export",
        "file_upload",
        "ai_chat",
    },
    ROLE_SUPPORT: {
        "contact_create",
        "contact_edit",
        "contact_note_create",
        "call_create",
        "call_edit",
        "call_delete",
        "task_create",
        "task_edit",
        "task_toggle",
        "task_delete",
        "mail_compose",
        "mail_template_use",
        "file_open",
        "file_export",
        "file_upload",
        "ai_chat",
    },
    ROLE_FINANCE: {
        "file_open",
        "file_export",
        "file_upload",
        "file_delete",
        "report_export",
    },
}


def normalize_role(role: str | None) -> str:
    return role if role in ROLE_ORDER else ROLE_SALES_REP


def permissions_for_role(role: str | None) -> Set[str]:
    return set(ROLE_PERMISSIONS.get(normalize_role(role), set()))


def role_can(role: str | None, permission: str) -> bool:
    return permission in permissions_for_role(role)


def user_can(user: Dict[str, Any] | None, permission: str) -> bool:
    return role_can((user or {}).get("role"), permission)


def role_can_view(role: str | None, view_name: str) -> bool:
    return view_name in ROLE_VIEW_ACCESS.get(normalize_role(role), set())


def user_can_view(user: Dict[str, Any] | None, view_name: str) -> bool:
    return role_can_view((user or {}).get("role"), view_name)


def visible_views_for_role(role: str | None, view_order: Iterable[str] = VIEW_ORDER) -> List[str]:
    normalized_role = normalize_role(role)
    allowed = ROLE_VIEW_ACCESS.get(normalized_role, set())
    return [view for view in view_order if view in allowed]

