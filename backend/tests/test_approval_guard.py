import asyncio

from agents import (
    Agent,
    ApplyPatchOperation,
    ApplyPatchResult,
    ApplyPatchTool,
    Runner,
    RunState,
)
from agents.testing import ScriptedModel, assistant_message
from openai.types.responses import ResponseApplyPatchToolCall
from openai.types.responses.response_apply_patch_tool_call import OperationCreateFile

from app.agents.approvals import approval_request


class RecordingEditor:
    """Test editor that records whether a protected write actually executed."""

    def __init__(self):
        self.executed_operations = 0

    def create_file(self, operation: ApplyPatchOperation) -> ApplyPatchResult:
        self.executed_operations += 1
        return ApplyPatchResult(output="created")

    def update_file(self, operation: ApplyPatchOperation) -> ApplyPatchResult:
        self.executed_operations += 1
        return ApplyPatchResult(output="updated")

    def delete_file(self, operation: ApplyPatchOperation) -> ApplyPatchResult:
        self.executed_operations += 1
        return ApplyPatchResult(output="deleted")


def test_rejected_patch_never_reaches_editor():
    model = ScriptedModel(
        [
            [
                ResponseApplyPatchToolCall(
                    id="patch-item-1",
                    type="apply_patch_call",
                    call_id="patch-call-1",
                    status="completed",
                    operation=OperationCreateFile(
                        type="create_file",
                        path="rejected.txt",
                        diff="*** Begin Patch\n*** Add File: rejected.txt\n+blocked\n*** End Patch",
                    ),
                )
            ],
            [assistant_message("The requested edit was rejected.")],
        ]
    )
    editor = RecordingEditor()
    agent = Agent(
        name="Approval guard test agent",
        instructions="Request the scripted edit.",
        model=model,
        tools=[ApplyPatchTool(editor=editor, needs_approval=True)],
    )

    async def run_and_reject():
        result = await Runner.run(agent, "Create rejected.txt")
        assert len(result.interruptions) == 1
        assert editor.executed_operations == 0

        request = approval_request(result.interruptions[0])
        assert request.summary == "Create rejected.txt"
        assert request.details["type"] == "create_file"

        saved_state = result.to_state().to_json()
        restored_state = await RunState.from_json(agent, saved_state)
        restored_state.reject(restored_state.get_interruptions()[0])
        await Runner.run(agent, restored_state)

    asyncio.run(run_and_reject())

    assert editor.executed_operations == 0
    model.assert_complete()
