import uuid
from pathlib import Path

from app.agents.workers import WorkExecution, WorkExecutionStatus
from app.api.api import _extract_approvals
from app.orchestration.state import (
    CoordinatorExecution,
    CoordinatorStages,
    MergeConflict,
    WorkRecord,
    WorkRecordStatus,
)
from app.orchestration.worktrees import Worktree
from app.schemas.schemas import ApprovalRequest, Workstream


def _pending_execution(call_id: str) -> WorkExecution:
    return WorkExecution(
        status=WorkExecutionStatus.PENDING_APPROVAL,
        run_state={"saved": True},
        approval_requests=[
            ApprovalRequest(
                call_id=call_id,
                tool_name="apply_patch",
                summary="Edit a file",
            )
        ],
    )


def test_extract_approvals_uses_only_the_current_pause_source():
    active_work = WorkRecord(
        work_id=uuid.uuid4(),
        status=WorkRecordStatus.NOT_MERGED,
        workstream=Workstream(
            name="active",
            task="Implement the active work",
            intended_paths=["backend"],
            acceptance_criteria=["The work is complete"],
        ),
        worktree=Worktree(
            id="active",
            branch="worker/active",
            path=Path("/tmp/active"),
        ),
        work_execution=_pending_execution("active-worker-call"),
    )
    state = CoordinatorExecution(
        stage=CoordinatorStages.AWAITING_APPROVALS,
        work_records=[active_work],
        merge_conflict=MergeConflict(
            work_id=active_work.work_id,
            file_paths=[Path("backend/conflicted.py")],
            repair_execution=_pending_execution("stale-repair-call"),
        ),
    )

    requests = _extract_approvals(state)

    assert [request.call_id for request in requests] == ["active-worker-call"]
