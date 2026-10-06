import { useState } from "react";
import type { ReactNode, SubmitEvent } from "react";
import type { WorkflowCreate } from "@/types/types";

type NewWorkflowFormProps = {
  createWorkflow: (payload: WorkflowCreate) => Promise<void>;
  isPlanning: boolean;
};

const NewWorkflowForm = ({
  createWorkflow,
  isPlanning,
}: NewWorkflowFormProps): ReactNode => {
  const [objective, setObjective] = useState<string>("");
  const [cloneUrl, setCloneUrl] = useState<string>("");
  const [baseBranch, setBaseBranch] = useState<string>("main");
  const [testCommand, setTestCommand] = useState<string>("uv run pytest -q");
  const [testWorkingDirectory, setTestWorkingDirectory] =
    useState<string>("backend");

  const handleSubmit = async (
    event: SubmitEvent<HTMLFormElement>,
  ): Promise<void> => {
    event.preventDefault();
    await createWorkflow({
      objective,
      repository_target: {
        clone_url: cloneUrl,
        base_branch: baseBranch,
        test_command: testCommand.trim().split(/\s+/),
        test_working_directory: testWorkingDirectory,
      },
    });
  };

  return (
    <section className="w-full rounded-2xl border-2 p-4 lg:shrink-0">
      <h2 className="mb-3 text-2xl">New workflow</h2>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <label htmlFor="objective">Objective</label>
        <textarea
          id="objective"
          value={objective}
          onChange={(event) => setObjective(event.target.value)}
          placeholder="Describe objective..."
          required
          className="min-h-24 w-full resize-y rounded-lg border p-2"
        />
        <label htmlFor="clone-url">Repository clone URL or local Git path</label>
        <input
          id="clone-url"
          value={cloneUrl}
          onChange={(event) => setCloneUrl(event.target.value)}
          required
          className="w-full rounded-lg border p-2"
        />
        <label htmlFor="base-branch">Base branch</label>
        <input
          id="base-branch"
          value={baseBranch}
          onChange={(event) => setBaseBranch(event.target.value)}
          required
          className="w-full rounded-lg border p-2"
        />
        <label htmlFor="test-command">Test command</label>
        <input
          id="test-command"
          value={testCommand}
          onChange={(event) => setTestCommand(event.target.value)}
          required
          className="w-full rounded-lg border p-2"
        />
        <label htmlFor="test-working-directory">Test working directory</label>
        <input
          id="test-working-directory"
          value={testWorkingDirectory}
          onChange={(event) => setTestWorkingDirectory(event.target.value)}
          required
          className="w-full rounded-lg border p-2"
        />
        <button
          type="submit"
          disabled={isPlanning}
          className="rounded-lg bg-lime-800 p-2 hover:bg-lime-600 disabled:opacity-50"
        >
          {isPlanning ? "Planning..." : "Submit"}
        </button>
      </form>
    </section>
  );
};

export default NewWorkflowForm;
