import asyncio

from mcp.types import TextContent, TextResourceContents

from app.mcp.repository_connection import make_repository_connection
from app.repository.operations import SAMPLE_REPOSITORY_ROOT


def test_repository_server_exposes_and_serves_expected_capabilities():
    async def exercise_server():
        async with make_repository_connection(SAMPLE_REPOSITORY_ROOT) as server:
            tool_names = {tool.name for tool in await server.list_tools()}
            assert {"list_files", "read_file", "search_repo"} <= tool_names

            read_result = await server.call_tool(
                "read_file", {"relative_path": "README.md"}
            )
            assert read_result.is_error is False
            assert isinstance(read_result.content[0], TextContent)
            assert "Reservations (sample app)" in read_result.content[0].text

            search_result = await server.call_tool("search_repo", {"query": "FastAPI"})
            assert search_result.is_error is False
            assert isinstance(search_result.content[0], TextContent)
            assert "backend/app/main.py" in search_result.content[0].text

            resource = await server.read_resource("docs://readme")
            assert isinstance(resource.contents[0], TextResourceContents)
            assert "Reservations (sample app)" in resource.contents[0].text

            prompt = await server.get_prompt("review_change")
            assert isinstance(prompt.messages[0].content, TextContent)
            assert "acceptance criteria" in prompt.messages[0].content.text

    asyncio.run(exercise_server())


def test_repository_server_rejects_a_path_outside_its_root():
    async def attempt_escape():
        async with make_repository_connection(SAMPLE_REPOSITORY_ROOT) as server:
            result = await server.call_tool(
                "read_file", {"relative_path": "../../.env"}
            )
            assert result.is_error is True
            assert isinstance(result.content[0], TextContent)
            assert "outside the permitted repository" in result.content[0].text

    asyncio.run(attempt_escape())
