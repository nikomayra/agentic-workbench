import uuid
from pathlib import Path

from app.agents.workers import (
    WorkerOutput,
    WorkExecution,
    WorkExecutionStatus,
)
from app.orchestration.state import (
    CoordinatorExecution,
    CoordinatorStages,
    MergeConflict,
    WorkRecord,
    WorkRecordStatus,
)
from app.orchestration.worktrees import Worktree
from app.schemas.schemas import (
    ApprovalRequest,
    Plan,
    PlanStep,
    Workstream,
)
from evals.models import EvalCase, RunObservation


def sample_plan() -> Plan:
    return Plan(
        summary="Make the requested change.",
        steps=[
            PlanStep(
                title="Implement change",
                description="Update the relevant fixture file.",
                acceptance_criteria="The requested behavior is present.",
            )
        ],
    )


def worktree(name: str) -> Worktree:
    return Worktree(
        id=name,
        branch=f"worker/{name}",
        path=Path(f"/tmp/{name}"),
    )


def completed_work_record(name: str) -> WorkRecord:
    return WorkRecord(
        work_id=uuid.uuid4(),
        status=WorkRecordStatus.NOT_MERGED,
        workstream=Workstream(
            name=name,
            task=f"Complete {name} work",
            intended_paths=[name],
            acceptance_criteria=[f"{name} work is complete"],
        ),
        worktree=worktree(name),
        work_execution=WorkExecution(
            status=WorkExecutionStatus.COMPLETED,
            output=WorkerOutput(work_notes=f"Completed {name}"),
        ),
    )


def merge_conflict_state(
    repair_execution: WorkExecution | None = None,
) -> CoordinatorExecution:
    conflicting_work = completed_work_record("frontend")
    return CoordinatorExecution(
        stage=(
            CoordinatorStages.MERGE_REPAIR_AWAITING_APPROVALS
            if repair_execution
            else CoordinatorStages.MERGE_CONFLICT
        ),
        work_records=[conflicting_work],
        integration_worktree=worktree("integration"),
        merge_conflict=MergeConflict(
            work_id=conflicting_work.work_id,
            file_paths=[Path("frontend/src/App.tsx")],
            repair_execution=repair_execution,
        ),
    )


def finalization_state() -> CoordinatorExecution:
    return CoordinatorExecution(
        stage=CoordinatorStages.AWAITING_FINAL_APPROVAL,
        work_records=[completed_work_record("backend")],
        integration_worktree=worktree("integration"),
    )


def pending_execution(call_id: str) -> WorkExecution:
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


def construct_eval_case(
    expected_path_prefixes: list[str], forbidden_path_prefixes: list[str]
) -> EvalCase:
    return EvalCase(
        id="test_eval_case",
        objective="test_objective",
        expected_path_prefixes=[Path(prefix) for prefix in expected_path_prefixes],
        forbidden_path_prefixes=[Path(prefix) for prefix in forbidden_path_prefixes],
    )


def construct_run_observation(
    tests_passed: bool, changed_paths: list[str], error: str | None = None
) -> RunObservation:
    return RunObservation(
        tests_passed=tests_passed,
        changed_paths=[Path(path) for path in changed_paths],
        latency_seconds=50,
        error=error,
    )
