import type { ReactNode } from "react";
import type { Workflow } from "@/types/types";

type WorkflowsListProps = {
  workflows: Workflow[] | null;
  load: (workflowId: string) => Promise<void>;
  isLoading: boolean;
};

const WorkflowsList = ({
  workflows,
  load,
  isLoading,
}: WorkflowsListProps): ReactNode => {
  return (
    <section className="w-full overflow-x-hidden rounded-2xl border-2 p-4 lg:min-h-0 lg:flex-1 lg:overflow-y-auto">
      <h2 className="mb-3 text-2xl">Workflows</h2>
      {workflows && workflows.length > 0 && (
        <div className="flex flex-col gap-3">
          {workflows.map((workflow) => (
            <article key={workflow.id} className="min-w-0 border-b-2 pb-3">
              <p className="break-all">ID: {workflow.id}</p>
              <p className="break-all">Status: {workflow.status}</p>
              <p className="wrap-break-word">Objective: {workflow.objective}</p>
              <p className="wrap-break-word">
                Plan Summary: {workflow.plan?.summary}
              </p>
              <p>
                Created_at: {new Date(workflow.created_at).toLocaleString()}
              </p>
              <button
                onClick={() => load(workflow.id)}
                className="rounded-lg bg-emerald-800 p-1 hover:bg-emerald-600 disabled:opacity-50"
                disabled={isLoading}
              >
                {isLoading ? "Loading..." : "Load"}
              </button>
            </article>
          ))}
        </div>
      )}
    </section>
  );
};

export default WorkflowsList;
