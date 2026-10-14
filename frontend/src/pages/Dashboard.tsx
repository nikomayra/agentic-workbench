import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import ServerStatus from "@/components/ServerStatus";
import type {
  WorkflowCreate,
  GitHubWorkflowCreate,
  Workflow,
  Approval,
  ApprovalRejectRequest,
} from "@/types/types";
import { ZodError } from "@/types/types";
import type { FinalApprovalRequest } from "@/types/types";
import {
  createWorkflowRun,
  createGitHubWorkflowRun,
  fetchWorkflowRun,
  fetcAllWorkflowRuns,
  fetchAllWorkflowRunApprovalItems,
  approveApprovalItem,
  rejectApprovalItem,
  approveWorkflowRun,
  finalizeWorkflowRun,
  subscribeToWorkflowRun,
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
  const [liveUpdateError, setLiveUpdateError] = useState<string>("");
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

  useEffect(() => {
    const workflowId = activeWorkflow?.id;
    if (!workflowId) {
      return;
    }

    const source = subscribeToWorkflowRun(
      workflowId,
      (workflow) => {
        setLiveUpdateError("");
        setActiveWorkflow(workflow);
        setWorkflows((current) => {
          if (!current) {
            return [workflow];
          }

          const workflowExists = current.some(
            (item) => item.id === workflow.id,
          );
          if (!workflowExists) {
            return [workflow, ...current];
          }

          return current.map((item) =>
            item.id === workflow.id ? workflow : item,
          );
        });

        void fetchAllWorkflowRunApprovalItems(workflow.id)
          .then(setApprovals)
          .catch((err: unknown) => {
            setLiveUpdateError(
              err instanceof Error
                ? err.message
                : "Failed to refresh workflow approvals",
            );
          });
      },
      (err: unknown) =>
        setLiveUpdateError(
          err instanceof Error
            ? err.message
            : "Failed to connect to live updates",
        ),
    );

    return () => source.close();
  }, [activeWorkflow?.id]);

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

  const createWorkflow = async (payload: WorkflowCreate): Promise<void> => {
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

  const createGitHubWorkflow = async (
    payload: GitHubWorkflowCreate,
  ): Promise<void> => {
    try {
      setIsPlanning(true);
      const workflow = await createGitHubWorkflowRun(payload);
      setActiveWorkflow(workflow);
      setApprovals([]);
      await refreshWorkflowsList();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setIsPlanning(false);
    }
  };

  return (
    <div className="flex min-h-0 w-full flex-1 flex-col gap-4 lg:overflow-hidden">
      <div className="flex items-center justify-between gap-4 rounded-xl border border-line bg-panel px-4 py-3 shadow-2xl shadow-black/10">
        <ServerStatus />
        <button
          onClick={() => refreshActiveWorkflow()}
          disabled={isRefreshing || !activeWorkflow}
          className="rounded-md border border-line bg-panel-muted px-3 py-1.5 text-sm font-medium transition hover:border-zinc-600 hover:bg-zinc-800 disabled:opacity-40"
        >
          {isRefreshing ? "Refreshing…" : "Refresh"}
        </button>
      </div>
      {error && (
        <p role="alert" className="rounded-lg border border-rose-900/70 bg-rose-950/40 px-4 py-3 text-sm text-rose-200">
          {error}
        </p>
      )}
      {liveUpdateError && (
        <p className="rounded-lg border border-amber-900/70 bg-amber-950/30 px-4 py-3 text-sm text-amber-200">
          {liveUpdateError}
        </p>
      )}

      <div className="flex min-h-0 flex-1 flex-col gap-4 lg:flex-row lg:items-stretch lg:overflow-hidden">
        <div className="flex min-h-0 w-full flex-col gap-4 lg:w-[23rem] lg:shrink-0">
          <NewWorkflowForm
            createWorkflow={createWorkflow}
            createGitHubWorkflow={createGitHubWorkflow}
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
