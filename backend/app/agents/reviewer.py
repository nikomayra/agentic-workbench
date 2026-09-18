from pathlib import Path

from agents import Agent, Runner
from agents.mcp import MCPServerStdio
from mcp.types import TextContent

from app.mcp.repository_connection import make_repository_connection
from app.schemas.schemas import (
    ReviewInput,
    ReviewOutput,
)


class ReviewerError(Exception):
    """The reviewer failed to review implementation."""


def make_reviewer(mcp_server: MCPServerStdio, instructions: str) -> Agent:
    agent_reviewer = Agent(
        name="Software Engineering Reviewer",
        instructions=instructions,
        model="gpt-5.6-luna",
        output_type=ReviewOutput,
        mcp_servers=[mcp_server],
    )
    return agent_reviewer


async def invoke_reviewer(
    trusted_root: Path, review_input: ReviewInput
) -> ReviewOutput:
    try:
        async with make_repository_connection(trusted_root) as mcp_server:
            instructions = await _review_instructions(mcp_server)
            result = await Runner.run(
                make_reviewer(mcp_server, instructions),
                review_input.model_dump_json(),
            )
    except ReviewerError:
        raise
    except Exception as exc:
        raise ReviewerError("Reviewer could not finish review.") from exc
    return result.final_output


async def _review_instructions(mcp_server: MCPServerStdio) -> str:
    """Load and validate the reviewer instructions supplied by the MCP server."""
    prompt = await mcp_server.get_prompt("review_change")
    if not prompt.messages:
        raise ReviewerError("The repository server returned an empty review prompt.")

    content = prompt.messages[0].content
    if not isinstance(content, TextContent):
        raise ReviewerError("The repository server returned a non-text review prompt.")

    return content.text
