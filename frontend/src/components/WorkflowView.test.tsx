import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import WorkflowView from "@/components/WorkflowView";
import type { Workflow } from "@/types/types";

const workflow: Workflow = {
  id: "1567d464-4cf6-4c02-9d1a-fc10d4594861",
  objective: "Validate reservation dates",
  status: "completed",
  repository_target: {
    clone_url: "https://github.com/example/project.git",
    base_branch: "main",
    test_command: ["pytest"],
    test_working_directory: ".",
  },
  issue_url: "https://github.com/example/project/issues/12",
  pull_request_url: "https://github.com/example/project/pull/44",
  plan: null,
  error: null,
  created_at: "2026-10-10T12:00:00Z",
  updated_at: "2026-10-10T12:10:00Z",
};

test("shows the linked GitHub issue and published draft pull request", () => {
  render(
    <WorkflowView
      workflow={workflow}
      approveWorkflowPlan={async () => undefined}
      finalizeWorkflow={async () => undefined}
      isDeciding={false}
    />,
  );

  expect(screen.getByRole("link", { name: /issue #12/i })).toHaveAttribute(
    "href",
    workflow.issue_url,
  );
  expect(
    screen.getByRole("link", { name: /draft pull request/i }),
  ).toHaveAttribute("href", workflow.pull_request_url);
});
