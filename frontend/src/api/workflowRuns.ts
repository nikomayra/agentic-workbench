import {
  ApprovalResponseSchema,
  WorkflowResponseSchema,
  type ApprovalRejectRequest,
  type Approval,
  type WorkflowCreate,
  type Workflow,
  type FinalApprovalRequest,
} from "@/types/types";

import * as z from "zod";

const BASE_URL = import.meta.env.VITE_API_BASE_URL;

export const createWorkflowRun = async (
  payload: WorkflowCreate,
): Promise<Workflow> => {
  const response = await fetch(`${BASE_URL}/runs`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error("Failed to generate plan");
  }

  const data: unknown = await response.json();
  return WorkflowResponseSchema.parse(data);
};

export const fetchWorkflowRun = async (run_id: string): Promise<Workflow> => {
  const response = await fetch(`${BASE_URL}/runs/${run_id}`);

  if (!response.ok) {
    throw new Error("Failed to find workflow run");
  }

  const data: unknown = await response.json();
  return WorkflowResponseSchema.parse(data);
};

export const fetcAllWorkflowRuns = async (): Promise<Workflow[]> => {
  const response = await fetch(`${BASE_URL}/runs`);

  if (!response.ok) {
    throw new Error("Failed to find workflow run");
  }

  const data: unknown = await response.json();
  return z.array(WorkflowResponseSchema).parse(data);
};

export const approveWorkflowRun = async (run_id: string): Promise<Workflow> => {
  const response = await fetch(`${BASE_URL}/runs/${run_id}/approve`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error("Failed to approve workflow plan");
  }

  const data: unknown = await response.json();
  return WorkflowResponseSchema.parse(data);
};

export const finalizeWorkflowRun = async (
  run_id: string,
  payload: FinalApprovalRequest,
): Promise<Workflow> => {
  const response = await fetch(`${BASE_URL}/runs/${run_id}/finalize`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error("Failed to finalize workflow plan");
  }

  const data: unknown = await response.json();
  return WorkflowResponseSchema.parse(data);
};

export const fetchAllWorkflowRunApprovalItems = async (
  run_id: string,
): Promise<Approval[]> => {
  const response = await fetch(`${BASE_URL}/runs/${run_id}/approvals`);

  if (!response.ok) {
    throw new Error("Failed to find workflow approvals");
  }

  const data: unknown = await response.json();
  return z.array(ApprovalResponseSchema).parse(data);
};

export const fetchApprovalItem = async (
  approval_id: string,
): Promise<Approval> => {
  const response = await fetch(`${BASE_URL}/approvals/${approval_id}`);

  if (!response.ok) {
    throw new Error("Failed to find approval item");
  }

  const data: unknown = await response.json();
  return ApprovalResponseSchema.parse(data);
};

export const approveApprovalItem = async (
  approval_id: string,
): Promise<Workflow> => {
  const response = await fetch(`${BASE_URL}/approvals/${approval_id}/approve`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error("Failed to approve approval item");
  }

  const data: unknown = await response.json();
  return WorkflowResponseSchema.parse(data);
};

export const rejectApprovalItem = async (
  approval_id: string,
  payload: ApprovalRejectRequest,
): Promise<Workflow> => {
  const response = await fetch(`${BASE_URL}/approvals/${approval_id}/reject`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error("Failed to reject approval item");
  }

  const data: unknown = await response.json();
  return WorkflowResponseSchema.parse(data);
};
