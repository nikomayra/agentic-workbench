import type { ReactNode } from "react";
import type { Plan } from "@/types/types";

type PlanViewProps = {
  plan: Plan | null;
};

const PlanView = ({ plan }: PlanViewProps): ReactNode => {
  return (
    <>
      {plan && (
        <>
          <h2>{plan.summary}</h2>
          <br />
          {plan.steps.map((step, index) => (
            <div key={index}>
              <p>
                <b>
                  {index + 1}: {step.title}
                </b>
              </p>
              <p>
                <b>Description:</b> {step.description}
              </p>
              <p>
                <b>Acceptance Criteria:</b> {step.acceptance_criteria}
              </p>
              <br />
            </div>
          ))}
        </>
      )}
    </>
  );
};

export default PlanView;
