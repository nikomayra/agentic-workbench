import { useState } from "react";
import type { ReactNode, SubmitEvent } from "react";
import type { GitHubWorkflowCreate, WorkflowCreate } from "@/types/types";
import InfoTooltip from "@/components/ui/InfoTooltip";

type NewWorkflowFormProps = {
  createWorkflow: (payload: WorkflowCreate) => Promise<void>;
  createGitHubWorkflow: (payload: GitHubWorkflowCreate) => Promise<void>;
  isPlanning: boolean;
};

const NewWorkflowForm = ({
  createWorkflow,
  createGitHubWorkflow,
  isPlanning,
}: NewWorkflowFormProps): ReactNode => {
  const [objective, setObjective] = useState<string>("");
  const [source, setSource] = useState<"github" | "custom">("github");
  const [issueUrl, setIssueUrl] = useState<string>("");
  const [cloneUrl, setCloneUrl] = useState<string>("");
  const [baseBranch, setBaseBranch] = useState<string>("main");
  const [testCommand, setTestCommand] = useState<string>("");
  const [testWorkingDirectory, setTestWorkingDirectory] =
    useState<string>(".");

  const handleSubmit = async (
    event: SubmitEvent<HTMLFormElement>,
  ): Promise<void> => {
    event.preventDefault();
    const testConfiguration = {
      test_command: testCommand.trim().split(/\s+/),
      test_working_directory: testWorkingDirectory,
    };
    if (source === "github") {
      await createGitHubWorkflow({
        issue_url: issueUrl,
        ...testConfiguration,
      });
      return;
    }

    await createWorkflow({
      objective,
      repository_target: {
        clone_url: cloneUrl,
        base_branch: baseBranch,
        ...testConfiguration,
      },
    });
  };

  return (
    <section className="w-full rounded-xl border border-line bg-panel p-4 shadow-2xl shadow-black/10 xl:min-h-0 xl:flex-1 xl:overflow-y-auto">
      <div className="mb-4">
        <h2 className="font-semibold tracking-tight">New workflow</h2>
        <p className="mt-1 text-sm text-copy-muted">
          Start from a GitHub issue or a custom repository objective.
        </p>
      </div>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <div className="flex items-center gap-1.5">
          <label htmlFor="workflow-source" className="text-xs font-medium text-copy-muted">
            Workflow source
          </label>
          <InfoTooltip label="About workflow sources">
            GitHub issue workflows can publish a draft pull request after final
            approval. Custom objectives use repository details you provide and
            keep the completed branch in the managed local workspace.
          </InfoTooltip>
        </div>
        <select
          id="workflow-source"
          value={source}
          onChange={(event) =>
            setSource(event.target.value as "github" | "custom")
          }
          className="w-full rounded-md border border-line bg-canvas px-3 py-2 text-sm outline-none transition focus:border-zinc-500"
        >
          <option value="github">GitHub issue</option>
          <option value="custom">Custom objective</option>
        </select>

        {source === "github" ? (
          <>
            <label htmlFor="issue-url" className="text-xs font-medium text-copy-muted">
              GitHub issue URL
            </label>
            <input
              id="issue-url"
              type="url"
              value={issueUrl}
              onChange={(event) => setIssueUrl(event.target.value)}
              placeholder="https://github.com/owner/repository/issues/123"
              required
              className="w-full rounded-md border border-line bg-canvas px-3 py-2 text-sm outline-none transition focus:border-zinc-500"
            />
            <p className="text-xs leading-5 text-copy-muted">
              The repository must already have a base branch with at least one
              commit.
            </p>
          </>
        ) : (
          <>
            <label htmlFor="objective" className="text-xs font-medium text-copy-muted">
              Objective
            </label>
            <textarea
              id="objective"
              value={objective}
              onChange={(event) => setObjective(event.target.value)}
              placeholder="Describe objective..."
              required
              className="min-h-24 w-full resize-y rounded-md border border-line bg-canvas px-3 py-2 text-sm outline-none transition focus:border-zinc-500"
            />
            <label htmlFor="clone-url" className="text-xs font-medium text-copy-muted">
              Repository clone URL or local Git path
            </label>
            <input
              id="clone-url"
              value={cloneUrl}
              onChange={(event) => setCloneUrl(event.target.value)}
              required
              className="w-full rounded-md border border-line bg-canvas px-3 py-2 text-sm outline-none transition focus:border-zinc-500"
            />
            <label htmlFor="base-branch" className="text-xs font-medium text-copy-muted">
              Base branch
            </label>
            <input
              id="base-branch"
              value={baseBranch}
              onChange={(event) => setBaseBranch(event.target.value)}
              required
              className="w-full rounded-md border border-line bg-canvas px-3 py-2 text-sm outline-none transition focus:border-zinc-500"
            />
          </>
        )}
        <div className="flex items-center gap-1.5">
          <label htmlFor="test-command" className="text-xs font-medium text-copy-muted">
            Test command
          </label>
          <InfoTooltip label="About the test command">
            Runs from the integration worktree after changes are committed.
            Enter an executable and arguments only—shell pipes and redirects
            are not supported.
          </InfoTooltip>
        </div>
        <input
          id="test-command"
          value={testCommand}
          onChange={(event) => setTestCommand(event.target.value)}
          placeholder="uv run pytest -q"
          required
          className="w-full rounded-md border border-line bg-canvas px-3 py-2 font-mono text-sm outline-none transition focus:border-zinc-500"
        />
        <div className="flex items-center gap-1.5">
          <label
            htmlFor="test-working-directory"
            className="text-xs font-medium text-copy-muted"
          >
            Test working directory
          </label>
          <InfoTooltip label="About the test working directory">
            This path is relative to the repository root. Use a single period
            to run the command from the root.
          </InfoTooltip>
        </div>
        <input
          id="test-working-directory"
          value={testWorkingDirectory}
          onChange={(event) => setTestWorkingDirectory(event.target.value)}
          required
          className="w-full rounded-md border border-line bg-canvas px-3 py-2 font-mono text-sm outline-none transition focus:border-zinc-500"
        />
        <button
          type="submit"
          disabled={isPlanning}
          className="mt-1 rounded-md bg-copy px-3 py-2 text-sm font-semibold text-canvas transition hover:bg-zinc-200 disabled:opacity-50"
        >
          {isPlanning ? "Starting workflow…" : "Start workflow"}
        </button>
      </form>
    </section>
  );
};

export default NewWorkflowForm;
