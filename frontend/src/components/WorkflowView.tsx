import type { ReactNode } from "react";
import type { Workflow, FinalApprovalRequest } from "@/types/types";
import PlanView from "@/components/PlanView";

const statusDescriptions: Record<Workflow["status"], string> = {
  cancelled: "The workflow was cancelled.",
  processing: "Agents are implementing, testing, or reviewing the result.",
  pending_plan_approval:
    "Review the proposed plan before implementation starts.",
  queued: "The workflow is waiting for a background worker.",
  pending_tool_approval: "Review the requested file edits to continue.",
  pending_final_approval:
    "Tests and independent review passed. Approve to publish the result.",
  completed: "The workflow completed successfully.",
  failed: "The workflow stopped before publication. See the error below.",
};

type WorkflowViewProps = {
  workflow: Workflow | null;
  approveWorkflowPlan: (runId: string) => Promise<void>;
  finalizeWorkflow: (
    runId: string,
    payload: FinalApprovalRequest,
  ) => Promise<void>;
  isDeciding: boolean;
};

const WorkflowView = ({
  workflow,
  approveWorkflowPlan,
  finalizeWorkflow,
  isDeciding,
}: WorkflowViewProps): ReactNode => {
  const issueNumber = workflow?.issue_url?.split("/").at(-1);

  const workflowStatusHandler = (workflow: Workflow): ReactNode => {
    if (workflow.status == "pending_final_approval") {
      return (
        <>
          <p className="text-sm text-copy-muted">
            Automated tests and independent review completed.
          </p>
          <div className="mt-3 flex min-w-0 w-full flex-wrap gap-2">
            <button
              onClick={() => finalizeWorkflow(workflow.id, { approved: true })}
              className="rounded-md bg-copy px-3 py-2 text-sm font-semibold text-canvas transition hover:bg-zinc-200 disabled:opacity-50"
              disabled={isDeciding}
            >
              {isDeciding ? "Approving..." : "Approve Final Result"}
            </button>
            <button
              onClick={() => finalizeWorkflow(workflow.id, { approved: false })}
              className="rounded-md border border-rose-800 px-3 py-2 text-sm font-medium text-rose-200 transition hover:bg-rose-950 disabled:opacity-50"
              disabled={isDeciding}
            >
              {isDeciding ? "Rejecting..." : "Reject Final Result"}
            </button>
          </div>
        </>
      );
    } else {
      return null;
    }
  };

  return (
    <section className="flex min-w-0 w-full flex-col rounded-xl border border-line bg-panel p-5 shadow-2xl shadow-black/10 xl:min-h-0 xl:flex-1 xl:overflow-y-auto">
      {!workflow && (
        <div className="m-auto max-w-sm text-center">
          <p className="font-medium">No workflow selected</p>
          <p className="mt-2 text-sm text-copy-muted">
            Start a workflow or open one from the recent list.
          </p>
        </div>
      )}
      {workflow && (
        <>
          <div className="border-b border-line pb-5">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-medium tracking-wide text-copy-muted uppercase">
                  Active workflow
                </p>
                <p className="mt-1 font-mono text-xs text-copy-muted">
                  {workflow.id}
                </p>
              </div>
              <span className="rounded-full border border-line bg-panel-muted px-2.5 py-1 text-xs font-medium capitalize">
                {workflow.status.replaceAll("_", " ")}
              </span>
            </div>
            <p className="mb-4 text-sm text-copy-muted">
              {statusDescriptions[workflow.status]}
            </p>
            <h2 className="text-l font-semibold tracking-tight whitespace-pre-wrap">
              {workflow.objective}
            </h2>
            {workflow.issue_url && (
              <a
                href={workflow.issue_url}
                target="_blank"
                rel="noreferrer"
                className="mt-3 inline-block text-sm"
              >
                GitHub issue #{issueNumber}
              </a>
            )}
            {workflow.pull_request_url && (
              <a
                href={workflow.pull_request_url}
                target="_blank"
                rel="noreferrer"
                className="mt-3 ml-4 inline-block text-sm"
              >
                Open draft pull request
              </a>
            )}
            {workflowStatusHandler(workflow)}
            {workflow.error && (
              <p className="mt-4 rounded-lg border border-rose-900/70 bg-rose-950/40 p-3 text-sm text-rose-200">
                {workflow.error}
              </p>
            )}
          </div>
          <div className="pt-5">
            <h3 className="mb-4 font-semibold">Execution plan</h3>
            <PlanView plan={workflow.plan} />
            {workflow.status === "pending_plan_approval" && (
              <button
                onClick={() => approveWorkflowPlan(workflow.id)}
                className="mt-4 rounded-md bg-copy px-3 py-2 text-sm font-semibold text-canvas transition hover:bg-zinc-200 disabled:opacity-50"
                disabled={isDeciding}
              >
                {isDeciding ? "Approving…" : "Approve plan"}
              </button>
            )}
          </div>
        </>
      )}
    </section>
  );
};

export default WorkflowView;
