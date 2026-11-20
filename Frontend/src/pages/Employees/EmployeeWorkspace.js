import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import useAuth from "../../hooks/useAuth";
import {
  getDocuments,
  uploadDocument,
  downloadDocument,
  deleteDocument,
  payInvoice,
} from "../../services/documentsService";
import { getFinanceUsers } from "../../services/userService";
import {
  getReportsData,
  generateReport,
  downloadReport,
} from "../../services/reportsService";
import { useSearchSort, TableToolbar } from "../../components/common/TableTools";
import {
  DocumentPreviewModal,
  ReportPreviewModal,
} from "../../components/documents/DocumentPreviewModal";
import { sendAssistantMessage } from "../../services/assistantService";
import { ApPanel, ArPanel, InvoicePanel, ReconPanel } from "./WorkflowPanelsA";
import {
  AnalystTools,
  ExpensePanel,
  FraudReviewDialog,
  FraudRiskPanel,
  SchedulesPanel,
  StatementsPanel,
} from "./WorkflowPanelsB";
import {
  getAgentDashboard,
  approveDocument,
  rejectDocument,
  requestDocumentChanges,
  reprocessDocument,
  runReconciliation,
  reviewFraudSignal,
} from "../../services/agentsService";

import { SkeletonLoader } from "../../components/common/Loader";
import "./EmployeeWorkspace.css";

/*
 * Category names must match the backend classifier exactly
 * (app/services/document_classifier.py ALLOWED_CATEGORIES):
 *   Accounts Payable, Accounts Receivable, Invoice, Reconciliation,
 *   Expense, Financial Report, Policy, Uncategorized
 */
const EMPLOYEES = {
  1: {
    name: "Accounts Payable",
    eyebrow: "SUPPLIER OPERATIONS",
    description: "Review supplier invoices, payable documents and payment obligations.",
    output: "Validated invoices and payable priorities",
    capabilities: ["Supplier invoice review", "Exception queue with resolutions", "Payment-ready batches with XLSX export", "Mark batches paid after Chief Accountant approval (Finance User)"],
    documentCategories: ["Accounts Payable", "Invoice"],
    reviewActions: true,
  },
  2: {
    name: "Accounts Receivable",
    eyebrow: "CUSTOMER COLLECTIONS",
    description: "Review receivables documents and identify overdue items from due dates.",
    output: "Receivables review and overdue visibility",
    capabilities: ["Aging and overdue detection", "Collection priorities with scores", "Reminder drafts and dispute cases", "12-week cash forecast inputs"],
    documentCategories: ["Accounts Receivable"],
    reviewActions: true,
  },
  3: {
    name: "Invoice Processing",
    eyebrow: "INVOICE OPERATIONS",
    description: "Upload invoices for AI extraction, validation and duplicate detection.",
    output: "Structured invoice data with validation status",
    capabilities: ["Structured extraction and validation", "Extraction confidence score", "Duplicate flags", "GL coding suggestions from your chart"],
    documentCategories: ["Invoice", "Accounts Payable"],
    reviewActions: true,
  },
  4: {
    name: "Reconciliation",
    eyebrow: "FINANCIAL CONTROLS",
    description: "Match company cashbook entries against bank statement lines in a reconciliation workbook.",
    output: "Matched and unmatched transactions",
    capabilities: ["Cashbook vs bank matching", "Exception cases (resolve / write off)", "Reconciliation statement (XLSX)"],
    documentCategories: ["Reconciliation"],
    reconcile: true,
  },
  5: {
    name: "Finance Analyst",
    eyebrow: "FINANCIAL INTELLIGENCE",
    description: "Ask finance questions answered from your uploaded documents.",
    output: "Document-grounded finance answers with sources",
    capabilities: ["Finance Q&A with cited sources", "Management insights", "Variance analysis (period or budget)", "Explainable forecasts", "Scenario analysis"],
  },
  6: {
    name: "Expense Employee",
    eyebrow: "EXPENSE OPERATIONS",
    description: "Review expense-related documents and extracted amounts.",
    output: "Expense document review",
    capabilities: ["Expense intake and totals", "Editable policy limits", "Policy violation checks", "Reimbursement recommendations, human decision"],
    documentCategories: ["Expense"],
    reviewActions: true,
  },
  7: {
    name: "Financial Reporting",
    eyebrow: "REPORTING OPERATIONS",
    description: "Generate summary reports from extracted document data and review past reports.",
    output: "Financial summary report",
    capabilities: ["Document summary reports", "P&L, Balance Sheet, Cash Flow from your ledger", "Variance commentary", "Reporting schedules"],
  },
  8: {
    name: "Fraud Detection",
    eyebrow: "RISK MONITORING",
    description: "Rule-based review signals across all of your uploaded financial documents.",
    output: "Risk signals for human investigation",
    capabilities: ["Duplicate and high-amount signals", "0-100 risk scores with visible rules", "Evidence packs (XLSX)", "Guided review with quick reasons"],
    fraud: true,
  },
};

const UPLOAD_ACCEPT = ".pdf,.csv,.xls,.xlsx,.xlsm,.docx";

/* ----------------------------- helpers ----------------------------- */

function humanize(key) {
  return String(key)
    .replace(/([A-Z])/g, " $1")
    .replace(/^./, (character) => character.toUpperCase())
    .trim();
}

function formatValue(value) {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") {
    return Number.isInteger(value)
      ? value.toLocaleString("en-IN")
      : value.toLocaleString("en-IN", { maximumFractionDigits: 2 });
  }
  if (typeof value === "object") {
    const entries = Object.entries(value);
    return entries.length
      ? entries.map(([key, count]) => `${key}: ${count}`).join(" · ")
      : "—";
  }
  return String(value);
}

function formatAmount(value) {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  return Number.isFinite(number)
    ? number.toLocaleString("en-IN", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })
    : String(value);
}

function formatInr(value) {
  const number = Number(value);
  return Number.isFinite(number)
    ? number.toLocaleString("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 2,
      })
    : "—";
}

function StatusPill({ status }) {
  const normalized = String(status || "UNKNOWN")
    .toLowerCase()
    .replace(/[\s_]+/g, "-");

  return (
    <span className={`workspace-status workspace-status-${normalized}`}>
      {String(status || "UNKNOWN").replace(/_/g, " ")}
    </span>
  );
}

function SummaryCard({ label, value, note }) {
  return (
    <article className="workspace-summary-card">
      <span>{label}</span>
      <strong>{value}</strong>
      {note ? <small>{note}</small> : null}
    </article>
  );
}

/* Renders an array of plain objects as a table (used for reconciliation rows). */
function GenericTable({ rows, limit = 25 }) {
  if (!Array.isArray(rows) || rows.length === 0) {
    return <p className="workspace-muted">None.</p>;
  }

  const columns = Object.keys(rows[0] || {}).slice(0, 8);
  const visibleRows = rows.slice(0, limit);

  return (
    <div className="workspace-table-wrap">
      <table className="workspace-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{humanize(column)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {visibleRows.map((row, index) => (
            <tr key={index}>
              {columns.map((column) => (
                <td key={column}>{formatValue(row[column])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > limit && (
        <p className="workspace-footnote">
          Showing the first {limit} of {rows.length} rows.
        </p>
      )}
    </div>
  );
}

const DOCUMENT_SORTS = [
  { key: "newest", label: "Upload date", get: (d) => d.id },
  { key: "name", label: "Name", get: (d) => d.name },
  { key: "vendor", label: "Vendor", get: (d) => d.vendorName },
  { key: "amount", label: "Amount", get: (d) => (d.totalAmount === null || d.totalAmount === undefined ? null : Number(d.totalAmount)) },
  { key: "status", label: "Status", get: (d) => d.status },
];
const documentSearchText = (d) =>
  [d.name, d.category, d.vendorName, d.invoiceNumber, d.status, d.reviewStatus, d.validationStatus, d.ownerName, d.totalAmount]
    .filter((v) => v !== null && v !== undefined)
    .join(" ");

const FRAUD_SORTS = [
  { key: "severity", label: "Severity", get: (f) => ({ HIGH: 3, REVIEW: 2 }[f.severity] || 1) },
  { key: "document", label: "Document", get: (f) => f.documentName },
  { key: "signal", label: "Signal", get: (f) => f.type },
  { key: "review", label: "Review status", get: (f) => f.reviewStatus },
];
const fraudSearchText = (f) =>
  [f.type, f.severity, f.documentName, f.reason, f.reviewStatus, f.documentOwner].filter(Boolean).join(" ");

const REPORT_SORTS = [
  { key: "newest", label: "Generated", get: (r) => r.id },
  { key: "name", label: "Name", get: (r) => r.name },
  { key: "period", label: "Period", get: (r) => r.period },
  { key: "status", label: "Status", get: (r) => r.status },
];
const reportSearchText = (r) => [r.name, r.category, r.period, r.status, r.format].filter(Boolean).join(" ");

/* --------------------------- live dashboard --------------------------- */

function useDashboard(employeeId) {
  const [state, setState] = useState({ data: null, loading: true, error: "" });
  const requestId = useRef(0);

  const load = useCallback(async () => {
    const current = ++requestId.current;

    setState((previous) => ({ ...previous, loading: true, error: "" }));

    try {
      const data = await getAgentDashboard(employeeId);
      if (current === requestId.current) {
        setState({ data, loading: false, error: "" });
      }
    } catch (requestError) {
      if (current === requestId.current) {
        setState({ data: null, loading: false, error: requestError.message });
      }
    }
  }, [employeeId]);

  useEffect(() => {
    load();
    return () => {
      requestId.current += 1;
    };
  }, [load]);

  return { ...state, reload: load };
}

function DashboardSummary({ dashboard, loading, error }) {
  if (loading && !dashboard) {
    return (
      <section className="workspace-panel">
        <SkeletonLoader variant="cards" />
      </section>
    );
  }

  if (error) {
    return (
      <section className="workspace-panel">
        <p className="workspace-error">Live summary unavailable: {error}</p>
      </section>
    );
  }

  const entries = Object.entries(dashboard?.summary || {}).filter(
    ([key]) => key !== "amountsAreInvoiceMetadata"
  );

  if (entries.length === 0) return null;

  return (
    <section className="workspace-panel">
      <div className="workspace-panel-header">
        <div>
          <h2>Live summary</h2>
          <p>Calculated from your uploaded documents.</p>
        </div>
      </div>

      <div className="workspace-summary-grid workspace-live-grid">
        {entries.map(([key, value]) => (
          <SummaryCard
            key={key}
            label={humanize(key).toUpperCase()}
            value={formatValue(value)}
          />
        ))}
      </div>

      {dashboard?.note && <p className="workspace-footnote">{dashboard.note}</p>}
    </section>
  );
}

/* --------------------- document-based employees --------------------- */

function DocumentsWorkspace({ employee, onChanged }) {
  const { currentUser } = useAuth();
  const roleName = currentUser?.role_name || "";
  const canReview = Boolean(currentUser?.can_review);
  const isFinanceManager = roleName === "Finance Manager";
  const isAdministrator = roleName === "Administrator";
  const isFinanceUser = roleName === "Finance User";
  const isChiefAccountant = roleName === "Chief Accountant";
  const isApWorkspace = employee.name === "Accounts Payable";
  const isInvoiceWorkflowWorkspace = isApWorkspace || employee.name === "Invoice Processing";
  const canDeleteDocument = (document) => isAdministrator || document.ownerId === currentUser?.id;

  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [uploading, setUploading] = useState(false);
  const [resubmitDocumentId, setResubmitDocumentId] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [rejectingId, setRejectingId] = useState(null);
  const [rejectReason, setRejectReason] = useState("");
  const [reviewActionMode, setReviewActionMode] = useState("REJECT");
  const [reconciliation, setReconciliation] = useState(null);
  // NEW: Finance Manager / Chief Accountant choose the downstream payment owner.
  const [financeUsers, setFinanceUsers] = useState([]);
  const [assignedFinanceUserId, setAssignedFinanceUserId] = useState("");
  const [financeUsersError, setFinanceUsersError] = useState("");
  // NEW: Expandable More Details panel and AP payment capture.
  const [expandedDocumentId, setExpandedDocumentId] = useState(null);
  const [payingDocumentId, setPayingDocumentId] = useState(null);
  const [paymentForm, setPaymentForm] = useState({
    amount: "",
    transferReference: "",
    bankName: "",
    paymentDate: new Date().toISOString().slice(0, 10),
  });
  const fileInputRef = useRef(null);

  useEffect(() => {
    let active = true;
    if (!isInvoiceWorkflowWorkspace || !["Finance Manager", "Chief Accountant"].includes(roleName)) {
      setFinanceUsers([]);
      return () => { active = false; };
    }
    getFinanceUsers()
      .then((rows) => {
        if (!active) return;
        const list = Array.isArray(rows) ? rows : [];
        setFinanceUsers(list);
        if (list.length === 1) setAssignedFinanceUserId(String(list[0].id));
      })
      .catch((requestError) => {
        if (active) setFinanceUsersError(requestError.message || "Unable to load Finance Users.");
      });
    return () => { active = false; };
  }, [isInvoiceWorkflowWorkspace, roleName]);

  useEffect(() => {
    let active = true;

    getDocuments()
      .then((data) => {
        if (active) setDocuments(Array.isArray(data) ? data : []);
      })
      .catch((requestError) => {
        if (active) setError(requestError.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const visibleDocuments = useMemo(() => {
    if (!employee.documentCategories?.length) return documents;

    return documents.filter((document) =>
      employee.documentCategories.some(
        (category) =>
          String(document.category || "").toLowerCase() === category.toLowerCase()
      )
    );
  }, [documents, employee]);

  const showInvoiceColumns = Boolean(employee.reviewActions);
  const [previewDoc, setPreviewDoc] = useState(null);
  const controls = useSearchSort(visibleDocuments, {
    searchText: documentSearchText,
    sorts: DOCUMENT_SORTS,
    defaultSort: { key: "newest", direction: "desc" },
  });

  async function handleDelete(document) {
    const confirmed = window.confirm(`Delete "${document.name}" permanently? The stored file and its database record will be removed.`);
    if (!confirmed) return;
    try {
      setBusyId(document.id);
      setError("");
      setMessage("");
      await deleteDocument(document.id);
      setDocuments((current) => current.filter((item) => item.id !== document.id));
      setMessage(`Deleted "${document.name}".`);
      if (previewDoc?.id === document.id) setPreviewDoc(null);
      onChanged();
    } catch (requestError) {
      setError(requestError.message || "Unable to delete this document.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleDownload(document) {
    try {
      setBusyId(document.id);
      setError("");
      await downloadDocument(document);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusyId(null);
    }
  }

  function replaceDocument(updated) {
    setDocuments((current) =>
      current.map((document) => (document.id === updated.id ? updated : document))
    );
  }

  async function runAction(documentId, action, successMessage) {
    try {
      setBusyId(documentId);
      setError("");
      setMessage("");
      const updated = await action();
      if (updated?.id) replaceDocument(updated);
      if (successMessage) setMessage(successMessage);
      onChanged();
      return updated;
    } catch (requestError) {
      setError(requestError.message);
      return null;
    } finally {
      setBusyId(null);
    }
  }

  async function handleFileChange(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    if (
      isInvoiceWorkflowWorkspace &&
      ["Finance Manager", "Chief Accountant"].includes(roleName) &&
      !resubmitDocumentId &&
      !assignedFinanceUserId
    ) {
      setError("Select the Finance User responsible for payment before uploading.");
      return;
    }

    try {
      setUploading(true);
      setError("");
      setMessage("");

      const uploaded = await uploadDocument(file, {
        workspace: isApWorkspace
          ? "accounts-payable"
          : employee.name === "Invoice Processing"
          ? "invoice-processing"
          : employee.name === "Expense Employee"
          ? "expense-employee"
          : undefined,
        replacesDocumentId: resubmitDocumentId,
        assignedFinanceUserId: isInvoiceWorkflowWorkspace && ["Finance Manager", "Chief Accountant"].includes(roleName)
          ? assignedFinanceUserId
          : undefined,
      });
      setResubmitDocumentId(null);
      setDocuments((current) => [uploaded, ...current]);

      const belongsHere =
        !employee.documentCategories?.length ||
        employee.documentCategories.some(
          (category) =>
            String(uploaded.category || "").toLowerCase() === category.toLowerCase()
        );

      setMessage(
        belongsHere
          ? `Uploaded "${uploaded.name}" (${uploaded.category}).`
          : `Uploaded "${uploaded.name}" and classified it as "${uploaded.category}", so it is handled by a different AI employee.`
      );
      onChanged();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setUploading(false);
    }
  }

  function handleApprove(document) {
    return runAction(
      document.id,
      () => approveDocument(document.id),
      `Approved "${document.name}".`
    );
  }

  async function handleRejectSubmit(document) {
    const reason = rejectReason.trim();

    if (!reason) {
      setError("A rejection reason is required.");
      return;
    }

    const result = await runAction(
      document.id,
      () => reviewActionMode === "REQUEST_CHANGES"
        ? requestDocumentChanges(document.id, reason)
        : rejectDocument(document.id, reason),
      reviewActionMode === "REQUEST_CHANGES"
        ? `Changes requested for "${document.name}".`
        : `Rejected "${document.name}".`
    );

    if (result) {
      setRejectingId(null);
      setRejectReason("");
      setReviewActionMode("REJECT");
    }
  }

  function handleReprocess(document) {
    return runAction(
      document.id,
      () => reprocessDocument(document.id),
      `Reprocessed "${document.name}".`
    );
  }

  // NEW: Capture the manual bank transfer and let the backend atomically post the GL voucher.
  async function handleInvoicePayment(document) {
    if (!paymentForm.transferReference.trim() || !paymentForm.paymentDate) {
      setError("Enter the bank transfer reference and payment date.");
      return;
    }
    const result = await runAction(
      document.id,
      () => payInvoice(document.id, {
        amount: paymentForm.amount,
        transferReference: paymentForm.transferReference.trim(),
        bankName: paymentForm.bankName.trim(),
        paymentDate: paymentForm.paymentDate,
      }),
      `Payment recorded and ledger voucher created for "${document.name}".`
    );
    if (result) {
      setPayingDocumentId(null);
      setExpandedDocumentId(document.id);
    }
  }

  async function handleReconcile(document) {
    try {
      setBusyId(document.id);
      setError("");
      setMessage("");
      const result = await runReconciliation(document.id);
      setReconciliation(result);
      setMessage(`Reconciliation completed for "${document.name}".`);
      onChanged();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusyId(null);
    }
  }

  const isXlsx = (document) => /\.xls[xm]$/i.test(document.name || "");

  return (
    <section className="workspace-panel">
      <div className="workspace-panel-header">
        <div>
          <h2>Financial documents</h2>
          <p>Documents the AI classified into this employee's workflow.</p>
        </div>
        <div className="workspace-actions">
          {isInvoiceWorkflowWorkspace && ["Finance Manager", "Chief Accountant"].includes(roleName) && (
            <select
              aria-label="Finance User responsible for payment"
              value={assignedFinanceUserId}
              onChange={(event) => setAssignedFinanceUserId(event.target.value)}
              disabled={uploading}
            >
              <option value="">Select payment owner</option>
              {financeUsers.map((person) => (
                <option key={person.id} value={String(person.id)}>{person.fullName} ({person.email})</option>
              ))}
            </select>
          )}
          {isInvoiceWorkflowWorkspace && (
            <a
              className="workspace-action"
              href="https://services.gst.gov.in/services/searchtp"
              target="_blank"
              rel="noopener noreferrer"
            >GST Check ↗</a>
          )}
        <button
          className="workspace-primary-button"
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
        >
          {uploading ? "Uploading and processing..." : "＋ Upload document"}
        </button>
        </div>
        <input
          ref={fileInputRef}
          className="workspace-hidden-input"
          type="file"
          accept={UPLOAD_ACCEPT}
          onChange={handleFileChange}
        />
      </div>

      {message && <p className="workspace-message">{message}</p>}
      {error && <p className="workspace-error">{error}</p>}
      {financeUsersError && <p className="workspace-error">{financeUsersError}</p>}
      {isInvoiceWorkflowWorkspace && ["Finance Manager", "Chief Accountant"].includes(roleName) && financeUsers.length === 0 && !financeUsersError && (
        <p className="workspace-footnote">No active Finance Users are available for payment assignment.</p>
      )}

      {loading ? (
        <SkeletonLoader variant="table" rows={6} />
      ) : visibleDocuments.length === 0 ? (
        <div className="workspace-empty">
          <strong>No matching documents</strong>
          <p>Upload a document and the AI will classify it to the right employee.</p>
        </div>
      ) : (
        <>
        <TableToolbar controls={controls} placeholder="Search name, vendor, invoice no., status..." label="documents" />
        {controls.filtered.length === 0 && (
          <p className="workspace-muted">No documents match your search.</p>
        )}
        <div className="workspace-table-wrap">
          <table className="workspace-table">
            <thead>
              <tr>
                <th>Document</th>
                {showInvoiceColumns && <th>Invoice</th>}
                {showInvoiceColumns && <th>Total</th>}
                {showInvoiceColumns && <th>Validation</th>}
                <th>Uploaded</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {controls.filtered.map((document) => {
                const busy = busyId === document.id;
                const documentStatus = document.status || document.reviewStatus;
                const uploaderRole = document.uploaderRole || "";
                const pendingFirstReview = ["PENDING_REVIEW", "PENDING_MANAGER_APPROVAL", "PENDING_FINANCE_USER_VERIFICATION", "READY_FOR_REVIEW"].includes(documentStatus);
                const pendingChiefAccountant = documentStatus === "PENDING_CA_APPROVAL";
                const isEmployeeUpload = uploaderRole === "Employee / Requester";
                const isFinanceUserUpload = uploaderRole === "Finance User";
                const isFinanceManagerUpload = uploaderRole === "Finance Manager";
                const isInvoiceDocument = ["accounts payable", "invoice", "invoices"].includes(String(document.category || "").toLowerCase());
                const canApprove = isInvoiceWorkflowWorkspace && document.ownerId !== currentUser?.id && (
                  ((isEmployeeUpload || isFinanceUserUpload) && pendingFirstReview && (isFinanceUser || isFinanceManager)) ||
                  ((isFinanceUserUpload || isFinanceManagerUpload) && pendingChiefAccountant && isChiefAccountant)
                );
                const canTakeReviewAction = canApprove;
                const canPayInvoice = isInvoiceDocument && isFinanceUser && documentStatus === "PENDING_PAYMENT" &&
                  (!document.assignedFinanceUserId || Number(document.assignedFinanceUserId) === Number(currentUser?.id));
                const approvedApAwaitingExtraction = employee.name === "Invoice Processing" &&
                  ["accounts payable", "invoice", "invoices"].includes(document.category?.toLowerCase()) &&
                  document.reviewStatus === "APPROVED" &&
                  document.validationStatus !== "VALID";
                const canReprocess = approvedApAwaitingExtraction || (
                  employee.reviewActions &&
                  !["READY_FOR_REVIEW", "MANAGER_APPROVED", "APPROVED", "REJECTED"].includes(document.reviewStatus)
                );

                return (
                  <React.Fragment key={document.id}>
                    <tr>
                      <td>
                        <strong>{document.name}</strong>
                        <small>
                          {document.type} · {document.size} · {document.category}
                        </small>
                        {canReview && document.ownerName && (
                          <small>Uploaded by {document.ownerName}</small>
                        )}
                      </td>

                      {showInvoiceColumns && (
                        <td>
                          <strong>{document.invoiceNumber || "—"}</strong>
                          <small>{document.vendorName || "Vendor not extracted"}</small>
                        </td>
                      )}
                      {showInvoiceColumns && <td>{formatAmount(document.totalAmount)}</td>}
                      {showInvoiceColumns && (
                        <td>
                          <StatusPill status={document.validationStatus} />
                          {document.isDuplicate && (
                            <small className="workspace-status-duplicate">
                              Possible duplicate{document.duplicateMatch ? ` · matches ${document.duplicateMatch.invoiceNumber || document.duplicateMatch.name}` : ""}
                              {document.duplicateMatch && (
                                <span>
                                  <br />Original: {document.duplicateMatch.vendorName || "Vendor unknown"} · {formatAmount(document.duplicateMatch.totalAmount)} · {document.duplicateMatch.status}
                                  <br />Uploaded by: {document.duplicateMatch.ownerName || "Unknown uploader"}
                                  {document.duplicateMatch.isPaid ? " · Already paid" : " · Not marked paid"}
                                </span>
                              )}
                            </small>
                          )}
                          {document.extractionConfidence != null && (
                            <small>
                              Confidence {Math.round(document.extractionConfidence * 100)}%
                              {document.lowConfidence ? " (please review)" : ""}
                            </small>
                          )}
                          {Array.isArray(document.validationErrors) &&
                            document.validationErrors
                              .slice(0, 2)
                              .map((validationError, index) => (
                                <small key={index}>{String(validationError)}</small>
                              ))}
                        </td>
                      )}

                      <td>{document.uploadedAt}</td>
                      <td>
                        <StatusPill status={document.status} />
                        {document.rejectionReason && <small>{document.rejectionReason}</small>}
                      </td>

                      <td className="workspace-actions">
                        <button
                          type="button"
                          className="workspace-action icon-action"
                          aria-label="View document"
                          title="View document"
                          disabled={busy}
                          onClick={() => setPreviewDoc(document)}
                        >
                          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>
                        </button>
                        <button
                          type="button"
                          className="workspace-action"
                          aria-expanded={expandedDocumentId === document.id}
                          onClick={() => setExpandedDocumentId((current) => current === document.id ? null : document.id)}
                        >
                          {expandedDocumentId === document.id ? "Hide details" : "More details"}
                        </button>
                        <button
                          type="button"
                          className="workspace-action icon-action"
                          aria-label="Download document"
                          title="Download document"
                          disabled={busy}
                          onClick={() => handleDownload(document)}
                        >
                          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5M12 15V3"/></svg>
                        </button>
                        {document.ownerId === currentUser?.id &&
                          (employee.name === "Expense Employee" || isInvoiceWorkflowWorkspace) &&
                          ["REJECTED", "NEEDS_CHANGES"].includes(document.status) && (
                          <button type="button" className="workspace-action" disabled={uploading} onClick={() => { setResubmitDocumentId(document.id); fileInputRef.current?.click(); }} title="Upload corrected document">Re-upload corrected</button>
                        )}
                        {canDeleteDocument(document) && (
                          <button
                            type="button"
                            className="workspace-action reject icon-action"
                            disabled={busy}
                            onClick={() => handleDelete(document)}
                            title="Delete this uploaded document"
                          >
                            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18M8 6V4h8v2m3 0-1 14H6L5 6m4 4v6m6-6v6"/></svg>
                          </button>
                        )}
                        {canPayInvoice && (
                          <button type="button" className="workspace-action approve" onClick={() => {
                            setExpandedDocumentId(document.id);
                            setPayingDocumentId(document.id);
                            setPaymentForm({ amount: document.totalAmount || "", transferReference: "", bankName: "", paymentDate: new Date().toISOString().slice(0, 10) });
                          }}>Record payment</button>
                        )}
                        {employee.reviewActions && canTakeReviewAction && (
                          <>
                            <button
                              type="button"
                              className="workspace-action approve icon-action"
                              disabled={busy}
                              title={isChiefAccountant ? "Chief Accountant approval / verification" : "Approve invoice"}
                              aria-label="Approve invoice"
                              onClick={() => handleApprove(document)}
                            >
                              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg>
                            </button>
                            <button
                              type="button"
                              className="workspace-action reject icon-action"
                              disabled={busy}
                              title="Reject invoice"
                              aria-label="Reject invoice"
                              onClick={() => {
                                setRejectingId(document.id);
                                setRejectReason("");
                                setReviewActionMode("REJECT");
                              }}
                            >
                              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m18 6-12 12M6 6l12 12"/></svg>
                            </button>
                            {(isFinanceManager || isFinanceUser) && (
                              <button
                                type="button"
                                className="workspace-action"
                                disabled={busy}
                                onClick={() => {
                                  setRejectingId(document.id);
                                  setRejectReason("");
                                  setReviewActionMode("REQUEST_CHANGES");
                                }}
                              >
                                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5m4-1v5l4 2"/></svg>
                              </button>
                            )}
                          </>
                        )}
                        {canReprocess && (
                          <button
                            type="button"
                            className="workspace-action"
                            disabled={busy}
                            onClick={() => handleReprocess(document)}
                          >
                            {approvedApAwaitingExtraction ? "Process approved invoice" : "Reprocess"}
                          </button>
                        )}
                        {employee.reconcile && isXlsx(document) && (
                          <button
                            type="button"
                            className="workspace-action approve"
                            disabled={busy}
                            onClick={() => handleReconcile(document)}
                          >
                            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 7v5h-5M4 17v-5h5"/><path d="M5.5 9A7 7 0 0 1 18 6l2 6M4 12l2 6a7 7 0 0 0 12.5-3"/></svg>
                          </button>
                        )}
                      </td>
                    </tr>

                    {expandedDocumentId === document.id && (
                      <tr>
                        <td colSpan={showInvoiceColumns ? 7 : 4}>
                          <div className="workspace-detail-panel">
                            <h3>Invoice details and approval history</h3>
                            <div className="workspace-summary-grid">
                              <SummaryCard label="UPLOADED BY" value={document.ownerName || "—"} />
                              <SummaryCard label="UPLOADER ROLE" value={document.uploaderRole || "—"} />
                              <SummaryCard label="APPROVED BY" value={document.firstReviewedByName || document.reviewedBy || "—"} />
                              <SummaryCard label="CHIEF ACCOUNTANT" value={document.chiefAccountantApprovedByName || "Not reviewed"} />
                              <SummaryCard label="PAYMENT OWNER" value={document.assignedFinanceUserName || "Any Finance User"} />
                              <SummaryCard label="PAID BY" value={document.paidByName || "Not paid"} />
                              <SummaryCard label="LEDGER VOUCHER" value={document.ledgerVoucherNo || "Not posted"} />
                              <SummaryCard label="PAYMENT REFERENCE" value={document.paymentReference || "—"} />
                            </div>
                            {document.rejectionReason && <p className="workspace-error">Reviewer remarks: {document.rejectionReason}</p>}
                            {document.paymentAmount && <p className="workspace-footnote">Paid {formatInr(document.paymentAmount)} on {document.paymentDate || "—"} · Bank: {document.paymentBankName || "—"} · Reference: {document.paymentReference || "—"}</p>}
                            {payingDocumentId === document.id && canPayInvoice && (
                              <div className="workspace-payment-form">
                                <h4>Final supplier payment details</h4>
                                <label>Payment amount<input type="number" min="0.01" step="0.01" value={paymentForm.amount} onChange={(event) => setPaymentForm((old) => ({ ...old, amount: event.target.value }))} /></label>
                                <label>Bank transfer reference<input required maxLength={120} value={paymentForm.transferReference} onChange={(event) => setPaymentForm((old) => ({ ...old, transferReference: event.target.value }))} /></label>
                                <label>Bank name<input maxLength={120} value={paymentForm.bankName} onChange={(event) => setPaymentForm((old) => ({ ...old, bankName: event.target.value }))} /></label>
                                <label>Payment date<input required type="date" value={paymentForm.paymentDate} onChange={(event) => setPaymentForm((old) => ({ ...old, paymentDate: event.target.value }))} /></label>
                                <div className="workspace-actions">
                                  <button type="button" className="workspace-primary-button" disabled={busy} onClick={() => handleInvoicePayment(document)}>Confirm payment and post to ledger</button>
                                  <button type="button" className="workspace-action" onClick={() => setPayingDocumentId(null)}>Cancel</button>
                                </div>
                                <small>Payment succeeds only when the backend records both payment details and the balanced ledger voucher.</small>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}

                    {rejectingId === document.id && (
                      <tr>
                        <td colSpan={showInvoiceColumns ? 7 : 4}>
                          <div className="workspace-reject-form">
                            <input
                              type="text"
                              value={rejectReason}
                              onChange={(event) => setRejectReason(event.target.value)}
                              placeholder={reviewActionMode === "REQUEST_CHANGES" ? "Explain what the requester must correct (required)" : "Reason for rejection (required)"}
                              aria-label="Rejection reason"
                              maxLength={2000}
                            />
                            <button
                              type="button"
                              className="workspace-action reject"
                              disabled={busy}
                              onClick={() => handleRejectSubmit(document)}
                            >
                              {reviewActionMode === "REQUEST_CHANGES" ? "Send change request" : "Confirm reject"}
                            </button>
                            <button
                              type="button"
                              className="workspace-action"
                              onClick={() => setRejectingId(null)}
                            >
                              Cancel
                            </button>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
        </>
      )}

      {previewDoc && (
        <DocumentPreviewModal document={previewDoc} onClose={() => setPreviewDoc(null)} />
      )}

      {employee.reviewActions && currentUser && (
        <p className="workspace-footnote">
          Your role: <strong>{currentUser.role_name || "Unknown"}</strong>.{" "}
          {isInvoiceWorkflowWorkspace
            ? (isFinanceUser
                ? "You can review employee uploads, independently review another Finance User's upload, and pay invoices assigned to you. You cannot approve your own upload."
                : isFinanceManager
                ? "You can review Employee and Finance User uploads. Your own uploads go directly to Chief Accountant review."
                : isChiefAccountant
                ? "You verify Finance User and Finance Manager uploads. Chief Accountant uploads require no further review."
                : "You can submit and track your own documents. Finance User or Finance Manager performs the review.")
            : "Use the dedicated expense workflow for employee reimbursement decisions."}
        </p>
      )}

      {employee.reconcile && (
        <p className="workspace-footnote">
          The workbook must contain sheets named exactly "Company Cashbook" and "Bank Statement".
        </p>
      )}

      {reconciliation && <ReconciliationResult result={reconciliation} />}
    </section>
  );
}

function ReconciliationResult({ result }) {
  const summary = result.summary || {};
  const results = result.results || {};

  return (
    <div className="workspace-result">
      <div className="workspace-panel-header">
        <div>
          <h2>Reconciliation result</h2>
          <p>{result.documentName}</p>
        </div>
        <StatusPill status={result.status} />
      </div>

      <div className="workspace-summary-grid workspace-live-grid">
        <SummaryCard label="MATCHED" value={formatValue(summary.matchedCount)} />
        <SummaryCard
          label="UNMATCHED CASHBOOK"
          value={formatValue(summary.unmatchedCashbookCount)}
        />
        <SummaryCard label="UNMATCHED BANK" value={formatValue(summary.unmatchedBankCount)} />
      </div>

      {summary.matchingPolicy && (
        <p className="workspace-footnote">{summary.matchingPolicy}</p>
      )}

      <h3>Unmatched cashbook entries</h3>
      <GenericTable rows={results.unmatchedCashbook} />

      <h3>Unmatched bank statement lines</h3>
      <GenericTable rows={results.unmatchedBankStatement} />
    </div>
  );
}

/* --------------------------- fraud detection --------------------------- */

function FraudWorkspace({ dashboard, loading, error, onChanged }) {
  const findings = Array.isArray(dashboard?.findings) ? dashboard.findings : [];
  const canReview = Boolean(dashboard?.canReview);
  const roleName = dashboard?.roleName || "";
  const controls = useSearchSort(findings, {
    searchText: fraudSearchText,
    sorts: FRAUD_SORTS,
    defaultSort: { key: "severity", direction: "desc" },
  });
  const [reviewing, setReviewing] = useState(null);
  const [dialogError, setDialogError] = useState("");
  const [busyKey, setBusyKey] = useState(null);
  const [actionError, setActionError] = useState("");
  const [actionMessage, setActionMessage] = useState("");

  async function decide(finding, decision, note = "") {
    const key = `${finding.type}-${finding.documentId}`;

    try {
      setBusyKey(key);
      setActionError("");
      setDialogError("");
      setActionMessage("");
      await reviewFraudSignal({
        documentId: finding.documentId,
        signalType: finding.type,
        decision,
        note,
      });
      setActionMessage(
        finding.isApDocument
          ? decision === "ESCALATE"
            ? "AP risk signal escalated to Finance Manager for investigation."
            : roleName === "Finance Manager"
            ? "Finance Manager investigation recorded. The invoice remains on hold until Chief Accountant makes the final decision."
            : decision === "CONFIRMED"
            ? "Chief Accountant confirmed the suspicious activity. The invoice remains on hold."
            : "Chief Accountant dismissed the fraud signal. The invoice returns to its normal approval stage; it is not automatically approved."
          : roleName === "Finance Manager"
          ? "Finance Manager review recorded. The record is on hold until Admin makes the final decision."
          : decision === "CONFIRMED"
          ? "Admin confirmed the suspicious activity. The record remains on hold."
          : "Admin dismissed the alert. The record can return to its workflow once all alerts are cleared."
      );
      setReviewing(null);
      onChanged();
    } catch (requestError) {
      if (decision === "OPEN" || decision === "ESCALATE") setActionError(requestError.message);
      else setDialogError(requestError.message);
    } finally {
      setBusyKey(null);
    }
  }

  return (
    <>
    <section className="workspace-panel">
      <div className="workspace-panel-header">
        <div>
          <h2>Risk signals</h2>
          <p>
            Rule-based signals for a human to investigate. A signal is not proof of fraud.
            {roleName === "Finance User"
              ? " You can escalate AP risk signals to Finance Manager for investigation."
              : roleName === "Finance Manager"
              ? " You investigate escalated AP signals and review non-AP risk signals."
              : roleName === "Chief Accountant"
              ? " You make the final AP fraud decision after Finance Manager investigation."
              : roleName === "Administrator"
              ? " You can review non-AP fraud signals. AP fraud decisions belong to Chief Accountant."
              : " Risk signals are reviewed by authorized finance roles."}
          </p>
        </div>
      </div>

      {actionMessage && <p className="workspace-message">{actionMessage}</p>}
      {actionError && <p className="workspace-error">{actionError}</p>}

      {loading && !dashboard ? (
        <SkeletonLoader variant="table" rows={5} />
      ) : error ? (
        <p className="workspace-error">{error}</p>
      ) : findings.length === 0 ? (
        <div className="workspace-empty">
          <strong>No review signals found</strong>
          <p>No duplicate or unusually high amounts were detected in the uploaded documents.</p>
        </div>
      ) : (
        <>
          <TableToolbar controls={controls} placeholder="Search signal, document, reason..." label="signals" />
          {controls.filtered.length === 0 && (
            <p className="workspace-muted">No signals match your search.</p>
          )}
          <div className="workspace-table-wrap">
            <table className="workspace-table">
              <thead>
                <tr>
                  <th>Signal</th>
                  <th>Severity</th>
                  <th>Document</th>
                  <th>Reason</th>
                  <th>Review</th>
                </tr>
              </thead>
              <tbody>
                {controls.filtered.map((finding, index) => {
                  const key = `${finding.type}-${finding.documentId}`;
                  const busy = busyKey === key;
                  return (
                    <tr key={`${key}-${index}`}>
                      <td>{humanize(String(finding.type || "").toLowerCase().replace(/_/g, " "))}</td>
                      <td>
                        <StatusPill status={finding.severity} />
                      </td>
                      <td>
                        <strong>{finding.documentName}</strong>
                        <small>ID {finding.documentId}</small>
                        {canReview && finding.documentOwner && (
                          <small>Uploaded by {finding.documentOwner}</small>
                        )}
                      </td>
                      <td>
                        {finding.reason}
                        {finding.amount !== undefined && (
                          <small>
                            Amount {formatAmount(finding.amount)} vs median{" "}
                            {formatAmount(finding.medianObservedAmount)}
                          </small>
                        )}
                      </td>
                      <td>
                        <StatusPill status={finding.reviewStatus || "OPEN"} />
                        {finding.reviewNote && <small>{finding.reviewNote}</small>}
                        {(
                          finding.isApDocument
                            ? (
                                (roleName === "Finance User" &&
                                  (!finding.reviewStatus || finding.reviewStatus === "OPEN")) ||
                                (roleName === "Finance Manager" &&
                                  finding.reviewStatus === "FINANCE_USER_ESCALATED") ||
                                (roleName === "Chief Accountant" &&
                                  ["MANAGER_CONFIRMED", "MANAGER_DISMISSED"].includes(finding.reviewStatus))
                              )
                            : (
                                (roleName === "Finance Manager" &&
                                  (!finding.reviewStatus || finding.reviewStatus === "OPEN")) ||
                                (roleName === "Administrator" &&
                                  ["MANAGER_CONFIRMED", "MANAGER_DISMISSED"].includes(finding.reviewStatus))
                              )
                        ) && (
                          <div className="workspace-actions">
                            {finding.isApDocument && roleName === "Finance User" ? (
                              <button
                                type="button"
                                className="workspace-action approve"
                                disabled={busy}
                                onClick={() => decide(finding, "ESCALATE", "Escalated by Finance User for investigation.")}
                              >
                                {busy ? "Escalating..." : "Escalate to Manager"}
                              </button>
                            ) : (
                              <button
                                type="button"
                                className="workspace-action approve"
                                disabled={busy}
                                onClick={() => {
                                  setDialogError("");
                                  setReviewing(finding);
                                }}
                              >
                                {finding.isApDocument
                                  ? roleName === "Finance Manager"
                                    ? "Investigate signal"
                                    : "Chief Accountant final decision"
                                  : roleName === "Administrator"
                                  ? "Admin final decision"
                                  : "Manager review"}
                              </button>
                            )}
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>

    <FraudRiskPanel canReview={canReview} />

    <FraudReviewDialog
      finding={reviewing}
      busy={Boolean(busyKey)}
      error={dialogError}
      onClose={() => setReviewing(null)}
      onSubmit={(decision, note) => decide(reviewing, decision, note)}
    />
    </>
  );
}

/* --------------------------- finance analyst --------------------------- */

function AnalystWorkspace() {
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const messagesEndRef = useRef(null);
  const [newestFirst, setNewestFirst] = useState(false);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const visibleMessages = useMemo(() => {
    const numbered = messages.map((message, order) => ({ ...message, order }));
    return newestFirst ? [...numbered].reverse() : numbered;
  }, [messages, newestFirst]);

  async function handleSubmit(event) {
    event.preventDefault();
    const trimmed = question.trim();
    if (trimmed.length < 3 || sending) return;

    setMessages((current) => [
      ...current,
      { id: `user-${Date.now()}`, role: "user", content: trimmed },
    ]);
    setQuestion("");
    setSending(true);
    setError("");

    try {
      const response = await sendAssistantMessage(trimmed);
      setMessages((current) => [...current, response]);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="workspace-panel">
      <div className="workspace-panel-header">
        <div>
          <h2>Finance analysis assistant</h2>
          <p>Searches your uploaded documents (RAG) and answers only from the passages it finds, with cited sources.</p>
        </div>
        <StatusPill status="LIVE" />
      </div>

      <div className="workspace-suggestions">
        {[
          "Which uploaded invoices have missing totals?",
          "What GST amount appears on our invoices?",
          "Which vendor has the highest invoice total?",
        ].map((prompt) => (
          <button key={prompt} type="button" onClick={() => setQuestion(prompt)}>
            {prompt}
          </button>
        ))}
      </div>

      {messages.length > 1 && (
        <div className="workspace-toolbar">
          <button type="button" className="workspace-action" onClick={() => setNewestFirst((v) => !v)}>
            {newestFirst ? "↓ Newest first" : "↑ Oldest first"}
          </button>
        </div>
      )}

      <div className="workspace-chat-messages">
        {messages.length === 0 ? (
          <p className="workspace-muted">Ask a question about your uploaded documents.</p>
        ) : (
          visibleMessages.map((message, index) => (
            <article
              className={`workspace-chat-message ${message.role === "user" ? "is-user" : "is-assistant"}`}
              key={message.id ?? index}
            >
              <span>{message.role === "user" ? "YOU" : "FINANCE AI"}</span>
              <p style={{ whiteSpace: "pre-wrap" }}>{message.content}</p>
              {Array.isArray(message.sources) && message.sources.length > 0 && (
                <details className="workspace-sources">
                  <summary>
                    {message.sources.length} sources retrieved from your documents
                  </summary>
                  {message.sources.map((source) => (
                    <div className="workspace-source" key={source.ref}>
                      <strong>
                        [{source.ref}] {source.name}
                      </strong>
                      <small>
                        part {source.part} · relevance {source.score}
                      </small>
                      <p>{source.snippet}</p>
                    </div>
                  ))}
                </details>
              )}
            </article>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {error && <p className="workspace-error">{error}</p>}

      <form className="workspace-chat-form" onSubmit={handleSubmit}>
        <textarea
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask a finance question..."
          rows={2}
          aria-label="Finance question"
          maxLength={4000}
        />
        <button
          className="workspace-primary-button"
          type="submit"
          disabled={sending || question.trim().length < 3}
        >
          {sending ? "Analysing..." : "Send question"}
        </button>
      </form>
    </section>
  );
}

/* --------------------------- financial reporting --------------------------- */

function ReportingWorkspace({ onChanged }) {
  const [reports, setReports] = useState([]);
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [name, setName] = useState("Finance Summary");
  const [period, setPeriod] = useState("");
  const [lastRun, setLastRun] = useState(null);
  const [previewReport, setPreviewReport] = useState(null);
  const [downloadingId, setDownloadingId] = useState(null);
  const controls = useSearchSort(reports, {
    searchText: reportSearchText,
    sorts: REPORT_SORTS,
    defaultSort: { key: "newest", direction: "desc" },
  });

  async function handleReportDownload(report) {
    try {
      setDownloadingId(report.id);
      setError("");
      await downloadReport(report);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setDownloadingId(null);
    }
  }

  useEffect(() => {
    let active = true;

    getReportsData()
      .then((data) => {
        if (!active) return;
        setReports(Array.isArray(data?.reports) ? data.reports : []);
        setOverview(data?.overview || null);
      })
      .catch((requestError) => {
        if (active) setError(requestError.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  async function handleGenerate(event) {
    event.preventDefault();
    if (generating || !name.trim()) return;

    try {
      setGenerating(true);
      setError("");

      const result = await generateReport({
        name: name.trim(),
        period: period.trim(),
      });

      setReports((current) => [result, ...current]);
      setOverview((current) => ({
        ...(current || {}),
        totalReports: (current?.totalReports ?? 0) + 1,
        generatedThisMonth: (current?.generatedThisMonth ?? 0) + 1,
      }));
      setLastRun(result);
      onChanged();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setGenerating(false);
    }
  }

  return (
    <>
      <section className="workspace-summary-grid">
        <SummaryCard
          label="TOTAL REPORTS"
          value={overview?.totalReports ?? "—"}
          note="Saved for your account"
        />
        <SummaryCard
          label="GENERATED THIS MONTH"
          value={overview?.generatedThisMonth ?? "—"}
          note="Completed reports"
        />
        <SummaryCard
          label="SCHEDULED"
          value={overview?.scheduledReports ?? "—"}
          note="Scheduling is not configured"
        />
      </section>

      <section className="workspace-panel">
        <div className="workspace-panel-header">
          <div>
            <h2>Generate report</h2>
            <p>Creates a summary of figures extracted from your uploaded documents.</p>
          </div>
        </div>

        <form className="workspace-report-form" onSubmit={handleGenerate}>
          <input
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Report name"
            aria-label="Report name"
            maxLength={255}
          />
          <input
            type="text"
            value={period}
            onChange={(event) => setPeriod(event.target.value)}
            placeholder="Period (e.g. October 2026)"
            aria-label="Report period"
            maxLength={100}
          />
          <button
            className="workspace-primary-button"
            type="submit"
            disabled={generating || !name.trim()}
          >
            {generating ? "Generating..." : "＋ Generate report"}
          </button>
        </form>

        {error && <p className="workspace-error">{error}</p>}

        {lastRun?.data && (
          <div className="workspace-result">
            <div className="workspace-panel-header">
              <h3>Latest result: {lastRun.name}</h3>
              <div className="workspace-actions">
                <button type="button" className="workspace-action icon-action" title="Preview report" aria-label="Preview report" onClick={() => setPreviewReport(lastRun)}>
                  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>
                </button>
                <button
                  type="button"
                  className="workspace-action icon-action"
                  title="Download report"
                  aria-label="Download report"
                  disabled={downloadingId === lastRun.id}
                  onClick={() => handleReportDownload(lastRun)}
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5M12 15V3"/></svg>
                </button>
              </div>
            </div>
            <div className="workspace-summary-grid workspace-live-grid">
              {Object.entries(lastRun.data)
                .filter(([, value]) => typeof value !== "object" || value === null)
                .map(([key, value]) => (
                  <SummaryCard
                    key={key}
                    label={humanize(key).toUpperCase()}
                    value={formatValue(value)}
                  />
                ))}
            </div>
            {lastRun.limitations && (
              <p className="workspace-footnote">{lastRun.limitations}</p>
            )}
          </div>
        )}
      </section>

      <section className="workspace-panel">
        <div className="workspace-panel-header">
          <div>
            <h2>Report history</h2>
            <p>Reports previously generated for your account.</p>
          </div>
        </div>

        {loading ? (
          <SkeletonLoader variant="table" rows={5} />
        ) : reports.length === 0 ? (
          <div className="workspace-empty">
            <strong>No reports yet</strong>
          </div>
        ) : (
          <>
          <TableToolbar controls={controls} placeholder="Search report name, period, status..." label="reports" />
          {controls.filtered.length === 0 && (
            <p className="workspace-muted">No reports match your search.</p>
          )}
          <div className="workspace-table-wrap">
            <table className="workspace-table">
              <thead>
                <tr>
                  <th>Report</th>
                  <th>Category</th>
                  <th>Period</th>
                  <th>Generated</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {controls.filtered.map((report, index) => (
                  <tr key={report.id ?? index}>
                    <td>
                      <strong>{report.name}</strong>
                      <small>{report.format || "Report"}</small>
                    </td>
                    <td>{report.category || "—"}</td>
                    <td>{report.period || "Not specified"}</td>
                    <td>{report.generatedAt || "—"}</td>
                    <td>
                      <StatusPill status={report.status} />
                    </td>
                    <td className="workspace-actions">
                      {report.fileAvailable ? (
                        <>
                          <button
                            type="button"
                            className="workspace-action icon-action"
                            title="Preview report"
                            aria-label="Preview report"
                            onClick={() => setPreviewReport(report)}
                          >
                            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>
                          </button>
                          <button
                            type="button"
                            className="workspace-action icon-action"
                            title="Download report"
                            aria-label="Download report"
                            disabled={downloadingId === report.id}
                            onClick={() => handleReportDownload(report)}
                          >
                            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5M12 15V3"/></svg>
                          </button>
                        </>
                      ) : (
                        <small>File not available — regenerate</small>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          </>
        )}
      </section>

      {previewReport && (
        <ReportPreviewModal report={previewReport} onClose={() => setPreviewReport(null)} />
      )}
    </>
  );
}

/* ------------------------------- page ------------------------------- */

function EmployeeWorkspace({ employeeId }) {
  const employee = EMPLOYEES[employeeId];
  const dashboard = useDashboard(employee ? employeeId : null);

  if (!employee) {
    return (
      <div className="workspace-empty">
        <h1>Employee not found</h1>
        <p>This Finance AI employee is not configured.</p>
      </div>
    );
  }

  const isAnalyst = employeeId === 5;
  const isReporting = employeeId === 7;

  return (
    <div className="employee-workspace">
      <section className="workspace-page-header">
        <div>
          <span className="workspace-eyebrow">{employee.eyebrow}</span>
          <h1>{employee.name}</h1>
          <p>{employee.description}</p>
        </div>
        <div className="workspace-employee-badge">
          <span>AI EMPLOYEE</span>
          <strong>{String(employeeId).padStart(2, "0")}</strong>
          <StatusPill status="READY" />
        </div>
      </section>

      <section className="workspace-summary-grid">
        <SummaryCard
          label="WORKFLOW"
          value={employee.name}
          note="Dedicated employee workspace"
        />
        <SummaryCard
          label="CORE OUTPUT"
          value={employee.output}
          note="Intended workflow output"
        />
        <SummaryCard
          label="SERVICE MODE"
          value="Live"
          note="Connected to the Finance AI backend"
        />
      </section>

      <section className="workspace-panel workspace-capabilities">
        <div className="workspace-panel-header">
          <div>
            <h2>Workspace capabilities</h2>
            <p>Available actions and information for this employee.</p>
          </div>
        </div>
        <div className="workspace-capability-grid">
          {employee.capabilities.map((capability, index) => (
            <div className="workspace-capability" key={capability}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <strong>{capability}</strong>
            </div>
          ))}
        </div>
      </section>

      {!isAnalyst && (
        <DashboardSummary
          dashboard={dashboard.data}
          loading={dashboard.loading}
          error={dashboard.error}
        />
      )}

      {isAnalyst ? (
        <AnalystWorkspace key={employeeId} />
      ) : isReporting ? (
        <ReportingWorkspace key={employeeId} onChanged={dashboard.reload} />
      ) : employee.fraud ? (
        <FraudWorkspace
          key={employeeId}
          dashboard={dashboard.data}
          loading={dashboard.loading}
          error={dashboard.error}
          onChanged={dashboard.reload}
        />
      ) : (
        <DocumentsWorkspace
          key={employeeId}
          employee={employee}
          onChanged={dashboard.reload}
        />
      )}

      {employeeId === 1 && <ApPanel key="ap-workflows" />}
      {employeeId === 2 && <ArPanel key="ar-workflows" />}
      {employeeId === 3 && <InvoicePanel key="invoice-workflows" />}
      {employeeId === 4 && <ReconPanel key="recon-workflows" />}
      {isAnalyst && <AnalystTools key="analyst-tools" />}
      {employeeId === 6 && <ExpensePanel key="expense-workflows" />}
      {isReporting && (
        <>
          <StatementsPanel key="statements" />
          <SchedulesPanel key="schedules" />
        </>
      )}
    </div>
  );
}

export default EmployeeWorkspace;
