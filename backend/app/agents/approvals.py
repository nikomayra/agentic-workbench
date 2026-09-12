import json
from collections.abc import Callable
from typing import Any

from agents import ToolApprovalItem
from pydantic import BaseModel

from app.schemas.schemas import ApprovalRequest


class ApprovalRequestError(Exception):
    """The approval request has failed."""


def _raw_field(raw_item: object, field_name: str) -> object | None:
    """Read one documented field from either an SDK model or restored dictionary."""
    if isinstance(raw_item, dict):
        return raw_item.get(field_name)
    return getattr(raw_item, field_name, None)


def _approval_arguments(interruption: ToolApprovalItem) -> dict[str, Any]:
    """Parse ordinary function/MCP tool arguments for display."""
    if not interruption.arguments:
        return {}

    try:
        arguments = json.loads(interruption.arguments)
    except json.JSONDecodeError:
        return {"raw_arguments": interruption.arguments}

    if isinstance(arguments, dict):
        return arguments
    return {"arguments": arguments}


def _describe_apply_patch(
    interruption: ToolApprovalItem,
    _arguments: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    raw_operation = _raw_field(interruption.raw_item, "operation")

    if isinstance(raw_operation, BaseModel):
        operation = raw_operation.model_dump(mode="json")
    elif isinstance(raw_operation, dict):
        operation = raw_operation
    else:
        return "Apply repository patch", {}

    action = operation.get("type", "apply_patch")
    path = operation.get("path")
    verbs = {
        "create_file": "Create",
        "update_file": "Update",
        "delete_file": "Delete",
    }
    verb = verbs.get(str(action), "Modify")
    summary = f"{verb} {path}" if path else "Apply repository patch"
    return summary, operation


def _describe_git_commit(
    _interruption: ToolApprovalItem,
    arguments: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    commit_message = arguments.get("commit_message")
    if isinstance(commit_message, str) and commit_message:
        return f'Commit repository changes as "{commit_message}"', arguments
    return "Commit repository changes", arguments


ApprovalDescriber = Callable[
    [ToolApprovalItem, dict[str, Any]],
    tuple[str, dict[str, Any]],
]

APPROVAL_DESCRIBERS: dict[str, ApprovalDescriber] = {
    "apply_patch": _describe_apply_patch,
    "git_commit": _describe_git_commit,
}


def approval_request(interruption: ToolApprovalItem) -> ApprovalRequest:
    call_id = interruption.call_id
    if not call_id:
        raise ApprovalRequestError("Tool approval is missing a call ID.")

    lookup_name = interruption.name or "unknown_tool"
    display_name = interruption.qualified_name or lookup_name
    arguments = _approval_arguments(interruption)
    describe = APPROVAL_DESCRIBERS.get(lookup_name)

    if describe is None:
        summary = f"Run {display_name}"
        details = arguments
    else:
        summary, details = describe(interruption, arguments)

    return ApprovalRequest(
        call_id=call_id,
        tool_name=display_name,
        summary=summary,
        details=details,
    )
