import apiClient, { apiBlob, saveBlob } from "./apiClient";

/*
 * Advanced AI-employee workflows (AP batches, AR collections, coding,
 * reconciliation exceptions, analyst tools, expense policy, fraud risk,
 * statements and schedules). All numbers come from the backend.
 */

const post = (path, body) =>
  apiClient(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

async function download(path, fallbackName) {
  const { blob, filename } = await apiBlob(path);
  saveBlob(blob, filename || fallbackName);
}

/* ---- Accounts Payable ---- */
export const getApExceptions = () => apiClient("/agents/accounts-payable/exceptions");
export const resolveApException = (documentId, code, note, reopen = false) =>
  post("/agents/accounts-payable/exceptions/resolve", { document_id: documentId, code, note, reopen });
export const getPaymentReady = () => apiClient("/agents/accounts-payable/payment-ready");
export const getPaymentBatches = () => apiClient("/agents/accounts-payable/payment-batches");
export const createPaymentBatch = ({ name, paymentDate, documentIds }) =>
  post("/agents/accounts-payable/payment-batches", {
    name,
    payment_date: paymentDate,
    document_ids: documentIds,
  });
export const submitPaymentBatch = (id) =>
  post(`/agents/accounts-payable/payment-batches/${id}/submit`);
export const approvePaymentBatch = (id) =>
  post(`/agents/accounts-payable/payment-batches/${id}/approve`);
export const rejectPaymentBatch = (id, reason) =>
  post(`/agents/accounts-payable/payment-batches/${id}/reject`, { reason });
export const uploadBatchPaymentProof = (id, file) => {
  const form = new FormData();
  form.append("file", file);
  return apiClient(`/agents/accounts-payable/payment-batches/${id}/payment-proof`, { method: "POST", body: form });
};
export const getBatchPaymentProof = (id) => apiClient(`/agents/accounts-payable/payment-batches/${id}/payment-proof`);
export const markBatchPaid = (id, details) => post(`/agents/accounts-payable/payment-batches/${id}/mark-paid`, {
  transfer_reference: details.transferReference, bank_name: details.bankName || null,
  transfer_date: details.transferDate, payment_proof_reference: details.proofReference || null,
});
export const cancelBatch = (id) => post(`/agents/accounts-payable/payment-batches/${id}/cancel`);
export const downloadBatch = (batch) =>
  download(`/agents/accounts-payable/payment-batches/${batch.id}/export`, `${batch.name}.xlsx`);

/* ---- Accounts Receivable sales invoices / Stripe ---- */
export const getSalesInvoices = () => apiClient("/agents/accounts-receivable/sales-invoices");
export const createSalesInvoice = (payload) => post("/agents/accounts-receivable/sales-invoices", payload);
export const submitSalesInvoice = (id) => post(`/agents/accounts-receivable/sales-invoices/${id}/submit`);
export const managerApproveSalesInvoice = (id) => post(`/agents/accounts-receivable/sales-invoices/${id}/manager-approve`);
export const adminApproveSalesInvoice = (id) => post(`/agents/accounts-receivable/sales-invoices/${id}/admin-approve`);
export const rejectSalesInvoice = (id, reason) => post(`/agents/accounts-receivable/sales-invoices/${id}/reject`, { reason });
export const createStripeCheckout = (id) => post(`/agents/accounts-receivable/sales-invoices/${id}/stripe-checkout`);
export const emailSalesInvoice = (id) => post(`/agents/accounts-receivable/sales-invoices/${id}/send-email`);
export const getSalesInvoiceHistory = (id) => apiClient(`/agents/accounts-receivable/sales-invoices/${id}/history`);
export const downloadSalesInvoicePdf = (id, invoiceNumber) => download(`/agents/accounts-receivable/sales-invoices/${id}/pdf`, `${invoiceNumber || `AR-${id}`}.pdf`);

/* ---- Accounts Receivable ---- */
export const getCollectionPriorities = () => apiClient("/agents/accounts-receivable/priorities");
export const getCashForecast = (delayDays = 0) =>
  apiClient(`/agents/accounts-receivable/cash-forecast?delay_days=${delayDays}`);
export const markCollected = (documentId) =>
  post(`/agents/accounts-receivable/documents/${documentId}/collected`);
export const getReminders = () => apiClient("/agents/accounts-receivable/reminders");
export const generateReminder = (documentId, useAi) =>
  post("/agents/accounts-receivable/reminders/generate", { document_id: documentId, use_ai: useAi });
export const markReminderSent = (id) => post(`/agents/accounts-receivable/reminders/${id}/mark-sent`);
export const getDisputes = () => apiClient("/agents/accounts-receivable/disputes");
export const createDispute = ({ documentId, customerName, amount, reason }) =>
  post("/agents/accounts-receivable/disputes", {
    document_id: documentId || null,
    customer_name: customerName || null,
    amount: amount === "" || amount === undefined ? null : amount,
    reason,
  });
export const updateDispute = (id, status, resolutionNote) =>
  apiClient(`/agents/accounts-receivable/disputes/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status, resolution_note: resolutionNote || null }),
  });

/* ---- Invoice Processing ---- */
export const getChartOfAccounts = () => apiClient("/agents/invoice-processing/chart-of-accounts");
export const loadDefaultChart = () => post("/agents/invoice-processing/chart-of-accounts/load-default");
export const suggestCoding = (documentId, useAi) =>
  post(`/agents/invoice-processing/documents/${documentId}/coding/suggest`, { use_ai: useAi });
export const acceptCoding = (documentId, accountCode) =>
  post(`/agents/invoice-processing/documents/${documentId}/coding/accept`, { account_code: accountCode });

/* ---- Reconciliation ---- */
export const getReconExceptions = (documentId) =>
  apiClient(`/agents/reconciliation/${documentId}/exceptions`);
export const resolveReconException = (documentId, itemKey, status, note) =>
  post(`/agents/reconciliation/${documentId}/exceptions/resolve`, { item_key: itemKey, status, note });
export const downloadReconStatement = (documentId, name) =>
  download(`/agents/reconciliation/${documentId}/statement`, `Reconciliation statement - ${name}.xlsx`);

/* ---- Finance Analyst ---- */
export const runVariance = (body) => post("/agents/finance-analyst/variance", body);
export const runForecast = (body) => post("/agents/finance-analyst/forecast", body);
export const runScenario = (body) => post("/agents/finance-analyst/scenario", body);
export const runInsights = (useAi) => post("/agents/finance-analyst/insights", { use_ai: useAi });

/* ---- Expense ---- */
export const getExpensePolicies = () => apiClient("/agents/expense/policies");
export const saveExpensePolicies = (policies) =>
  apiClient("/agents/expense/policies", { method: "PUT", body: JSON.stringify({ policies }) });
export const getExpenseEvaluation = () => apiClient("/agents/expense/evaluation");
export const decideExpense = ({ documentId, decision, approvedAmount, note }) =>
  post("/agents/expense/decision", {
    document_id: documentId,
    decision,
    approved_amount: approvedAmount === "" || approvedAmount === undefined ? null : approvedAmount,
    note: note || null,
  });
// NEW: Finance User completes approved expense reimbursements and GL posting.
export const reimburseExpense = (documentId) =>
  post(`/agents/expense/${documentId}/reimburse`);

// NEW: Finance User-only Stripe environment readiness; no secret values are returned.
export const getStripeGatewayStatus = () => apiClient("/agents/accounts-receivable/stripe-status");

/* ---- Fraud ---- */
export const getFraudRisk = () => apiClient("/agents/fraud-detection/risk");
export const downloadEvidencePack = (documentId) =>
  download(`/agents/fraud-detection/evidence/${documentId}`, `Evidence pack - document ${documentId}.xlsx`);

/* ---- Financial Reporting ---- */
export const getLedgerStatus = () => apiClient("/agents/financial-reporting/ledger");
export const downloadLedgerTemplate = () =>
  download("/agents/financial-reporting/ledger/template", "ledger-template.xlsx");
export const importLedger = (file) => {
  const form = new FormData();
  form.append("file", file);
  return apiClient("/agents/financial-reporting/ledger/import", { method: "POST", body: form });
};
export const buildStatements = (body) => post("/agents/financial-reporting/statements", body);
export const downloadStatements = ({ start, end, compareStart, compareEnd }) => {
  const q = new URLSearchParams({ start, end });
  if (compareStart && compareEnd) {
    q.set("compare_start", compareStart);
    q.set("compare_end", compareEnd);
  }
  return download(`/agents/financial-reporting/statements/export?${q}`, "financial-statements.xlsx");
};
export const getSchedules = () => apiClient("/agents/financial-reporting/schedules");
export const createSchedule = (body) => post("/agents/financial-reporting/schedules", body);
export const scheduleAction = (id, action) =>
  post(`/agents/financial-reporting/schedules/${id}/${action}`);
export const deleteSchedule = (id) =>
  apiClient(`/agents/financial-reporting/schedules/${id}`, { method: "DELETE" });

export const refundStripePayment = (invoiceId, amount, reason) =>
  post(`/agents/accounts-receivable/sales-invoices/${invoiceId}/stripe-refunds`, { amount, reason });
