import type { ReactNode } from "react";
import type { Workflow, FinalApprovalRequest } from "@/types/types";
import PlanView from "@/components/PlanView";

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
  const workflowStatusHandler = (workflow: Workflow): ReactNode => {
    if (workflow.status == "pending_final_approval") {
      return (
        <>
          <p>Status: {workflow.status}</p>
          <p>Automated tests and review completed.</p>
          <div className="flex min-w-0 w-full flex-row">
            <button
              onClick={() => finalizeWorkflow(workflow.id, { approved: true })}
              className="bg-emerald-800 hover:bg-emerald-600 rounded-lg p-1"
              disabled={isDeciding}
            >
              {isDeciding ? "Approving..." : "Approve Final Result"}
            </button>
            <button
              onClick={() => finalizeWorkflow(workflow.id, { approved: false })}
              className="bg-pink-800 hover:bg-pink-600 rounded-lg p-1"
              disabled={isDeciding}
            >
              {isDeciding ? "Rejecting..." : "Reject Final Result"}
            </button>
          </div>
        </>
      );
    } else {
      return <p>Status: {workflow.status}</p>;
    }
  };

  return (
    <>
      {workflow && (
        <div className="flex min-w-0 w-full flex-col rounded-2xl border-2 p-2 lg:min-h-0 lg:flex-1 lg:overflow-y-auto">
          <p className="text-2xl">Workflow:</p>
          <div className="border-b-2">
            <p className="break-all">ID: {workflow.id}</p>
            <p className="wrap-break-word">Objective: {workflow.objective}</p>
            {workflowStatusHandler(workflow)}
            {workflow.error && <p>Error: {workflow.error}</p>}
          </div>
          <div>
            <p className="text-xl">Plan:</p>
            <PlanView plan={workflow.plan} />
            {workflow.status === "pending_plan_approval" && (
              <button
                onClick={() => approveWorkflowPlan(workflow.id)}
                className="bg-emerald-800 hover:bg-emerald-600 rounded-lg p-1"
                disabled={isDeciding}
              >
                {isDeciding ? "Approving..." : "Approve"}
              </button>
            )}
          </div>
        </div>
      )}
    </>
  );
};

export default WorkflowView;
