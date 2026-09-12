import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import ServerStatus from "@/components/ServerStatus";
import type {
  WorkflowCreate,
  Workflow,
  Approval,
  ApprovalRejectRequest,
} from "@/types/types";
import { ZodError } from "@/types/types";
import type { FinalApprovalRequest } from "@/types/types";
import {
  createWorkflowRun,
  fetchWorkflowRun,
  fetcAllWorkflowRuns,
  fetchAllWorkflowRunApprovalItems,
  approveApprovalItem,
  rejectApprovalItem,
  approveWorkflowRun,
  finalizeWorkflowRun,
} from "@/api/workflowRuns";
import ApprovalsList from "@/components/ApprovalsList";
import NewWorkflowForm from "@/components/NewWorkflowForm";
import WorkflowsList from "@/components/WorkflowsList";
import WorkflowView from "@/components/WorkflowView";

const Dashboard = (): ReactNode => {
  const [Workflows, setWorkflows] = useState<Workflow[] | null>(null);
  const [activeWorkflow, setActiveWorkflow] = useState<Workflow | null>(null);
  const [approvals, setApprovals] = useState<Approval[] | null>(null);
  const [error, setError] = useState<string>("");
  const [isPlanning, setIsPlanning] = useState<boolean>(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isDeciding, setIsDeciding] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const refreshActiveWorkflow = async (workflowId?: string): Promise<void> => {
    const targetId = workflowId ?? activeWorkflow?.id;
    if (!targetId) {
      return;
    }

    setIsRefreshing(true);
    try {
      const [updatedWorkflow, currentApprovals] = await Promise.all([
        fetchWorkflowRun(targetId),
        fetchAllWorkflowRunApprovalItems(targetId),
        refreshWorkflowsList(),
      ]);
      setActiveWorkflow(updatedWorkflow);
      setApprovals(currentApprovals);
    } catch (err) {
      if (err instanceof ZodError) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Unknown error");
      }
    } finally {
      setIsRefreshing(false);
    }
  };

  const refreshWorkflowsList = async (): Promise<void> => {
    try {
      const allWorkflowRuns = await fetcAllWorkflowRuns();
      setWorkflows(allWorkflowRuns);
    } catch (err) {
      if (err instanceof ZodError) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Unknown error");
      }
    }
  };

  useEffect(() => {
    void fetcAllWorkflowRuns()
      .then(setWorkflows)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Unknown error");
      });
  }, []);

  const loadWorkflow = async (workflowId: string): Promise<void> => {
    setIsLoading(true);
    try {
      await refreshActiveWorkflow(workflowId);
    } finally {
      setIsLoading(false);
    }
  };

  const approveWorkflowPlan = async (runId: string): Promise<void> => {
    setIsDeciding(true);
    try {
      await approveWorkflowRun(runId);
    } catch (err) {
      if (err instanceof ZodError) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Unknown error");
      }
    } finally {
      setIsDeciding(false);
    }
    await refreshActiveWorkflow();
  };

  const finalizeWorkflow = async (
    runId: string,
    payload: FinalApprovalRequest,
  ): Promise<void> => {
    setIsDeciding(true);
    try {
      await finalizeWorkflowRun(runId, payload);
    } catch (err) {
      if (err instanceof ZodError) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Unknown error");
      }
    } finally {
      setIsDeciding(false);
    }
    await refreshActiveWorkflow();
  };

  const approveApproval = async (approvalId: string): Promise<void> => {
    setIsDeciding(true);
    try {
      await approveApprovalItem(approvalId);
    } catch (err) {
      if (err instanceof ZodError) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Unknown error");
      }
    } finally {
      setIsDeciding(false);
    }
    await refreshActiveWorkflow();
  };

  const rejectApproval = async (
    approvalId: string,
    msg: string | null = null,
  ): Promise<void> => {
    const payload: ApprovalRejectRequest = {
      rejection_message: msg,
    };
    setIsDeciding(true);
    try {
      await rejectApprovalItem(approvalId, payload);
    } catch (err) {
      if (err instanceof ZodError) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Unknown error");
      }
    } finally {
      setIsDeciding(false);
    }
    await refreshActiveWorkflow();
  };

  const createWorkflow = async (objective: string): Promise<void> => {
    const payload: WorkflowCreate = {
      objective,
    };
    try {
      setIsPlanning(true);
      const workflow = await createWorkflowRun(payload);
      setActiveWorkflow(workflow);
      setApprovals([]);
      await refreshWorkflowsList();
    } catch (err) {
      if (err instanceof ZodError) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Unknown error");
      }
    } finally {
      setIsPlanning(false);
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 lg:overflow-hidden">
      <ServerStatus />
      {error && <p>{error}</p>}
      <button
        onClick={() => refreshActiveWorkflow()}
        disabled={isRefreshing}
        className="self-start rounded-lg bg-violet-800 p-2 hover:bg-violet-600 disabled:opacity-50"
      >
        {isRefreshing ? "Refreshing..." : "Refresh active Workflow + Approvals"}
      </button>

      <div className="flex min-h-0 flex-1 flex-col gap-4 lg:flex-row lg:items-stretch lg:overflow-hidden">
        <div className="flex min-h-0 w-full flex-col gap-4 lg:w-80 lg:shrink-0">
          <NewWorkflowForm
            createWorkflow={createWorkflow}
            isPlanning={isPlanning}
          />
          <WorkflowsList
            workflows={Workflows}
            load={loadWorkflow}
            isLoading={isLoading}
          />
        </div>

        <div className="min-w-0 w-full lg:flex lg:min-h-0 lg:flex-1 lg:overflow-hidden">
          <WorkflowView
            workflow={activeWorkflow}
            approveWorkflowPlan={approveWorkflowPlan}
            finalizeWorkflow={finalizeWorkflow}
            isDeciding={isDeciding}
          />
        </div>

        <div className="min-w-0 w-full lg:flex lg:min-h-0 lg:w-96 lg:shrink-0 lg:overflow-hidden">
          <ApprovalsList
            approvals={approvals}
            approve={approveApproval}
            reject={rejectApproval}
            isDeciding={isDeciding}
          />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
