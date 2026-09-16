from enum import StrEnum
from pathlib import Path
from typing import Any

from agents import Agent, ApplyPatchTool, Runner, RunResult, RunState
from pydantic import BaseModel, Field

from app.agents.approvals import approval_request
from app.schemas.schemas import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalResolution,
    Workstream,
)
from app.tools.agent_tools import (
    make_git_diff_tool,
    make_list_files_tool,
    make_read_file_tool,
    make_run_tests_tool,
    make_search_code_tool,
    make_workspace_info_tool,
)
from app.tools.editor import RepositoryEditor

MAX_AGENT_TURNS = 7


class WorkerError(Exception):
    """A worker failed."""


class WorkExecutionStatus(StrEnum):
    COMPLETED = "completed"
    PENDING_APPROVAL = "pending_approval"


class WorkerOutput(BaseModel):
    work_notes: str


class WorkerInput(BaseModel):
    """The approved requirements and one worker's assigned portion of them."""

    workstream: Workstream


class WorkExecution(BaseModel):
    """Application-facing result of running or resuming the work."""

    status: WorkExecutionStatus
    output: WorkerOutput | None = None
    run_state: dict[str, Any] | None = None
    approval_requests: list[ApprovalRequest] = Field(default_factory=list)


def make_worker(trusted_root: Path) -> Agent:
    """Create a worker agent bound to one worktree."""
    scoped_editing_tool = ApplyPatchTool(
        editor=RepositoryEditor(trusted_root), needs_approval=True
    )
    return Agent(
        name="Worker",
        instructions=(
            "You are a software implementation worker. Inspect the assigned "
            "repository workspace before editing. Implement only the supplied "
            "work assignment, follow its approved plan, acceptance criteria, "
            "shared contracts, and review feedback, and keep changes focused. "
            "Return concise work notes describing the result."
        ),
        model="gpt-5.6-luna",
        output_type=WorkerOutput,
        tools=[
            scoped_editing_tool,
            make_workspace_info_tool(trusted_root),
            make_list_files_tool(trusted_root),
            make_search_code_tool(trusted_root),
            make_read_file_tool(trusted_root),
            make_git_diff_tool(trusted_root),
            make_run_tests_tool(trusted_root),
        ],
    )


async def invoke_worker(
    trusted_root: Path,
    worker_input: WorkerInput,
) -> WorkExecution:
    try:
        agent = make_worker(trusted_root)
        result = await Runner.run(
            agent,
            worker_input.model_dump_json(),
            max_turns=MAX_AGENT_TURNS,
        )
        return _work_execution(result)
    except WorkerError:
        raise
    except Exception as exc:
        raise WorkerError("Failed to invoke worker") from exc


async def resume_worker(
    trusted_root: Path,
    run_state: dict[str, Any],
    resolutions: dict[str, ApprovalResolution],
) -> WorkExecution:
    """Resume a worker after all requested tool decisions are available."""
    try:
        agent = make_worker(trusted_root)
        state = await RunState.from_json(agent, run_state)

        for interruption in state.get_interruptions():
            call_id = interruption.call_id
            resolution = resolutions.get(call_id or "")
            if resolution is None or resolution.decision == ApprovalDecision.Pending:
                raise WorkerError(
                    "Every tool approval needs a decision before resuming."
                )
            if resolution.decision == ApprovalDecision.Approved:
                state.approve(interruption)
            else:
                state.reject(
                    interruption, rejection_message=resolution.rejection_message
                )
        result = await Runner.run(agent, state)
        return _work_execution(result)
    except WorkerError:
        raise
    except Exception as exc:
        raise WorkerError("Worker could not resume") from exc


def _work_execution(result: RunResult) -> WorkExecution:
    if result.interruptions:
        state = result.to_state()
        return WorkExecution(
            status=WorkExecutionStatus.PENDING_APPROVAL,
            run_state=state.to_json(),
            approval_requests=[approval_request(item) for item in result.interruptions],
        )

    output = result.final_output
    if not isinstance(output, WorkerOutput):
        raise WorkerError("Implementer finished without structured output.")

    return WorkExecution(
        status=WorkExecutionStatus.COMPLETED,
        output=output,
    )
