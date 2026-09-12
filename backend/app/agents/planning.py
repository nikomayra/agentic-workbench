from pathlib import Path

from agents import Agent, Runner
from agents.mcp import MCPServerStdio

from app.mcp.repository_connection import make_repository_connection
from app.schemas.schemas import (
    ExecutionPlan,
    Plan,
    Workstream,
)

MAX_AGENT_TURNS = 5


class PlannerError(Exception):
    """The planner failed to produce a valid plan."""


def make_planner(mcp_server: MCPServerStdio) -> Agent:
    planner_agent = Agent(
        name="Software Engineering Planner",
        instructions=(
            "Inspect the permitted repository before producing a plan. "
            "Do not invent file paths or line numbers. "
        ),
        model="gpt-5.6-luna",
        output_type=Plan,
        mcp_servers=[mcp_server],
    )

    return planner_agent


async def invoke_planner(trusted_root: Path, objective: str) -> Plan:
    try:
        async with make_repository_connection(trusted_root) as mcp_server:
            result = await Runner.run(
                make_planner(mcp_server),
                objective,
                max_turns=MAX_AGENT_TURNS,
            )
    except Exception as exc:
        raise PlannerError("Planner could not produce a plan") from exc

    return result.final_output


def make_decomposer(mcp_server: MCPServerStdio) -> Agent:
    decomposer_agent = Agent(
        name="Software Engineering Plan Decomposer",
        instructions=(
            "Inspect the permitted repository before producing a plan. "
            "Do not invent file paths or line numbers. "
            "Decompose the plan into independent workstreams when applicable. "
            "Define any contracts that the workstreams must share. If the work "
            "cannot be divided safely, return one workstream covering the full plan."
        ),
        model="gpt-5.6-luna",
        output_type=ExecutionPlan,
        mcp_servers=[mcp_server],
    )
    return decomposer_agent


async def invoke_decomposer(trusted_root: Path, plan: Plan) -> ExecutionPlan:
    """Convert an approved plan into a validated execution plan."""
    try:
        async with make_repository_connection(trusted_root) as mcp_server:
            result = await Runner.run(
                make_decomposer(mcp_server),
                plan.model_dump_json(),
                max_turns=MAX_AGENT_TURNS,
            )
    except Exception as exc:
        raise PlannerError("Planner could not decompose the approved plan") from exc

    return _execution_plan_for_work(plan, result.final_output)


def _execution_plan_for_work(
    approved_plan: Plan,
    proposed_plan: ExecutionPlan,
) -> ExecutionPlan:
    """Use a plausible decomposition or deterministically fall back to one worker."""
    if len(proposed_plan.workstreams) == 1 or _can_run_in_parallel(proposed_plan):
        return proposed_plan

    task = "\n".join(
        f"{step.title}: {step.description}" for step in approved_plan.steps
    )
    return ExecutionPlan(
        workstreams=[
            Workstream(
                name="full-plan",
                task=task or approved_plan.summary,
                intended_paths=["."],
                acceptance_criteria=[
                    step.acceptance_criteria for step in approved_plan.steps
                ],
            )
        ]
    )


def _can_run_in_parallel(execution_plan: ExecutionPlan) -> bool:
    """Accept multiple workstreams only when their declared paths do not overlap."""
    if len(execution_plan.workstreams) <= 1:
        return False

    seen_paths: set[str] = set()
    for workstream in execution_plan.workstreams:
        if not workstream.intended_paths:
            return False
        for path in workstream.intended_paths:
            if path in seen_paths:
                return False
            seen_paths.add(path)
    return True
