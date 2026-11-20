import apiClient from "./apiClient";

/*
 * Finance AI employee service.
 *
 * Frontend employee ids (1-8) map to backend agent slugs.
 */

export const AGENT_SLUGS = {
  1: "accounts-payable",
  2: "accounts-receivable",
  3: "invoice-processing",
  4: "reconciliation",
  5: "finance-analyst",
  6: "expense",
  7: "financial-reporting",
  8: "fraud-detection",
};

export async function getAgents() {
  return apiClient("/agents");
}

export async function getAgentDashboard(employeeId) {
  const slug = AGENT_SLUGS[employeeId];

  if (!slug) {
    throw new Error("Unknown AI employee.");
  }

  return apiClient(`/agents/${slug}/dashboard`);
}

/* ---- Invoice review workflow (AP / Invoice Processing) ---- */

export async function approveDocument(documentId) {
  return apiClient(`/documents/${documentId}/approve`, { method: "POST" });
}

export async function rejectDocument(documentId, reason) {
  return apiClient(`/documents/${documentId}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export async function requestDocumentChanges(documentId, reason) {
  return apiClient(`/documents/${documentId}/request-changes`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export async function reprocessDocument(documentId) {
  return apiClient(`/documents/${documentId}/reprocess`, { method: "POST" });
}

export async function getDocumentHistory(documentId) {
  return apiClient(`/documents/${documentId}/history`);
}

/* ---- Reconciliation ---- */

export async function runReconciliation(documentId) {
  return apiClient(`/documents/${documentId}/reconcile`, { method: "POST" });
}

export async function getLatestReconciliation(documentId) {
  return apiClient(`/documents/${documentId}/reconciliation`);
}

/* ---- Finance Analyst ---- */

export async function askFinanceAnalyst(question, documentIds = []) {
  return apiClient("/agents/finance-analyst/ask", {
    method: "POST",
    body: JSON.stringify({ question, document_ids: documentIds }),
  });
}

/* ---- Financial Reporting ---- */

export async function generateFinancialReport({ name, period } = {}) {
  return apiClient("/agents/financial-reporting/generate", {
    method: "POST",
    body: JSON.stringify({
      name: name || "Finance Summary",
      period: period || null,
    }),
  });
}

/* ---- Fraud review (Administrator / Finance Manager) ---- */
export async function reviewFraudSignal({ documentId, signalType, decision, note }) {
  return apiClient("/agents/fraud-detection/review", {
    method: "POST",
    body: JSON.stringify({
      document_id: documentId,
      signal_type: signalType,
      decision,
      note: note || null,
    }),
  });
}
