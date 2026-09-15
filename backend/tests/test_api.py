import uuid
from pathlib import Path

from app.orchestration.state import (
    CoordinatorExecution,
    CoordinatorStages,
    MergeConflict,
    WorkRecord,
    WorkRecordStatus,
    pending_approval_requests,
)
from app.orchestration.worktrees import Worktree
from app.schemas.schemas import Workstream
from tests.factories import pending_execution


def test_pending_approval_requests_uses_only_the_current_pause_source():
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
        work_execution=pending_execution("active-worker-call"),
    )
    state = CoordinatorExecution(
        stage=CoordinatorStages.AWAITING_APPROVALS,
        work_records=[active_work],
        merge_conflict=MergeConflict(
            work_id=active_work.work_id,
            file_paths=[Path("backend/conflicted.py")],
            repair_execution=pending_execution("stale-repair-call"),
        ),
    )

    requests = pending_approval_requests(state)

    assert [request.call_id for request in requests] == ["active-worker-call"]
