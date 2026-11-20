import React, { useEffect, useState } from "react";

import {
  getDocumentPreview,
  getDocumentFileBlob,
  downloadDocument,
} from "../../services/documentsService";
import { getReportPreview, downloadReport } from "../../services/reportsService";

function useEscape(onClose) {
  useEffect(() => {
    const handler = (event) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);
}

function Shell({ title, subtitle, onClose, onDownload, downloading, children }) {
  useEscape(onClose);
  return (
    <div className="preview-backdrop" role="dialog" aria-modal="true" aria-label={title} onClick={onClose}>
      <div className="preview-modal" onClick={(event) => event.stopPropagation()}>
        <header className="preview-header">
          <div>
            <h2>{title}</h2>
            {subtitle && <small>{subtitle}</small>}
          </div>
          <div className="preview-header-actions">
            {onDownload && (
              <button type="button" className="workspace-primary-button" onClick={onDownload} disabled={downloading}>
                {downloading ? "Downloading..." : "⬇ Download"}
              </button>
            )}
            <button type="button" className="workspace-action" onClick={onClose}>
              Close
            </button>
          </div>
        </header>
        <div className="preview-body">{children}</div>
      </div>
    </div>
  );
}

function SimpleTable({ headers, rows }) {
  return (
    <div className="workspace-table-wrap">
      <table className="workspace-table">
        <thead>
          <tr>{headers.map((h) => <th key={h}>{h}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>{row.map((cell, j) => <td key={j}>{cell}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const inr = (n) =>
  typeof n === "number"
    ? n.toLocaleString("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 })
    : "—";

export function DocumentPreviewModal({ document, onClose }) {
  const [state, setState] = useState({ loading: true, error: "", preview: null, pdfUrl: null });
  const [downloading, setDownloading] = useState(false);
  const [actionError, setActionError] = useState("");

  useEffect(() => {
    let active = true;
    let objectUrl = null;

    (async () => {
      try {
        const preview = await getDocumentPreview(document.id);
        let pdfUrl = null;
        if (preview.kind === "pdf") {
          const { blob } = await getDocumentFileBlob(document.id);
          objectUrl = URL.createObjectURL(blob);
          pdfUrl = objectUrl;
        }
        if (active) setState({ loading: false, error: "", preview, pdfUrl });
      } catch (error) {
        if (active) setState({ loading: false, error: error.message, preview: null, pdfUrl: null });
      }
    })();

    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [document.id]);

  async function handleDownload() {
    try {
      setDownloading(true);
      setActionError("");
      await downloadDocument(document);
    } catch (error) {
      setActionError(error.message);
    } finally {
      setDownloading(false);
    }
  }

  const { loading, error, preview, pdfUrl } = state;

  return (
    <Shell
      title={document.name}
      subtitle={`${document.type} · ${document.size} · ${document.category}`}
      onClose={onClose}
      onDownload={handleDownload}
      downloading={downloading}
    >
      {actionError && <p className="workspace-error">{actionError}</p>}
      {loading && <p className="workspace-muted">Loading preview...</p>}
      {error && <p className="workspace-error">{error}</p>}
      {preview?.kind === "pdf" && pdfUrl && (
        <iframe className="preview-frame" title={`Preview of ${document.name}`} src={pdfUrl} />
      )}
      {preview?.kind === "table" &&
        preview.sheets.map((sheet) => (
          <div key={sheet.name}>
            <h3>{sheet.name}</h3>
            {sheet.rows.length === 0 ? (
              <p className="workspace-muted">This sheet is empty.</p>
            ) : (
              <SimpleTable
                headers={sheet.rows[0].map((h, i) => h || `Column ${i + 1}`)}
                rows={sheet.rows.slice(1)}
              />
            )}
            {sheet.truncated && <p className="workspace-footnote">Showing the first rows only. Download for the full file.</p>}
          </div>
        ))}
      {preview?.kind === "text" && (
        <>
          <pre className="preview-text">{preview.text || "This document has no readable text."}</pre>
          {preview.truncated && <p className="workspace-footnote">Preview truncated. Download for the full file.</p>}
        </>
      )}
      {preview?.kind === "unsupported" && <p className="workspace-muted">{preview.message}</p>}
    </Shell>
  );
}

export function ReportPreviewModal({ report, onClose }) {
  const [state, setState] = useState({ loading: true, error: "", data: null });
  const [downloading, setDownloading] = useState(false);
  const [actionError, setActionError] = useState("");

  useEffect(() => {
    let active = true;
    getReportPreview(report.id)
      .then((result) => active && setState({ loading: false, error: "", data: result.data }))
      .catch((error) => active && setState({ loading: false, error: error.message, data: null }));
    return () => {
      active = false;
    };
  }, [report.id]);

  async function handleDownload() {
    try {
      setDownloading(true);
      setActionError("");
      await downloadReport(report);
    } catch (error) {
      setActionError(error.message);
    } finally {
      setDownloading(false);
    }
  }

  const { loading, error, data } = state;
  const s = data?.summary;

  return (
    <Shell
      title={report.name}
      subtitle={data ? `Period: ${data.period} · Generated ${data.generatedAt}` : report.period}
      onClose={onClose}
      onDownload={report.fileAvailable ? handleDownload : null}
      downloading={downloading}
    >
      {actionError && <p className="workspace-error">{actionError}</p>}
      {loading && <p className="workspace-muted">Loading report...</p>}
      {error && <p className="workspace-error">{error}</p>}
      {data && (
        <>
          <div className="workspace-summary-grid workspace-live-grid">
            {[
              ["DOCUMENTS", s.documentCount],
              ["WITH AMOUNTS", s.documentsWithExtractedAmounts],
              ["TOTAL EXTRACTED", inr(s.knownExtractedAmountTotal)],
              ["APPROVED", inr(s.approvedAmount)],
              ["AWAITING APPROVAL", inr(s.pendingApprovalAmount)],
            ].map(([label, value]) => (
              <article className="workspace-summary-card" key={label}>
                <span>{label}</span>
                <strong>{value}</strong>
              </article>
            ))}
          </div>

          <h3>By category</h3>
          <SimpleTable headers={["Category", "Documents", "Amount"]}
            rows={data.byCategory.map((r) => [r.category, r.count, inr(r.amount)])} />
          <h3>By status</h3>
          <SimpleTable headers={["Status", "Documents", "Amount"]}
            rows={data.byStatus.map((r) => [r.status, r.count, inr(r.amount)])} />
          {data.topVendors.length > 0 && (
            <>
              <h3>Top vendors</h3>
              <SimpleTable headers={["Vendor", "Documents", "Amount"]}
                rows={data.topVendors.map((r) => [r.vendor, r.count, inr(r.amount)])} />
            </>
          )}
          <h3>Documents</h3>
          <SimpleTable
            headers={["Document", "Category", "Vendor", "Invoice no.", "Total", "Status"]}
            rows={data.documents.slice(0, 100).map((r) => [r.name, r.category, r.vendor || "—", r.invoiceNumber || "—", inr(r.totalAmount), r.status])}
          />
          <p className="workspace-footnote">{data.limitations}</p>
        </>
      )}
    </Shell>
  );
}
