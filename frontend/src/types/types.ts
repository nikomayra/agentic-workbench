import * as z from "zod";

export const ZodError = z.ZodError;

const PlanStepSchema = z.object({
  title: z.string(),
  description: z.string(),
  acceptance_criteria: z.string(),
});
export type PlanStep = z.infer<typeof PlanStepSchema>;

const PlanSchema = z.object({
  summary: z.string(),
  steps: z.array(PlanStepSchema),
});
export type Plan = z.infer<typeof PlanSchema>;

export const WorkflowStatusSchema = z.enum([
  "cancelled",
  "processing",
  "pending_plan_approval",
  "pending_tool_approval",
  "pending_final_approval",
  "completed",
  "failed",
]);
export type WorkflowStatus = z.infer<typeof WorkflowStatusSchema>;

export const WorkflowResponseSchema = z.object({
  id: z.uuid(),
  objective: z.string(),
  status: WorkflowStatusSchema,
  plan: PlanSchema.nullable(),
  error: z.string().nullable(),
  created_at: z.iso.datetime(),
});
export type Workflow = z.infer<typeof WorkflowResponseSchema>;

export const WorkflowCreateSchema = z.object({
  objective: z.string(),
});
export type WorkflowCreate = z.infer<typeof WorkflowCreateSchema>;

export const FinalApprovalRequestSchema = z.object({
  approved: z.boolean(),
});

export type FinalApprovalRequest = z.infer<typeof FinalApprovalRequestSchema>;

export const ApprovalDecisionSchema = z.enum([
  "pending",
  "approved",
  "rejected",
]);
export type ApprovalDecision = z.infer<typeof ApprovalDecisionSchema>;

export const ApprovalResponseSchema = z.object({
  id: z.uuid(),
  workflow_run_id: z.string(),
  call_id: z.string(),
  tool_name: z.string(),
  summary: z.string(),
  details: z.record(z.string(), z.any()),
  decision: ApprovalDecisionSchema,
  rejection_message: z.string().nullable(),
  created_at: z.iso.datetime(),
  decided_at: z.iso.datetime().nullable(),
});
export type Approval = z.infer<typeof ApprovalResponseSchema>;

export const ApprovalRejectRequestSchema = z.object({
  rejection_message: z.string().nullable(),
});
export type ApprovalRejectRequest = z.infer<typeof ApprovalRejectRequestSchema>;
