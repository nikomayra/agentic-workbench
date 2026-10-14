import type { ReactNode } from "react";
import type { Plan } from "@/types/types";

type PlanViewProps = {
  plan: Plan | null;
};

const PlanView = ({ plan }: PlanViewProps): ReactNode => {
  return (
    <div>
      {!plan && <p className="text-sm text-copy-muted">The plan has not been generated yet.</p>}
      {plan && (
        <div>
          <p className="mb-4 text-sm leading-6 text-zinc-300">{plan.summary}</p>
          <ol className="space-y-3">
          {plan.steps.map((step, index) => (
            <li key={index} className="rounded-lg border border-line bg-panel-muted p-4">
              <p className="font-medium">
                <span className="mr-2 font-mono text-xs text-copy-muted">
                  {String(index + 1).padStart(2, "0")}
                </span>
                {step.title}
              </p>
              <p className="mt-2 text-sm leading-6 text-copy-muted">
                {step.description}
              </p>
              <p className="mt-3 text-xs font-medium text-zinc-300">
                Acceptance: {step.acceptance_criteria}
              </p>
            </li>
          ))}
          </ol>
        </div>
      )}
    </div>
  );
};

export default PlanView;
