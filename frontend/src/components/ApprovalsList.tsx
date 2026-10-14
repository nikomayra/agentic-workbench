import type { ReactNode } from "react";
import { useState } from "react";
import type { Approval } from "@/types/types";

type ApprovalsListProps = {
  approvals: Approval[] | null;
  approve: (approvalId: string) => Promise<void>;
  reject: (approvalId: string, msg: string | undefined) => Promise<void>;
  isDeciding: boolean;
};

const ApprovalsList = ({
  approvals,
  approve,
  reject,
  isDeciding,
}: ApprovalsListProps): ReactNode => {
  const [rejectMsg, setRejectMsg] = useState<string | undefined>();

  const handleChange = (
    e: React.ChangeEvent<HTMLTextAreaElement, HTMLTextAreaElement>,
  ) => {
    setRejectMsg(e.target.value);
  };

  return (
    <section className="flex min-w-0 w-full flex-col gap-3 rounded-xl border border-line bg-panel p-4 shadow-2xl shadow-black/10 lg:min-h-0 lg:flex-1 lg:overflow-y-auto">
      <div>
        <h2 className="font-semibold tracking-tight">Tool approvals</h2>
        <p className="mt-1 text-sm text-copy-muted">
          Review guarded repository edits before execution continues.
        </p>
      </div>
      {(!approvals || approvals.length === 0) && (
        <p className="rounded-lg border border-dashed border-line p-4 text-sm text-copy-muted">
          No approval requests for this workflow.
        </p>
      )}
      {approvals && approvals.length > 0 && (
        <div className="flex flex-col gap-3">
          {approvals.map((approval) => (
            <article
              key={approval.id}
              className="min-w-0 rounded-lg border border-line bg-panel-muted p-4 text-sm"
            >
              <div className="flex items-center justify-between gap-2">
                <p className="font-medium">{approval.tool_name}</p>
                <span className="rounded-full border border-line px-2 py-0.5 text-[11px] capitalize text-copy-muted">
                  {approval.decision}
                </span>
              </div>
              <p className="mt-2 text-copy-muted">{approval.summary}</p>
              <div className="mt-3 border-t border-line pt-3 font-mono text-xs text-copy-muted">
                {Object.entries(approval.details).map(([key, value]) => (
                  <p key={key} className="wrap-break-word whitespace-pre-wrap">
                    {key}: {String(value)}
                  </p>
                ))}
              </div>
              {approval.decision === "pending" && (
                <div className="flex flex-col gap-2">
                  <textarea
                    onChange={handleChange}
                    value={rejectMsg}
                    placeholder="Optional rejection guidance"
                    className="min-h-20 rounded-md border border-line bg-canvas p-2 text-sm outline-none focus:border-zinc-500"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => approve(approval.id)}
                      className="flex-1 rounded-md bg-copy px-3 py-2 text-sm font-semibold text-canvas hover:bg-zinc-200"
                      disabled={isDeciding}
                    >
                      {isDeciding ? "Approving..." : "Approve"}
                    </button>
                    <button
                      onClick={() => reject(approval.id, rejectMsg)}
                      className="flex-1 rounded-md border border-rose-800 px-3 py-2 text-sm font-medium text-rose-200 hover:bg-rose-950"
                      disabled={isDeciding}
                    >
                      {isDeciding ? "Rejecting..." : "Reject"}
                    </button>
                  </div>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
};

export default ApprovalsList;
