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
    <section className="w-full overflow-x-hidden rounded-xl border border-line bg-panel p-4 shadow-2xl shadow-black/10 lg:min-h-0 lg:flex-1 lg:overflow-y-auto">
      <h2 className="mb-3 font-semibold tracking-tight">Recent workflows</h2>
      {workflows && workflows.length > 0 && (
        <div className="flex flex-col gap-2">
          {workflows.map((workflow) => (
            <article key={workflow.id} className="min-w-0 rounded-lg border border-line bg-panel-muted p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className="rounded-full border border-line px-2 py-0.5 text-[11px] font-medium text-copy-muted">
                  {workflow.status.replaceAll("_", " ")}
                </span>
                <time className="text-xs text-copy-muted">
                  {new Date(workflow.created_at).toLocaleDateString()}
                </time>
              </div>
              <p className="line-clamp-2 text-sm font-medium">{workflow.objective}</p>
              <p className="mt-1 truncate font-mono text-[11px] text-copy-muted">
                {workflow.id}
              </p>
              <button
                onClick={() => load(workflow.id)}
                className="mt-3 rounded-md border border-line px-2.5 py-1.5 text-xs font-medium transition hover:bg-zinc-800 disabled:opacity-50"
                disabled={isLoading}
              >
                {isLoading ? "Loading…" : "Open workflow"}
              </button>
            </article>
          ))}
        </div>
      )}
    </section>
  );
};

export default WorkflowsList;
