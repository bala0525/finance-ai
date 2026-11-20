import apiClient, { apiBlob, saveBlob } from "./apiClient";
import { generateFinancialReport } from "./agentsService";

/*
 * Reports service.
 *
 *   GET  /reports                       list + overview
 *   POST /agents/financial-reporting/generate   create a summary report
 *
 * The backend uses its own status/category vocabulary; the Reports UI uses
 * READY / PENDING / GENERATING and "Financial Reporting". Map between them here
 * so UI components stay unchanged.
 */

const STATUS_MAP = {
  COMPLETED: "READY",
  REQUESTED: "PENDING",
};

const CATEGORY_MAP = {
  "Financial Report": "Financial Reporting",
};

function formatDate(isoString) {
  if (!isoString) return "—";

  const date = new Date(isoString);

  if (Number.isNaN(date.getTime())) return "—";

  return date.toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function toUiReport(report) {
  return {
    id: report.id,
    name: report.name,
    category: CATEGORY_MAP[report.category] || report.category,
    period: report.period || "Not specified",
    frequency: "On Demand",
    generatedAt: formatDate(report.createdAt),
    status: STATUS_MAP[report.status] || report.status,
    format: report.format,
    fileAvailable: Boolean(report.fileAvailable),
    generatedBy: "AI Financial Reporting Employee",
  };
}

export async function getReportsData() {
  const data = await apiClient("/reports");

  const reports = Array.isArray(data?.reports) ? data.reports : [];
  const pending = reports.filter((report) => report.status === "REQUESTED").length;

  return {
    overview: {
      totalReports: data?.overview?.totalReports ?? reports.length,
      generatedThisMonth: data?.overview?.generatedThisMonth ?? 0,
      scheduledReports: data?.overview?.scheduledReports ?? 0,
      pendingReports: pending,
    },
    reports: reports.map(toUiReport),
  };
}

/*
 * Returns the UI-shaped report plus the calculated summary figures and the
 * limitations text from the backend.
 */
export async function generateReport(reportRequest = {}) {
  const result = await generateFinancialReport({
    name: reportRequest.name,
    period: reportRequest.period,
  });

  return {
    ...toUiReport(result.report),
    data: result.data,
    preview: result.preview,
    limitations: result.limitations,
  };
}

export async function getReportPreview(reportId) {
  return apiClient(`/reports/${reportId}/preview`);
}

export async function downloadReport(report) {
  const { blob, filename } = await apiBlob(`/reports/${report.id}/download`);
  saveBlob(blob, filename || `${report.name}.xlsx`);
}
