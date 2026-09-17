import asyncio
from pathlib import Path
from types import SimpleNamespace

import evals.run_evals as evals_module
from app.agents.workers import WorkExecution, WorkExecutionStatus
from evals.models import EvalConfiguration, ExecutionFacts
from evals.observability import EvalTraceProcessor
from evals.run_evals import evaluate_current_workflow
from tests.factories import (
    construct_eval_case,
    construct_trace_metrics,
    pending_execution,
    worktree,
)


def fake_trace(*_args, **_kwargs):
    class TraceContext:
        def __enter__(self):
            return SimpleNamespace(trace_id="test-trace-id")

        def __exit__(self, *_exc_info):
            return False

    return TraceContext()


def make_trace_processor() -> EvalTraceProcessor:
    """Create a processor with deterministic metrics for the fake trace."""
    processor = EvalTraceProcessor()
    processor.metrics_collection.mapped_metrics["test-trace-id"] = (
        construct_trace_metrics()
    )
    return processor


def test_evaluate_current_workflow_scores_successful_execution(monkeypatch):
    eval_case = construct_eval_case(
        expected_path_prefixes=["backend/"],
        forbidden_path_prefixes=["frontend/"],
    )

    async def fake_execution_mapper(configuration, case):
        assert configuration == EvalConfiguration.FULL_WORKFLOW
        assert case == eval_case
        return ExecutionFacts(
            tests_passed=True,
            changed_paths=[
                Path("backend/app/models.py"),
                Path("backend/tests/test_models.py"),
            ],
        )

    monkeypatch.setattr(evals_module, "_execution_mapper", fake_execution_mapper)
    monkeypatch.setattr(evals_module, "trace", fake_trace)

    result = asyncio.run(
        evaluate_current_workflow(
            EvalConfiguration.FULL_WORKFLOW,
            eval_case,
            make_trace_processor(),
        )
    )

    assert result.case_id == eval_case.id
    assert result.configuration == EvalConfiguration.FULL_WORKFLOW
    assert result.trace_id == "test-trace-id"
    assert result.observation.tests_passed
    assert result.observation.changed_paths == [
        Path("backend/app/models.py"),
        Path("backend/tests/test_models.py"),
    ]
    assert result.passed
    assert result.reasons == []


def test_evaluate_current_workflow_scores_failed_execution(monkeypatch):
    eval_case = construct_eval_case(
        expected_path_prefixes=["backend/"],
        forbidden_path_prefixes=["frontend/"],
    )

    async def fake_execution_mapper(_configuration, _case):
        return ExecutionFacts(
            tests_passed=False,
            changed_paths=[],
            error="RuntimeError: worker failed",
        )

    monkeypatch.setattr(evals_module, "_execution_mapper", fake_execution_mapper)
    monkeypatch.setattr(evals_module, "trace", fake_trace)

    result = asyncio.run(
        evaluate_current_workflow(
            EvalConfiguration.SINGLE_WORKER,
            eval_case,
            make_trace_processor(),
        )
    )

    assert not result.passed
    assert not result.observation.tests_passed
    assert result.observation.changed_paths == []
    assert result.observation.error == "RuntimeError: worker failed"
    assert "Workflow Error: RuntimeError: worker failed" in result.reasons


def test_evaluate_current_workflow_formats_expected_task_group_error(monkeypatch):
    eval_case = construct_eval_case(
        expected_path_prefixes=["backend/"],
        forbidden_path_prefixes=["frontend/"],
    )

    async def fake_execution_mapper(_configuration, _case):
        raise ExceptionGroup(
            "parallel worker failures",
            [evals_module.WorkerError("worker could not resume")],
        )

    monkeypatch.setattr(evals_module, "_execution_mapper", fake_execution_mapper)
    monkeypatch.setattr(evals_module, "trace", fake_trace)

    result = asyncio.run(
        evaluate_current_workflow(
            EvalConfiguration.FULL_WORKFLOW,
            eval_case,
            make_trace_processor(),
        )
    )

    assert not result.passed
    assert result.observation.error == "WorkerError: worker could not resume"


def test_run_worker_until_complete_uses_generated_worktree_root(monkeypatch):
    generated_worktree = worktree("single-worker")
    pending = pending_execution("approval-1")
    completed = WorkExecution(status=WorkExecutionStatus.COMPLETED)
    received_roots = []

    async def fake_invoke_worker(trusted_root, _worker_input):
        received_roots.append(trusted_root)
        return pending

    async def fake_resume_worker(trusted_root, _run_state, _resolutions):
        received_roots.append(trusted_root)
        return completed

    monkeypatch.setattr(evals_module, "invoke_worker", fake_invoke_worker)
    monkeypatch.setattr(evals_module, "resume_worker", fake_resume_worker)

    result = asyncio.run(
        evals_module._run_worker_until_complete(
            evals_module.WorkerInput(
                workstream=evals_module.Workstream(
                    name="backend",
                    task="Implement the requested backend change.",
                    intended_paths=[],
                    acceptance_criteria=["Relevant tests pass."],
                )
            ),
            generated_worktree,
        )
    )

    assert result.status == WorkExecutionStatus.COMPLETED
    assert received_roots == [generated_worktree.path, generated_worktree.path]
