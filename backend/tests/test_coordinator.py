import asyncio
import uuid
from pathlib import Path

import app.orchestration.coordinator as coordinator_module
from app.agents.planning import (
    _can_run_in_parallel,
    _execution_plan_for_work,
)
from app.agents.workers import (
    WorkerOutput,
    WorkExecution,
    WorkExecutionStatus,
)
from app.orchestration import repository_checks
from app.orchestration.coordinator import (
    _merge_worktrees_into_integration,
    _review_integration_worktree,
    _state_from_merge_repair_completed,
    advance_until_pause,
    finalize_coordinator,
    resume_merge_conflict_repair,
    start_merge_conflict_repair,
)
from app.orchestration.state import (
    CoordinatorExecution,
    CoordinatorStages,
    MergeConflict,
    WorkRecord,
    WorkRecordStatus,
)
from app.orchestration.worktrees import MergeOutcome, Worktree
from app.schemas.schemas import (
    ExecutionPlan,
    Plan,
    PlanStep,
    ReviewOutput,
    ReviewStatus,
    Workstream,
)


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


def test_identify_parallel_plans():
    one_workstream = Workstream(
        name="test",
        task="Do task",
        intended_paths=["backend/app/file_1", "backend/app/file_2"],
        acceptance_criteria=["task complete on file_1", "task complete on file_2"],
        shared_contracts=["Endpoint X expects Y data", "Endpoint Z expects A data"],
    )
    assert _can_run_in_parallel(ExecutionPlan(workstreams=[one_workstream])) is False

    two_workstreams = [
        Workstream(
            name="test1",
            task="Do task",
            intended_paths=["backend/app/file_1", "backend/app/file_2"],
            acceptance_criteria=["task complete on file_1", "task complete on file_2"],
            shared_contracts=["Endpoint X expects Y data", "Endpoint Z expects A data"],
        ),
        Workstream(
            name="test2",
            task="Do task",
            intended_paths=["frontend/app/file_1", "frontend/app/file_2"],
            acceptance_criteria=["task complete on file_1", "task complete on file_2"],
            shared_contracts=["Endpoint X expects Y data", "Endpoint Z expects A data"],
        ),
    ]
    assert _can_run_in_parallel(ExecutionPlan(workstreams=two_workstreams)) is True


def test_overlapping_decomposition_falls_back_to_one_worker():
    overlapping_plan = ExecutionPlan(
        workstreams=[
            Workstream(
                name="first",
                task="First task",
                intended_paths=["shared.py"],
                acceptance_criteria=["First task complete"],
            ),
            Workstream(
                name="second",
                task="Second task",
                intended_paths=["shared.py"],
                acceptance_criteria=["Second task complete"],
            ),
        ]
    )

    result = _execution_plan_for_work(sample_plan(), overlapping_plan)

    assert len(result.workstreams) == 1
    assert result.workstreams[0].name == "full-plan"


def _completed_work_record(name: str) -> WorkRecord:
    return WorkRecord(
        work_id=uuid.uuid4(),
        status=WorkRecordStatus.NOT_MERGED,
        workstream=Workstream(
            name=name,
            task=f"Complete {name} work",
            intended_paths=[name],
            acceptance_criteria=[f"{name} work is complete"],
        ),
        worktree=Worktree(
            id=name,
            branch=f"worker/{name}",
            path=Path(f"/tmp/{name}"),
        ),
        work_execution=WorkExecution(
            status=WorkExecutionStatus.COMPLETED,
            output=WorkerOutput(work_notes=f"Completed {name}"),
        ),
    )


def test_merge_stops_at_conflict_and_preserves_prior_progress(monkeypatch):
    first_work = _completed_work_record("backend")
    conflicting_work = _completed_work_record("frontend")
    integration_worktree = Worktree(
        id="integration",
        branch="worker/integration",
        path=Path("/tmp/integration"),
    )
    initial_state = CoordinatorExecution(
        stage=CoordinatorStages.INTEGRATING,
        work_records=[first_work, conflicting_work],
        integration_worktree=integration_worktree,
    )

    def fake_merge(worktree, _integration_worktree):
        if worktree.id == "backend":
            return MergeOutcome(conflicts=False)
        return MergeOutcome(
            conflicts=True,
            conflict_file_paths=(Path("frontend/src/App.tsx"),),
        )

    monkeypatch.setattr(
        coordinator_module,
        "merge_worktree_changes",
        fake_merge,
    )

    result = _merge_worktrees_into_integration(initial_state)

    assert result.stage == CoordinatorStages.MERGE_CONFLICT
    assert result.integration_worktree == integration_worktree
    assert result.work_records[0].status == WorkRecordStatus.MERGED
    assert result.work_records[1].status == WorkRecordStatus.NOT_MERGED
    assert result.merge_conflict is not None
    assert result.merge_conflict.work_id == conflicting_work.work_id
    assert result.merge_conflict.file_paths == [Path("frontend/src/App.tsx")]
    assert initial_state.work_records[0].status == WorkRecordStatus.NOT_MERGED


def _merge_conflict_state(
    repair_execution: WorkExecution | None = None,
) -> CoordinatorExecution:
    conflicting_work = _completed_work_record("frontend")
    return CoordinatorExecution(
        stage=(
            CoordinatorStages.MERGE_REPAIR_AWAITING_APPROVALS
            if repair_execution
            else CoordinatorStages.MERGE_CONFLICT
        ),
        work_records=[conflicting_work],
        integration_worktree=Worktree(
            id="integration",
            branch="worker/integration",
            path=Path("/tmp/integration"),
        ),
        merge_conflict=MergeConflict(
            work_id=conflicting_work.work_id,
            file_paths=[Path("frontend/src/App.tsx")],
            repair_execution=repair_execution,
        ),
    )


def test_start_merge_conflict_repair_saves_pending_execution(monkeypatch):
    pending_execution = WorkExecution(
        status=WorkExecutionStatus.PENDING_APPROVAL,
        run_state={"saved": "repair state"},
    )
    received_inputs = []

    async def fake_invoke_worker(trusted_root, worker_input):
        received_inputs.append((trusted_root, worker_input))
        return pending_execution

    monkeypatch.setattr(coordinator_module, "invoke_worker", fake_invoke_worker)

    result = asyncio.run(start_merge_conflict_repair(_merge_conflict_state()))

    assert result.stage == CoordinatorStages.MERGE_REPAIR_AWAITING_APPROVALS
    assert result.merge_conflict is not None
    assert result.merge_conflict.repair_execution == pending_execution
    assert received_inputs[0][0] == Path("/tmp/integration")
    assert received_inputs[0][1].workstream.intended_paths == ["frontend/src/App.tsx"]


def test_resume_merge_conflict_repair_saves_completed_execution(monkeypatch):
    pending_execution = WorkExecution(
        status=WorkExecutionStatus.PENDING_APPROVAL,
        run_state={"saved": "repair state"},
    )
    completed_execution = WorkExecution(
        status=WorkExecutionStatus.COMPLETED,
        output=WorkerOutput(work_notes="Resolved merge conflict"),
    )
    received_arguments = []

    async def fake_resume_worker(trusted_root, run_state, decisions):
        received_arguments.append((trusted_root, run_state, decisions))
        return completed_execution

    monkeypatch.setattr(coordinator_module, "resume_worker", fake_resume_worker)

    result = asyncio.run(
        resume_merge_conflict_repair(
            _merge_conflict_state(pending_execution),
            {},
        )
    )

    assert result.stage == CoordinatorStages.MERGE_REPAIR_COMPLETED
    assert result.merge_conflict is not None
    assert result.merge_conflict.repair_execution == completed_execution
    assert received_arguments == [
        (Path("/tmp/integration"), {"saved": "repair state"}, {})
    ]


def test_complete_merge_conflict_repair_clears_conflict_state(monkeypatch):
    completed_repair_execution = WorkExecution(
        status=WorkExecutionStatus.COMPLETED,
        output=WorkerOutput(work_notes="Completed work_id_1"),
    )
    conflicting_work = _completed_work_record("frontend")
    repair_complete_state = CoordinatorExecution(
        stage=CoordinatorStages.MERGE_REPAIR_COMPLETED,
        work_records=[conflicting_work],
        integration_worktree=Worktree(
            id="integration",
            branch="worker/integration",
            path=Path("/tmp/integration"),
        ),
        merge_conflict=MergeConflict(
            work_id=conflicting_work.work_id,
            file_paths=[Path("frontend/src/App.tsx")],
            repair_execution=completed_repair_execution,
        ),
    )

    monkeypatch.setattr(
        coordinator_module,
        "complete_merge_after_conflict",
        lambda *args, **kwargs: None,
    )

    updated_state = _state_from_merge_repair_completed(repair_complete_state)

    assert updated_state.work_records[0].status == WorkRecordStatus.MERGED
    assert updated_state.merge_conflict == None
    assert updated_state.stage == CoordinatorStages.INTEGRATING


def test_merge_continues_with_only_unmerged_work(monkeypatch):
    already_merged = _completed_work_record("backend").model_copy(
        update={"status": WorkRecordStatus.MERGED}
    )
    repaired_work = _completed_work_record("frontend").model_copy(
        update={"status": WorkRecordStatus.MERGED}
    )
    remaining_work = _completed_work_record("docs")
    merged_worktree_ids = []

    def fake_merge(worktree, _integration_worktree):
        merged_worktree_ids.append(worktree.id)
        return MergeOutcome(conflicts=False)

    monkeypatch.setattr(coordinator_module, "merge_worktree_changes", fake_merge)

    result = _merge_worktrees_into_integration(
        CoordinatorExecution(
            stage=CoordinatorStages.INTEGRATING,
            work_records=[already_merged, repaired_work, remaining_work],
            integration_worktree=Worktree(
                id="integration",
                branch="worker/integration",
                path=Path("/tmp/integration"),
            ),
        )
    )

    assert merged_worktree_ids == ["docs"]
    assert result.stage == CoordinatorStages.INTEGRATED
    assert all(work.status == WorkRecordStatus.MERGED for work in result.work_records)


def test_failed_tests_cannot_reach_final_approval(monkeypatch):
    state = CoordinatorExecution(
        stage=CoordinatorStages.INTEGRATED,
        work_records=[_completed_work_record("backend")],
        integration_worktree=Worktree(
            id="integration",
            branch="worker/integration",
            path=Path("/tmp/integration"),
        ),
    )

    monkeypatch.setattr(
        coordinator_module,
        "run_tests",
        lambda _root: repository_checks.TestsOutcome(
            passed=False, output="one test failed"
        ),
    )
    monkeypatch.setattr(
        coordinator_module,
        "git_diff",
        lambda _root: repository_checks.GitDiffOutcome(output="diff output"),
    )

    async def fake_reviewer(_root, review_input):
        assert review_input.test_output.startswith("Combined tests: FAILED")
        return ReviewOutput(status=ReviewStatus.SUCCESS)

    monkeypatch.setattr(coordinator_module, "invoke_reviewer", fake_reviewer)

    result = asyncio.run(_review_integration_worktree(sample_plan(), state))

    assert result.stage == CoordinatorStages.REVIEW_FINDINGS
    assert result.review_findings is not None
    assert result.review_findings.review_output.status == ReviewStatus.CHANGES_REQUIRED


def test_dispatcher_stops_at_final_approval():
    state = CoordinatorExecution(
        stage=CoordinatorStages.AWAITING_FINAL_APPROVAL,
        work_records=[_completed_work_record("backend")],
        integration_worktree=Worktree(
            id="integration",
            branch="worker/integration",
            path=Path("/tmp/integration"),
        ),
    )

    result = asyncio.run(advance_until_pause(sample_plan(), state))

    assert result is state


def test_dispatcher_advances_completed_work_to_final_approval(monkeypatch):
    transitions = []
    work_records = [_completed_work_record("backend")]
    integration_worktree = Worktree(
        id="integration",
        branch="worker/integration",
        path=Path("/tmp/integration"),
    )

    def fake_commit(state):
        transitions.append("commit")
        assert state.stage == CoordinatorStages.WORK_COMPLETED

    def fake_create_integration(state):
        transitions.append("create_integration")
        return state.model_copy(
            update={
                "stage": CoordinatorStages.INTEGRATING,
                "integration_worktree": integration_worktree,
            }
        )

    def fake_merge(state):
        transitions.append("merge")
        return state.model_copy(update={"stage": CoordinatorStages.INTEGRATED})

    async def fake_review(_plan, state):
        transitions.append("review")
        return state.model_copy(
            update={"stage": CoordinatorStages.AWAITING_FINAL_APPROVAL}
        )

    monkeypatch.setattr(coordinator_module, "_commit_completed_work", fake_commit)
    monkeypatch.setattr(
        coordinator_module,
        "_create_integration_worktree",
        fake_create_integration,
    )
    monkeypatch.setattr(
        coordinator_module,
        "_merge_worktrees_into_integration",
        fake_merge,
    )
    monkeypatch.setattr(
        coordinator_module,
        "_review_integration_worktree",
        fake_review,
    )

    result = asyncio.run(
        advance_until_pause(
            sample_plan(),
            CoordinatorExecution(
                stage=CoordinatorStages.WORK_COMPLETED,
                work_records=work_records,
            ),
        )
    )

    assert transitions == ["commit", "create_integration", "merge", "review"]
    assert result.stage == CoordinatorStages.AWAITING_FINAL_APPROVAL


def _finalization_state() -> CoordinatorExecution:
    return CoordinatorExecution(
        stage=CoordinatorStages.AWAITING_FINAL_APPROVAL,
        work_records=[_completed_work_record("backend")],
        integration_worktree=Worktree(
            id="integration",
            branch="worker/integration",
            path=Path("/tmp/integration"),
        ),
    )


def test_approved_finalization_removes_checkouts_but_keeps_result_branch(monkeypatch):
    removed_checkouts: list[str] = []
    deleted_branches: list[str] = []

    monkeypatch.setattr(
        coordinator_module,
        "remove_worktree_checkout",
        lambda worktree: removed_checkouts.append(worktree.id),
    )
    monkeypatch.setattr(
        coordinator_module,
        "delete_generated_branch",
        lambda worktree: deleted_branches.append(worktree.id),
    )

    result = finalize_coordinator(_finalization_state(), approved=True)

    assert result.stage == CoordinatorStages.COMPLETED
    assert removed_checkouts == ["backend", "integration"]
    assert deleted_branches == ["backend"]


def test_rejected_finalization_removes_checkouts_and_all_branches(monkeypatch):
    removed_checkouts: list[str] = []
    deleted_branches: list[str] = []

    monkeypatch.setattr(
        coordinator_module,
        "remove_worktree_checkout",
        lambda worktree: removed_checkouts.append(worktree.id),
    )
    monkeypatch.setattr(
        coordinator_module,
        "delete_generated_branch",
        lambda worktree: deleted_branches.append(worktree.id),
    )

    result = finalize_coordinator(_finalization_state(), approved=False)

    assert result.stage == CoordinatorStages.REJECTED
    assert removed_checkouts == ["backend", "integration"]
    assert deleted_branches == ["backend", "integration"]
