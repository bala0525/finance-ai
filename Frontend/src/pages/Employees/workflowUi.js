import React, { useCallback, useEffect, useRef, useState } from "react";
import { SkeletonLoader } from "../../components/common/Loader";

/* Small shared UI helpers for the advanced workflow panels. */

export function fmtInr(value) {
  const n = Number(value);
  return Number.isFinite(n)
    ? n.toLocaleString("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 })
    : "—";
}

export function fmtNum(value, digits = 2) {
  const n = Number(value);
  return Number.isFinite(n)
    ? n.toLocaleString("en-IN", { minimumFractionDigits: digits, maximumFractionDigits: digits })
    : "—";
}

export function fmtPct(value) {
  return value === null || value === undefined ? "—" : `${Number(value).toFixed(1)}%`;
}

export function fmtDate(value) {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime())
    ? String(value)
    : d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export function isoDate(date = new Date()) {
  const d = new Date(date);
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 10);
}

export function addDaysIso(days, from = new Date()) {
  const d = new Date(from);
  d.setDate(d.getDate() + days);
  return isoDate(d);
}

const TONES = {
  ok: ["RESOLVED", "PAID", "APPROVED", "APPROVE", "MARKED_SENT", "ACCEPTED", "LOW", "VALID", "CONFIRMED_OK", "DISMISSED"],
  bad: ["HIGH", "REJECTED", "REJECT", "WRITTEN_OFF", "OVERDUE_61_PLUS", "OVERDUE_31_60", "INVALID", "CONFIRMED", "ERROR"],
  warn: ["OPEN", "DRAFT", "PENDING", "IN_REVIEW", "MEDIUM", "PARTIAL", "SUGGESTED", "CHANGED", "OVERDUE_1_30", "DUE_SOON", "PAUSED", "ACTIVE", "DUE"],
};

export function Pill({ value, label }) {
  const key = String(value || "UNKNOWN").toUpperCase();
  const tone = TONES.bad.includes(key) ? "bad" : TONES.warn.includes(key) ? "warn" : TONES.ok.includes(key) ? "ok" : "info";
  return <span className={`wf-pill wf-pill-${tone}`}>{label || key.replace(/_/g, " ")}</span>;
}

export function Notice({ error, message }) {
  if (error) return <p className="workspace-error" role="alert">{error}</p>;
  if (message) return <p className="workspace-message" role="status">{message}</p>;
  return null;
}

export function Section({ title, subtitle, actions, children }) {
  return (
    <section className="workspace-panel wf-section">
      <div className="workspace-panel-header">
        <div>
          <h2>{title}</h2>
          {subtitle ? <p>{subtitle}</p> : null}
        </div>
        {actions ? <div className="wf-header-actions">{actions}</div> : null}
      </div>
      {children}
    </section>
  );
}

export function Stat({ label, value, note }) {
  return (
    <div className="wf-stat">
      <span>{label}</span>
      <strong>{value}</strong>
      {note ? <small>{note}</small> : null}
    </div>
  );
}

export function Empty({ title, children }) {
  return (
    <div className="workspace-empty">
      <strong>{title}</strong>
      {children ? <p>{children}</p> : null}
    </div>
  );
}

export function Button({ children, tone, busy, disabled, ...props }) {
  return (
    <button
      type="button"
      className={`workspace-action${tone ? ` ${tone}` : ""}`}
      {...props}
      disabled={Boolean(busy || disabled)}
    >
      {children}
    </button>
  );
}

export function PrimaryButton({ children, ...props }) {
  return (
    <button type="button" className="workspace-primary-button wf-primary" {...props}>
      {children}
    </button>
  );
}

export function Field({ label, children, hint }) {
  return (
    <label className="wf-field">
      <span>{label}</span>
      {children}
      {hint ? <small>{hint}</small> : null}
    </label>
  );
}

export function Table({ columns, rows, rowKey, empty = "Nothing to show.", loading = false }) {
  if (loading) return <SkeletonLoader variant="table" rows={4} />;
  if (!rows || rows.length === 0) return <p className="workspace-muted">{empty}</p>;
  return (
    <div className="workspace-table-wrap">
      <table className="workspace-table">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key || c.label} className={c.align === "right" ? "wf-right" : undefined}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={rowKey ? rowKey(row, index) : index}>
              {columns.map((c) => (
                <td key={c.key || c.label} className={c.align === "right" ? "wf-right" : undefined}>
                  {c.render ? c.render(row, index) : row[c.key] ?? "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* Loads data on mount; `reload()` refetches. Ignores results after unmount. */
export function useLoader(fetcher, { enabled = true } = {}) {
  const [state, setState] = useState({ data: null, loading: enabled, error: "" });
  const alive = useRef(true);
  const fetchRef = useRef(fetcher);
  fetchRef.current = fetcher;

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  const reload = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: "" }));
    try {
      const data = await fetchRef.current();
      if (alive.current) setState({ data, loading: false, error: "" });
    } catch (error) {
      if (alive.current) setState({ data: null, loading: false, error: error.message });
    }
  }, []);

  useEffect(() => {
    if (enabled) reload();
  }, [enabled, reload]);

  return { ...state, reload };
}

/* Runs an async action with shared busy / error / success state. */
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const run = useCallback(async (fn, successMessage) => {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await fn();
      if (successMessage) setMessage(successMessage);
      return result;
    } catch (e) {
      setError(e.message || "Something went wrong.");
      return undefined;
    } finally {
      setBusy(false);
    }
  }, []);

  return { busy, error, message, run, setError, setMessage };
}

/* Inline "add a note, then confirm" row used for resolve / write-off actions. */
export function NoteInline({ placeholder, confirmLabel, onConfirm, onCancel, busy }) {
  const [note, setNote] = useState("");
  return (
    <div className="wf-note-inline">
      <input
        type="text"
        value={note}
        maxLength={2000}
        autoFocus
        placeholder={placeholder}
        aria-label={placeholder}
        onChange={(e) => setNote(e.target.value)}
      />
      <Button tone="approve" busy={busy} disabled={!note.trim()} onClick={() => onConfirm(note.trim())}>
        {confirmLabel}
      </Button>
      <Button onClick={onCancel}>Cancel</Button>
    </div>
  );
}

export function BarChart({ items, valueKey = "value", labelKey = "label", format = fmtNum }) {
  const max = Math.max(1, ...items.map((i) => Math.abs(Number(i[valueKey]) || 0)));
  return (
    <div className="wf-bars" role="img" aria-label="Bar chart">
      {items.map((item, index) => {
        const value = Number(item[valueKey]) || 0;
        return (
          <div className="wf-bar-col" key={`${item[labelKey]}-${index}`} title={`${item[labelKey]}: ${format(value)}`}>
            <div className="wf-bar-track">
              <div className={`wf-bar${value < 0 ? " neg" : ""}`} style={{ height: `${Math.max(2, (Math.abs(value) / max) * 100)}%` }} />
            </div>
            <small>{item[labelKey]}</small>
          </div>
        );
      })}
    </div>
  );
}
