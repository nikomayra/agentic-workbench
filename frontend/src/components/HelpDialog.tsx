import * as Dialog from "@radix-ui/react-dialog";
import {
  CircleHelp,
  GitPullRequest,
  ListChecks,
  ShieldCheck,
  X,
} from "lucide-react";
import type { ReactNode } from "react";

const HelpDialog = (): ReactNode => (
  <Dialog.Root>
    <Dialog.Trigger asChild>
      <button
        type="button"
        className="inline-flex items-center gap-1.5 rounded-md border border-line bg-panel-muted px-3 py-1.5 text-sm font-medium transition hover:border-zinc-600 hover:bg-zinc-800"
      >
        <CircleHelp aria-hidden="true" className="size-4" />
        Help
      </button>
    </Dialog.Trigger>
    <Dialog.Portal>
      <Dialog.Overlay className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm" />
      <Dialog.Content className="fixed top-1/2 left-1/2 z-50 max-h-[85vh] w-[calc(100%-2rem)] max-w-2xl -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-xl border border-line bg-panel p-6 text-copy shadow-2xl focus:outline-none">
        <div className="pr-10">
          <Dialog.Title className="text-xl font-semibold tracking-tight">
            How Agentic Workbench runs
          </Dialog.Title>
          <Dialog.Description className="mt-2 text-sm leading-6 text-copy-muted">
            Give the workbench a Git repository and an objective. It plans,
            edits in isolated worktrees, tests, reviews, and pauses before
            sensitive changes or publication.
          </Dialog.Description>
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          <section className="rounded-lg border border-line bg-panel-muted p-4">
            <div className="flex items-center gap-2 font-medium">
              <GitPullRequest aria-hidden="true" className="size-4" />
              Choose an input
            </div>
            <p className="mt-2 text-sm leading-6 text-copy-muted">
              <strong className="text-copy">GitHub issue</strong> loads the
              issue and repository automatically and can publish an approved
              result as a draft pull request. <strong className="text-copy">Custom objective</strong>{" "}
              uses the repository details you enter and keeps the result local.
            </p>
          </section>

          <section className="rounded-lg border border-line bg-panel-muted p-4">
            <div className="flex items-center gap-2 font-medium">
              <ListChecks aria-hidden="true" className="size-4" />
              Configure validation
            </div>
            <p className="mt-2 text-sm leading-6 text-copy-muted">
              The test command runs after edits are integrated, so it may refer
              to files the workflow is expected to create. Use a command that
              exits on its own; long-running development servers are not tests.
            </p>
          </section>

          <section className="rounded-lg border border-line bg-panel-muted p-4 sm:col-span-2">
            <div className="flex items-center gap-2 font-medium">
              <ShieldCheck aria-hidden="true" className="size-4" />
              Review the checkpoints
            </div>
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm leading-6 text-copy-muted">
              <li>Approve the human-readable plan.</li>
              <li>Approve or reject guarded file edits.</li>
              <li>Wait while the integration result is tested and reviewed.</li>
              <li>Approve the final result to publish a GitHub draft PR.</li>
            </ol>
          </section>
        </div>

        <p className="mt-5 rounded-lg border border-amber-900/70 bg-amber-950/30 px-4 py-3 text-sm leading-6 text-amber-100">
          The repository must already be initialized with a base branch and at
          least one commit. Generated work remains local until final approval.
        </p>

        <Dialog.Close asChild>
          <button
            type="button"
            aria-label="Close help"
            className="absolute top-4 right-4 rounded-md p-2 text-copy-muted transition hover:bg-zinc-800 hover:text-copy focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-400"
          >
            <X aria-hidden="true" className="size-4" />
          </button>
        </Dialog.Close>
      </Dialog.Content>
    </Dialog.Portal>
  </Dialog.Root>
);

export default HelpDialog;
