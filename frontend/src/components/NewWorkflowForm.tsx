import { useState } from "react";
import type { ReactNode, SubmitEvent } from "react";

type NewWorkflowFormProps = {
  createWorkflow: (objective: string) => Promise<void>;
  isPlanning: boolean;
};

const NewWorkflowForm = ({
  createWorkflow,
  isPlanning,
}: NewWorkflowFormProps): ReactNode => {
  const [objective, setObjective] = useState<string>("");

  const handleSubmit = async (
    event: SubmitEvent<HTMLFormElement>,
  ): Promise<void> => {
    event.preventDefault();
    await createWorkflow(objective);
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
