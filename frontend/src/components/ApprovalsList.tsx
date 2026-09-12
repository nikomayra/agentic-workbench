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
    <>
      {approvals && approvals.length > 0 && (
        <section className="flex min-w-0 w-full flex-col gap-3 rounded-2xl border-2 p-2 lg:min-h-0 lg:flex-1 lg:overflow-y-auto">
          <p className="text-2xl">Approvals:</p>
          {approvals.map((approval) => (
            <article key={approval.id} className="min-w-0 border-b-2 pb-3">
              <p>ID: {approval.id}</p>
              <p>Call_ID: {approval.call_id}</p>
              <p>Tool_Name: {approval.tool_name}</p>
              <p>Summary: {approval.summary}</p>
              <p>Decision: {approval.decision}</p>
              <p>Rejection_Message: {approval.rejection_message}</p>
              <p>
                Created_at: {new Date(approval.created_at).toLocaleString()}
              </p>
              <p>
                Decided_at:{" "}
                {approval.decided_at &&
                  new Date(approval.decided_at).toLocaleString()}
              </p>
              <p>Details: </p>
              {Object.entries(approval.details).map(([key, value]) => (
                <p key={key} className="wrap-break-word whitespace-pre-wrap">
                  {key}: {String(value)}
                </p>
              ))}
              {approval.decision === "pending" && (
                <div className="flex flex-col gap-2">
                  <button
                    onClick={() => approve(approval.id)}
                    className="bg-emerald-800 rounded-lg p-1 hover:bg-emerald-600"
                    disabled={isDeciding}
                  >
                    {isDeciding ? "Approving..." : "Approve"}
                  </button>
                  <button
                    onClick={() => reject(approval.id, rejectMsg)}
                    className="bg-rose-800 rounded-lg p-1 hover:bg-rose-600"
                    disabled={isDeciding}
                  >
                    {isDeciding ? "Rejecting..." : "Reject"}
                  </button>
                  <textarea
                    onChange={handleChange}
                    value={rejectMsg}
                    placeholder="Add optional rejection message..."
                  ></textarea>
                </div>
              )}
            </article>
          ))}
        </section>
      )}
    </>
  );
};

export default ApprovalsList;
