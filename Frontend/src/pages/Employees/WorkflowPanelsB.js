import React, { useEffect, useState } from "react";

import Modal from "../../components/common/Modal";
import { SkeletonLoader } from "../../components/common/Loader";
import useAuth from "../../hooks/useAuth";
import {
  getLedgerAccounts, seedLedgerAccounts, getTrialBalance, createLedgerJournal,
  getLedgerPeriodCloses, closeLedgerPeriod, getLedgerProfitAndLoss,
  getLedgerBalanceSheet, getLedgerCashFlow,
} from "../../services/ledgerService";
import {
  runVariance, runForecast, runScenario, runInsights,
  getExpensePolicies, saveExpensePolicies, getExpenseEvaluation, decideExpense, reimburseExpense,
  getFraudRisk, downloadEvidencePack,
  getLedgerStatus, downloadLedgerTemplate, importLedger, buildStatements, downloadStatements,
  getSchedules, createSchedule, scheduleAction, deleteSchedule,
} from "../../services/workflowService";
import {
  BarChart, Button, Empty, Field, Notice, Pill, PrimaryButton, Section, Stat, Table,
  addDaysIso, fmtDate, fmtInr, fmtNum, fmtPct, isoDate, useAction, useLoader,
} from "./workflowUi";

/* ============================== Finance Analyst ============================ */

function firstOfMonth(offset = 0) {
  const d = new Date();
  return isoDate(new Date(d.getFullYear(), d.getMonth() + offset, 1));
}
function lastOfMonth(offset = 0) {
  const d = new Date();
  return isoDate(new Date(d.getFullYear(), d.getMonth() + offset + 1, 0));
}

export function AnalystTools() {
  const [tab, setTab] = useState("insights");
  return (
    <Section
      title="Controlled analysis tools"
      subtitle="Every number below is calculated by the backend from your uploaded documents. AI only writes optional commentary."
      actions={
        <div className="wf-tabs" role="tablist">
          {[["insights", "Insights"], ["variance", "Variance"], ["forecast", "Forecast"], ["scenario", "Scenario"]].map(([key, label]) => (
            <button key={key} type="button" role="tab" aria-selected={tab === key} className={`wf-tab${tab === key ? " active" : ""}`} onClick={() => setTab(key)}>
              {label}
            </button>
          ))}
        </div>
      }
    >
      {tab === "insights" ? <InsightsTool /> : tab === "variance" ? <VarianceTool /> : tab === "forecast" ? <ForecastTool /> : <ScenarioTool />}
    </Section>
  );
}

const SEVERITY_LABEL = { ACTION: "Needs action", WATCH: "Keep an eye on", INFO: "For information" };

function InsightsTool() {
  const action = useAction();
  const [useAi, setUseAi] = useState(false);
  const [result, setResult] = useState(null);

  async function run() {
    setResult((await action.run(() => runInsights(useAi))) || null);
  }

  return (
    <>
      <p className="workspace-footnote">
        Management insights from your uploaded documents: spending trend, vendor concentration, overdue receivables,
        payables due soon, approval backlog, data quality and working-capital position. Each one is a fixed rule with its numbers shown.
      </p>
      <div className="wf-form-row">
        <label className="wf-check"><input type="checkbox" checked={useAi} onChange={(e) => setUseAi(e.target.checked)} /> Add an AI-written summary</label>
        <PrimaryButton disabled={action.busy} onClick={run}>{action.busy ? "Analysing..." : result ? "Refresh insights" : "Generate insights"}</PrimaryButton>
      </div>
      <Notice error={action.error} />
      {result ? (
        <>
          {result.summary ? (
            <div className="wf-commentary">
              <strong>AI summary</strong>
              <p>{result.summary.text}</p>
              <small>{result.summary.label}</small>
            </div>
          ) : null}
          <div className="wf-insights">
            {result.insights.map((item) => (
              <article className={`wf-insight wf-insight-${item.severity.toLowerCase()}`} key={item.code}>
                <div className="wf-insight-head">
                  <strong>{item.title}</strong>
                  <Pill value={item.severity === "ACTION" ? "HIGH" : item.severity === "WATCH" ? "MEDIUM" : "LOW"} label={SEVERITY_LABEL[item.severity]} />
                </div>
                <p>{item.message}</p>
              </article>
            ))}
          </div>
          <p className="workspace-footnote">Based on {result.documentCount} document(s) as of {fmtDate(result.asOf)}. {result.note}</p>
        </>
      ) : null}
    </>
  );
}

function VarianceTool() {
  const action = useAction();
  const [form, setForm] = useState({
    currentStart: firstOfMonth(0), currentEnd: lastOfMonth(0),
    baseStart: firstOfMonth(-1), baseEnd: lastOfMonth(-1),
    mode: "PERIOD", groupBy: "category", budgetText: "", useAi: false,
  });
  const [result, setResult] = useState(null);
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));

  async function run() {
    let budget = null;
    if (form.mode === "BUDGET") {
      budget = {};
      for (const line of form.budgetText.split("\n")) {
        const [name, amount] = line.split(/[:=,]/).map((x) => x.trim());
        if (!name) continue;
        const n = Number(amount);
        if (!Number.isFinite(n) || n < 0) {
          action.setError(`Budget line "${line}" needs the form  Name: amount`);
          return;
        }
        budget[name] = n;
      }
      if (Object.keys(budget).length === 0) {
        action.setError("Enter at least one budget line, e.g.  Expense: 50000");
        return;
      }
    }
    const data = await action.run(() =>
      runVariance({
        current_start: form.currentStart, current_end: form.currentEnd,
        base_start: form.mode === "PERIOD" ? form.baseStart : null,
        base_end: form.mode === "PERIOD" ? form.baseEnd : null,
        budget, group_by: form.groupBy, use_ai: form.useAi,
      })
    );
    setResult(data || null);
  }

  return (
    <>
      <div className="wf-form-row">
        <Field label="Current from"><input type="date" value={form.currentStart} onChange={set("currentStart")} /></Field>
        <Field label="Current to"><input type="date" value={form.currentEnd} onChange={set("currentEnd")} /></Field>
        <Field label="Compare against">
          <select value={form.mode} onChange={set("mode")}>
            <option value="PERIOD">Another period</option>
            <option value="BUDGET">My budget</option>
          </select>
        </Field>
        <Field label="Group by">
          <select value={form.groupBy} onChange={set("groupBy")}>
            <option value="category">Category</option>
            <option value="vendor">Vendor</option>
          </select>
        </Field>
      </div>
      {form.mode === "PERIOD" ? (
        <div className="wf-form-row">
          <Field label="Compare from"><input type="date" value={form.baseStart} onChange={set("baseStart")} /></Field>
          <Field label="Compare to"><input type="date" value={form.baseEnd} onChange={set("baseEnd")} /></Field>
        </div>
      ) : (
        <Field label="Budget (one per line)" hint="Use the same names as the group column, e.g. Expense: 50000">
          <textarea rows={4} value={form.budgetText} onChange={set("budgetText")} placeholder={"Expense: 50000\nAccounts Payable: 120000"} />
        </Field>
      )}
      <div className="wf-form-row">
        <label className="wf-check"><input type="checkbox" checked={form.useAi} onChange={set("useAi")} /> Add AI-written commentary</label>
        <PrimaryButton disabled={action.busy} onClick={run}>{action.busy ? "Calculating..." : "Run variance analysis"}</PrimaryButton>
      </div>
      <Notice error={action.error} />
      {result ? (
        <>
          <div className="wf-stats">
            <Stat label={result.basis === "BUDGET" ? "Budget" : "Comparison period"} value={fmtInr(result.totals.reference)} />
            <Stat label="Actual" value={fmtInr(result.totals.actual)} />
            <Stat label="Variance" value={fmtInr(result.totals.variance)} note={fmtPct(result.totals.variancePct)} />
          </div>
          <Table
            rows={result.lines}
            rowKey={(r) => r.group}
            columns={[
              { label: result.groupBy === "vendor" ? "Vendor" : "Category", key: "group" },
              { label: "Reference", align: "right", render: (r) => fmtNum(r.reference) },
              { label: "Actual", align: "right", render: (r) => fmtNum(r.actual) },
              { label: "Variance", align: "right", render: (r) => fmtNum(r.variance) },
              { label: "%", align: "right", render: (r) => fmtPct(r.variancePct) },
            ]}
          />
          <div className="wf-commentary">
            <strong>{result.commentary.ai ? "AI commentary" : "Summary"}</strong>
            <p>{result.commentary.text}</p>
            {result.commentary.label ? <small>{result.commentary.label}</small> : null}
          </div>
        </>
      ) : null}
    </>
  );
}

function ForecastTool() {
  const action = useAction();
  const [method, setMethod] = useState("moving_average");
  const [periods, setPeriods] = useState(3);
  const [result, setResult] = useState(null);

  async function run() {
    setResult((await action.run(() => runForecast({ method, periods: Number(periods) }))) || null);
  }

  const series = result ? [...result.history.slice(-9), ...result.forecast.map((f) => ({ ...f, projected: true }))] : [];
  return (
    <>
      <div className="wf-form-row">
        <Field label="Method">
          <select value={method} onChange={(e) => setMethod(e.target.value)}>
            <option value="moving_average">Moving average (3 months)</option>
            <option value="linear_trend">Linear trend</option>
          </select>
        </Field>
        <Field label="Months ahead">
          <input type="number" min="1" max="12" value={periods} onChange={(e) => setPeriods(Math.max(1, Math.min(12, Number(e.target.value) || 1)))} />
        </Field>
        <PrimaryButton disabled={action.busy} onClick={run}>{action.busy ? "Forecasting..." : "Run forecast"}</PrimaryButton>
      </div>
      <Notice error={action.error} />
      {result ? (
        <>
          <p className="workspace-footnote">{result.explanation}</p>
          {result.warnings.map((w) => (<p className="wf-warn" key={w}>{w}</p>))}
          <BarChart items={series.map((s) => ({ label: s.period.slice(2) + (s.projected ? "*" : ""), value: s.value }))} format={fmtInr} />
          <p className="workspace-footnote">* projected. Based on monthly document totals; it is an explainable estimate, not a promise.</p>
          <Table
            rows={result.forecast}
            rowKey={(r) => r.period}
            columns={[{ label: "Month", key: "period" }, { label: "Forecast", align: "right", render: (r) => fmtInr(r.value) }]}
          />
        </>
      ) : null}
    </>
  );
}

function ScenarioTool() {
  const action = useAction();
  const [form, setForm] = useState({ revenue: 0, expense: 0, delay: 0 });
  const [result, setResult] = useState(null);
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  async function run() {
    setResult(
      (await action.run(() =>
        runScenario({
          revenue_change_pct: Number(form.revenue) || 0,
          expense_change_pct: Number(form.expense) || 0,
          collection_delay_days: Math.round(Number(form.delay) || 0),
        })
      )) || null
    );
  }

  return (
    <>
      <div className="wf-form-row">
        <Field label="Revenue change %"><input type="number" min="-100" max="1000" value={form.revenue} onChange={set("revenue")} /></Field>
        <Field label="Expense change %"><input type="number" min="-100" max="1000" value={form.expense} onChange={set("expense")} /></Field>
        <Field label="Collection delay (days)"><input type="number" min="0" max="365" value={form.delay} onChange={set("delay")} /></Field>
        <PrimaryButton disabled={action.busy} onClick={run}>{action.busy ? "Calculating..." : "Run scenario"}</PrimaryButton>
      </div>
      <Notice error={action.error} />
      {result ? (
        <>
          <Table
            rows={[
              { item: "Revenue", base: result.base.revenue, scenario: result.scenario.revenue },
              { item: "Expenses", base: result.base.expenses, scenario: result.scenario.expenses },
              { item: "Net result", base: result.base.net, scenario: result.scenario.net },
              { item: "Cash inflows, next 12 weeks", base: result.base.inflowsNext12Weeks, scenario: result.scenario.inflowsNext12Weeks },
            ]}
            rowKey={(r) => r.item}
            columns={[
              { label: "Item", key: "item" },
              { label: "Base", align: "right", render: (r) => fmtInr(r.base) },
              { label: "Scenario", align: "right", render: (r) => fmtInr(r.scenario) },
              { label: "Change", align: "right", render: (r) => fmtInr(r.scenario - r.base) },
            ]}
          />
          <BarChart items={result.weeklyInflows.map((w) => ({ label: `W${w.week}`, value: w.scenario }))} format={fmtInr} />
          <p className="workspace-footnote">Weekly inflows under the scenario. {result.basis}</p>
        </>
      ) : null}
    </>
  );
}

/* ================================== Expense ================================ */

export function ExpensePanel() {
  const { currentUser } = useAuth();
  const canReview = Boolean(currentUser?.can_review);
  const isFinanceManager = currentUser?.role_name === "Finance Manager";
  const isFinanceUser = currentUser?.role_name === "Finance User";
  const policies = useLoader(getExpensePolicies);
  const evaluation = useLoader(getExpenseEvaluation);
  const action = useAction();
  const [draft, setDraft] = useState(null);
  const [deciding, setDeciding] = useState(null);
  const [form, setForm] = useState({ decision: "APPROVED", amount: "", note: "" });

  useEffect(() => {
    if (policies.data) {
      setDraft(policies.data.policies.map((p) => ({ ...p, claimLimit: p.claimLimit ?? "" })));
    }
  }, [policies.data]);

  async function savePolicies() {
    const body = draft.map((p) => ({
      expense_type: p.expenseType,
      claim_limit: p.claimLimit === "" ? null : Number(p.claimLimit),
      receipt_required: p.receiptRequired,
    }));
    if (await action.run(() => saveExpensePolicies(body), "Policy saved.")) {
      policies.reload();
      evaluation.reload();
    }
  }

  async function decide(row) {
    const done = await action.run(
      () => decideExpense({ documentId: row.documentId, decision: form.decision, approvedAmount: form.decision === "PARTIAL" ? form.amount : null, note: form.note }),
      "Reimbursement decision saved."
    );
    if (done) {
      setDeciding(null);
      evaluation.reload();
    }
  }

  // NEW: Finance User-only reimbursement completion with automatic ledger posting.
  async function reimburse(row) {
    if (await action.run(() => reimburseExpense(row.documentId), "Expense reimbursed and posted to the General Ledger.")) {
      evaluation.reload();
    }
  }

  function startDeciding(row) {
    const rec = row.recommendation;
    setDeciding(row.documentId);
    setForm({
      decision: isFinanceUser ? "VERIFIED" : (rec.decision === "APPROVE" ? "APPROVED" : rec.decision === "PARTIAL" ? "PARTIAL" : "REJECTED"),
      amount: rec.decision === "PARTIAL" ? String(row.decision?.approvedAmount || rec.allowedAmount) : "",
      note: "",
    });
  }

  const defaults = (policies.data?.policies || []).some((p) => p.isDefault);

  return (
    <>
      <Section
        title="Expense policy"
        subtitle="Limits per expense type. Claims are checked against these automatically."
        actions={canReview && draft ? <PrimaryButton disabled={action.busy} onClick={savePolicies}>Save policy</PrimaryButton> : null}
      >
        <Notice error={policies.error || action.error} message={action.message} />
        {defaults ? <p className="wf-warn">These are starter defaults, not your company policy. {canReview ? "Edit and save them to make them yours." : "An Administrator or Finance Manager can edit them."}</p> : null}
        <Table
          rows={draft}
          rowKey={(r) => r.expenseType}
          columns={[
            { label: "Expense type", key: "expenseType" },
            {
              label: "Limit per claim (INR)",
              render: (r) => (
                <input
                  className="wf-cell-input" type="number" min="0" disabled={!canReview} value={r.claimLimit} placeholder="No limit"
                  onChange={(e) => setDraft((d) => d.map((x) => (x.expenseType === r.expenseType ? { ...x, claimLimit: e.target.value } : x)))}
                />
              ),
            },
            {
              label: "Receipt number required",
              render: (r) => (
                <input
                  type="checkbox" disabled={!canReview} checked={r.receiptRequired} aria-label={`Receipt required for ${r.expenseType}`}
                  onChange={(e) => setDraft((d) => d.map((x) => (x.expenseType === r.expenseType ? { ...x, receiptRequired: e.target.checked } : x)))}
                />
              ),
            },
            { label: "Source", render: (r) => <Pill value={r.isDefault ? "DRAFT" : "APPROVED"} label={r.isDefault ? "DEFAULT" : "CUSTOM"} /> },
          ]}
        />
      </Section>

      <Section title="Policy check and reimbursement recommendation" subtitle="A recommendation only. A person confirms each decision, and it is recorded in the document history.">
        <Notice error={evaluation.error} />
        <Table
          loading={evaluation.loading}
          rows={evaluation.data?.expenses}
          rowKey={(r) => r.documentId}
          empty={evaluation.loading ? "Checking claims..." : "No expense documents yet."}
          columns={[
            { label: "Claim", render: (r) => (<><strong>{r.vendor || r.documentName}</strong><small>{r.expenseType} · {r.invoiceNumber || "no receipt no."} · {fmtDate(r.date)}</small></>) },
            { label: "Amount", align: "right", render: (r) => (r.amount === null ? "—" : fmtNum(r.amount)) },
            {
              label: "Policy findings",
              render: (r) => r.violations.length === 0
                ? <Pill value="APPROVED" label="WITHIN POLICY" />
                : (<div>{r.violations.map((v) => (<small key={v.code} className="wf-wrap"><Pill value={v.severity} /> {v.message}</small>))}</div>),
            },
            {
              label: "Recommendation",
              render: (r) => (<><Pill value={r.recommendation.decision} />{r.recommendation.decision === "PARTIAL" ? <small>Up to {fmtNum(r.recommendation.allowedAmount)}</small> : null}</>),
            },
            {
              label: "Decision",
              render: (r) => {
                const stage = r.decision?.decision || null;
                const awaitingManager = stage === "FINANCE_USER_VERIFIED";
                const finalDecision = ["APPROVED", "PARTIAL", "REJECTED", "CHANGES_REQUESTED"].includes(stage);
                if (finalDecision) {
                  return (
                    <>
                      <Pill value={stage} />
                      <small>{stage === "REJECTED" ? "Rejected" : stage === "CHANGES_REQUESTED" ? "Returned for correction" : `Approved reimbursement ${fmtNum(r.decision.approvedAmount)}`}</small>
                      {r.decision.note ? <small className="wf-wrap">{r.decision.note}</small> : null}
                      {isFinanceUser && ["APPROVED", "PARTIAL"].includes(stage) && r.status === "PENDING_PAYMENT" ? (
                        <Button tone="approve" busy={action.busy} onClick={() => reimburse(r)}>Record reimbursement</Button>
                      ) : null}
                      {r.status === "PAID" ? <small>Paid and posted · Voucher {r.ledgerVoucherNo || "—"}</small> : null}
                    </>
                  );
                }
                if (awaitingManager && !isFinanceManager) return <><Pill value={stage} /><small>Finance User verified · Awaiting Finance Manager review</small></>;
                const canVerify = isFinanceUser && !stage;
                const canManagerDecide = isFinanceManager && awaitingManager;
                if (!canVerify && !canManagerDecide) return <small>{stage ? `Current stage: ${stage.replace(/_/g, " ")}` : "Awaiting Finance User verification"}</small>;
                if (deciding !== r.documentId) return <Button tone="approve" onClick={() => startDeciding(r)}>{canVerify ? "Verify claim" : "Finance Manager decision"}</Button>;
                if (canVerify) return (
                  <div className="wf-decide">
                    <input type="text" maxLength={2000} placeholder="Verification note (optional)" value={form.note} onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))} />
                    <div className="workspace-actions"><Button tone="approve" busy={action.busy} onClick={() => decide(r)}>Confirm verification</Button><Button onClick={() => setDeciding(null)}>Cancel</Button></div>
                  </div>
                );
                return (
                  <div className="wf-decide">
                    <select value={form.decision} onChange={(e) => setForm((f) => ({ ...f, decision: e.target.value }))} aria-label="Decision">
                      <option value="APPROVED">Approve in full</option>
                      <option value="PARTIAL">Approve part</option>
                      <option value="REJECTED">Reject</option>
                      <option value="CHANGES_REQUESTED">Send back for resubmission</option>
                    </select>
                    {form.decision === "PARTIAL" ? (
                      <input type="number" min="0" placeholder="Amount to pay" value={form.amount} onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))} />
                    ) : null}
                    <input type="text" maxLength={2000} placeholder={["REJECTED", "CHANGES_REQUESTED"].includes(form.decision) ? "Reason / correction instructions (required)" : "Note (optional)"} value={form.note} onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))} />
                    <div className="workspace-actions">
                      <Button tone="approve" busy={action.busy} onClick={() => decide(r)}>Confirm</Button>
                      <Button onClick={() => setDeciding(null)}>Cancel</Button>
                    </div>
                  </div>
                );
              },
            },
          ]}
        />
      </Section>
    </>
  );
}

/* ============================ Fraud: risk + review ========================= */

export function FraudRiskPanel({ canReview }) {
  const risk = useLoader(getFraudRisk);
  const action = useAction();
  const docs = risk.data?.documents || [];
  const [showAll, setShowAll] = useState(false);
  const shown = showAll ? docs : docs.filter((d) => d.score > 0).slice(0, 15);

  return (
    <Section
      title="Risk scores"
      subtitle="Each document and vendor gets a 0-100 score from documented rules. Scores help you decide what to look at first. They are not proof of fraud."
      actions={<Button onClick={() => setShowAll((v) => !v)}>{showAll ? "Show only scored" : "Show all documents"}</Button>}
    >
      <Notice error={risk.error || action.error} />
      {risk.data ? (
        <p className="workspace-footnote">
          Bands: High {risk.data.bands.HIGH}, Medium {risk.data.bands.MEDIUM}, Low {risk.data.bands.LOW}. Rule weights: {Object.entries(risk.data.ruleWeights).map(([k, v]) => `${k.replace(/_/g, " ").toLowerCase()} ${v}`).join(" · ")}.
        </p>
      ) : null}
      <Table
        loading={risk.loading}
        rows={shown}
        rowKey={(r) => r.documentId}
        empty={risk.loading ? "Scoring documents..." : "No document triggered a risk rule."}
        columns={[
          { label: "Document", render: (r) => (<><strong>{r.documentName}</strong><small>{r.vendor || "Vendor not extracted"} · {r.amount === null ? "no amount" : fmtNum(r.amount)}</small></>) },
          { label: "Score", render: (r) => (<><strong>{r.score}</strong><Pill value={r.band} /></>) },
          { label: "Why", render: (r) => (r.rules.length ? (<div>{r.rules.map((x) => (<small className="wf-wrap" key={x.code} title={x.description}>+{x.weight} {x.code.replace(/_/g, " ").toLowerCase()}{x.detail ? ` (${x.detail})` : ""}</small>))}</div>) : <small>No rules triggered</small>) },
          {
            label: "Evidence",
            render: (r) => canReview && r.score > 0
              ? <Button busy={action.busy} onClick={() => action.run(() => downloadEvidencePack(r.documentId))}>Evidence pack</Button>
              : <small>{canReview ? "—" : "Admin / Finance Manager"}</small>,
          },
        ]}
      />
      {risk.data?.vendors?.length ? (
        <>
          <h3 className="wf-subhead">Vendor risk</h3>
          <Table
            rows={risk.data.vendors.filter((v) => v.score > 0).slice(0, 10)}
            rowKey={(v) => v.vendor}
            empty="No vendor has a risk score above zero."
            columns={[
              { label: "Vendor", key: "vendor" },
              { label: "Documents", align: "right", key: "documentCount" },
              { label: "High-risk docs", align: "right", key: "highDocuments" },
              { label: "Score", render: (v) => (<><strong>{v.score}</strong><Pill value={v.band} /></>) },
            ]}
          />
        </>
      ) : null}
    </Section>
  );
}

const QUICK_REASONS = {
  DISMISSED: ["Verified with the vendor", "Legitimate recurring invoice", "Amount approved by management", "Corrected or already credited"],
  CONFIRMED: ["Duplicate payment prevented", "Vendor could not verify the invoice", "Amount does not match the purchase order", "Needs further investigation"],
};

/* Friendly review dialog: pick an outcome, tap a reason, optionally add detail. */
export function FraudReviewDialog({ finding, onClose, onSubmit, busy, error }) {
  const [decision, setDecision] = useState("DISMISSED");
  const [note, setNote] = useState("");

  useEffect(() => {
    setDecision(["CONFIRMED", "MANAGER_CONFIRMED"].includes(finding?.reviewStatus) ? "CONFIRMED" : "DISMISSED");
    setNote(finding?.reviewNote || "");
  }, [finding]);

  if (!finding) return null;
  const needsNote = decision === "CONFIRMED";
  const canSave = !needsNote || note.trim().length >= 3;

  function addReason(text) {
    setNote((current) => (current.includes(text) ? current : current.trim() ? `${current.trim()}. ${text}` : text));
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Review risk signal"
      size="md"
      footer={
        <div className="wf-dialog-footer">
          <Button onClick={onClose}>Cancel</Button>
          <PrimaryButton disabled={busy || !canSave} onClick={() => onSubmit(decision, note.trim())}>
            {busy ? "Saving..." : decision === "CONFIRMED" ? "Confirm as suspicious" : "Dismiss as false alarm"}
          </PrimaryButton>
        </div>
      }
    >
      <div className="wf-dialog">
        <div className="wf-dialog-summary">
          <strong>{finding.documentName}</strong>
          <small>{String(finding.type || "").replace(/_/g, " ").toLowerCase()}</small>
          <p>{finding.reason}</p>
        </div>

        <fieldset className="wf-choice-group">
          <legend>What is your decision?</legend>
          <label className={`wf-choice${decision === "DISMISSED" ? " selected ok" : ""}`}>
            <input type="radio" name="fraud-decision" checked={decision === "DISMISSED"} onChange={() => setDecision("DISMISSED")} />
            <span><strong>False alarm</strong><small>This is legitimate. Dismiss the signal.</small></span>
          </label>
          <label className={`wf-choice${decision === "CONFIRMED" ? " selected bad" : ""}`}>
            <input type="radio" name="fraud-decision" checked={decision === "CONFIRMED"} onChange={() => setDecision("CONFIRMED")} />
            <span><strong>Suspicious</strong><small>This needs action. A reason is required.</small></span>
          </label>
        </fieldset>

        <div>
          <span className="wf-label">Quick reasons (tap to add)</span>
          <div className="wf-chips">
            {QUICK_REASONS[decision].map((reason) => (
              <button type="button" key={reason} className="wf-chip" onClick={() => addReason(reason)}>{reason}</button>
            ))}
          </div>
        </div>

        <Field label={needsNote ? "Remarks (required)" : "Remarks (optional)"}>
          <textarea rows={4} maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Add any detail that will help the next reviewer." />
          <small className="wf-counter">{note.length}/2000</small>
        </Field>
        {needsNote && !canSave ? <p className="wf-warn">Please add a short reason before confirming.</p> : null}
        <Notice error={error} />
      </div>
    </Modal>
  );
}

/* ========================== Financial Reporting ============================ */

export function StatementsPanel() {
  const ledger = useLoader(getLedgerStatus);
  const action = useAction();
  const [form, setForm] = useState({
    start: firstOfMonth(-1), end: lastOfMonth(-1), compareStart: firstOfMonth(-2), compareEnd: lastOfMonth(-2), compare: true, useAi: false,
  });
  const [result, setResult] = useState(null);
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));
  const hasLedger = (ledger.data?.journalLineCount || 0) > 0;

  async function upload(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (await action.run(() => importLedger(file), "Ledger entries imported and appended without deleting existing records.")) {
      ledger.reload();
      setResult(null);
    }
  }

  async function build() {
    const data = await action.run(() =>
      buildStatements({
        start: form.start, end: form.end,
        compare_start: form.compare ? form.compareStart : null,
        compare_end: form.compare ? form.compareEnd : null,
        use_ai: form.useAi,
      })
    );
    setResult(data || null);
  }

  const st = result?.statements;
  return (
    <>
      <Section
        title="Ledger"
        subtitle="Statements are built from your ledger accounts and journal entries. Import a workbook with 'Accounts' and 'Journal' sheets."
        actions={
          <>
            <Button onClick={() => action.run(() => downloadLedgerTemplate())}>Download template</Button>
            <label className="workspace-primary-button wf-primary wf-file">
              Import ledger (XLSX)
              <input type="file" accept=".xlsx,.xlsm" hidden onChange={upload} disabled={action.busy} />
            </label>
          </>
        }
      >
        <Notice error={action.error || ledger.error} message={action.message} />
        {ledger.loading ? <SkeletonLoader variant="cards" /> : <div className="wf-stats">
          <Stat label="Accounts" value={ledger.data?.accountCount ?? "—"} />
          <Stat label="Journal lines" value={ledger.data?.journalLineCount ?? "—"} />
          <Stat label="GL balance" value={ledger.loading ? "Checking..." : (ledger.data?.isBalanced ? "Balanced" : "Needs review")} note={ledger.data ? `${ledger.data.unbalancedVoucherCount || 0} unbalanced vouchers` : "Journal verification"} />
          <Stat label="Entries from" value={fmtDate(ledger.data?.firstEntry)} note={ledger.data?.lastEntry ? `to ${fmtDate(ledger.data.lastEntry)}` : null} />
          <Stat label="Last import" value={ledger.data?.lastImport?.filename || "None"} />
        </div>}
        {ledger.data && !ledger.data.isBalanced && (ledger.data.unbalancedVouchers || []).length > 0 ? (
          <div className="wf-warn" role="alert">
            <strong>General Ledger validation found unbalanced vouchers.</strong>
            {(ledger.data.unbalancedVouchers || []).slice(0, 5).map((voucher) => (
              <p key={voucher.voucherNo}>{voucher.voucherNo}: Debit {fmtInr(voucher.debit)} · Credit {fmtInr(voucher.credit)}</p>
            ))}
          </div>
        ) : ledger.data?.isBalanced ? (
          <p className="workspace-message" role="status">General Ledger debit and credit totals are balanced, and all vouchers have at least two lines.</p>
        ) : null}
        <p className="workspace-footnote">Importing replaces your existing ledger. Every voucher must balance (debit = credit).</p>
      </Section>

      <Section title="P&L, Balance Sheet and Cash Flow" subtitle="Pick a period. Optionally compare with an earlier period for variance and commentary.">
        {!hasLedger ? (
          <Empty title="No ledger data yet">Download the template, fill in your accounts and journal, then import it.</Empty>
        ) : (
          <>
            <div className="wf-form-row">
              <Field label="From"><input type="date" value={form.start} onChange={set("start")} /></Field>
              <Field label="To"><input type="date" value={form.end} onChange={set("end")} /></Field>
              <label className="wf-check"><input type="checkbox" checked={form.compare} onChange={set("compare")} /> Compare with</label>
              {form.compare ? (
                <>
                  <Field label="From"><input type="date" value={form.compareStart} onChange={set("compareStart")} /></Field>
                  <Field label="To"><input type="date" value={form.compareEnd} onChange={set("compareEnd")} /></Field>
                  <label className="wf-check"><input type="checkbox" checked={form.useAi} onChange={set("useAi")} /> AI-written commentary</label>
                </>
              ) : null}
            </div>
            <div className="wf-form-row">
              <PrimaryButton disabled={action.busy} onClick={build}>{action.busy ? "Building..." : "Build statements"}</PrimaryButton>
              {st ? (
                <Button onClick={() => action.run(() => downloadStatements({ start: form.start, end: form.end, compareStart: form.compare ? form.compareStart : null, compareEnd: form.compare ? form.compareEnd : null }))}>
                  Export XLSX pack
                </Button>
              ) : null}
            </div>
          </>
        )}

        {st ? (
          <>
            {st.warnings.map((w) => (<p className="wf-warn" key={w}>{w}</p>))}
            <div className="wf-stats">
              <Stat label="Revenue" value={fmtInr(st.profitAndLoss.revenue.total)} />
              <Stat label="Gross profit" value={fmtInr(st.profitAndLoss.grossProfit)} />
              <Stat label="Net profit" value={fmtInr(st.profitAndLoss.netProfit)} />
              <Stat label="Total assets" value={fmtInr(st.balanceSheet.assets.total)} note={`As of ${fmtDate(st.balanceSheet.asOf)}`} />
              <Stat label="Net change in cash" value={fmtInr(st.cashFlow.netChangeInCash)} />
            </div>

            <h3 className="wf-subhead">Profit and loss</h3>
            <StatementTable
              groups={[
                ["Revenue", st.profitAndLoss.revenue],
                ["Cost of goods sold", st.profitAndLoss.costOfGoodsSold],
                ["Operating expenses", st.profitAndLoss.operatingExpenses],
              ]}
              footer={[["Gross profit", st.profitAndLoss.grossProfit], ["Net profit", st.profitAndLoss.netProfit]]}
            />

            <h3 className="wf-subhead">Balance sheet</h3>
            <StatementTable
              groups={[["Assets", st.balanceSheet.assets], ["Liabilities", st.balanceSheet.liabilities], ["Equity", { rows: [...st.balanceSheet.equity.rows, { code: "", name: "Current earnings", amount: st.balanceSheet.equity.currentEarnings }], total: st.balanceSheet.equity.total }]]}
              footer={[["Balance check (should be 0)", st.balanceSheet.balanceCheck]]}
            />

            <h3 className="wf-subhead">Cash flow</h3>
            <Table
              rows={[
                ["Net profit", st.cashFlow.operating.netProfit],
                ["Change in other assets", st.cashFlow.operating.changeInOtherAssets],
                ["Change in other liabilities", st.cashFlow.operating.changeInOtherLiabilities],
                ["Operating cash flow", st.cashFlow.operating.total],
                ["Investing cash flow", st.cashFlow.investing.total],
                ["Financing cash flow", st.cashFlow.financing.total],
                ["Net change in cash (calculated)", st.cashFlow.netChangeInCash],
                ["Actual change in cash", st.cashFlow.actualChangeInCash],
                ["Unexplained difference", st.cashFlow.unexplainedDifference],
              ]}
              rowKey={(r) => r[0]}
              columns={[{ label: "Item", render: (r) => r[0] }, { label: "Amount", align: "right", render: (r) => fmtNum(r[1]) }]}
            />
            <p className="workspace-footnote">{st.cashFlow.method}</p>

            {result.comparison ? (
              <>
                <h3 className="wf-subhead">Variance and commentary</h3>
                <Table
                  rows={result.comparison.variances}
                  rowKey={(r) => r.metric}
                  columns={[
                    { label: "Metric", key: "metric" },
                    { label: "Previous", align: "right", render: (r) => fmtNum(r.previous) },
                    { label: "Current", align: "right", render: (r) => fmtNum(r.current) },
                    { label: "Variance", align: "right", render: (r) => fmtNum(r.variance) },
                    { label: "%", align: "right", render: (r) => fmtPct(r.variancePct) },
                  ]}
                />
                <div className="wf-commentary">
                  <strong>Commentary (calculated)</strong>
                  <ul>{result.commentary.lines.map((line) => (<li key={line}>{line}</li>))}</ul>
                  {result.commentary.ai ? (<><strong>AI wording</strong><p>{result.commentary.ai.text}</p><small>{result.commentary.ai.label}</small></>) : null}
                </div>
              </>
            ) : null}
          </>
        ) : null}
      </Section>
      <GeneralLedgerControls />
    </>
  );
}

function GeneralLedgerControls() {
  const { currentUser } = useAuth();
  const accounts = useLoader(getLedgerAccounts);
  const trial = useLoader(() => getTrialBalance());
  const periods = useLoader(getLedgerPeriodCloses);
  const action = useAction();
  const canPost = ["Chief Accountant", "Administrator"].includes(currentUser?.role_name);
  const isChief = currentUser?.role_name === "Chief Accountant";
  const [voucher, setVoucher] = useState("");
  const [entryDate, setEntryDate] = useState(isoDate(new Date()));
  const [narration, setNarration] = useState("");
  const [debitCode, setDebitCode] = useState("");
  const [creditCode, setCreditCode] = useState("");
  const [amount, setAmount] = useState("");
  const [periodStart, setPeriodStart] = useState(firstOfMonth(-1));
  const [periodEnd, setPeriodEnd] = useState(lastOfMonth(-1));
  const [reason, setReason] = useState("");
  const [reportStart, setReportStart] = useState(firstOfMonth(-1));
  const [reportEnd, setReportEnd] = useState(lastOfMonth(-1));
  const [statements, setStatements] = useState(null);
  const accountRows = accounts.data?.accounts || [];

  async function seed() {
    if (await action.run(() => seedLedgerAccounts(), "Default Chart of Accounts ready.")) accounts.reload();
  }
  async function postJournal() {
    const value = Number(amount);
    if (!voucher.trim() || !narration.trim() || !debitCode || !creditCode || !Number.isFinite(value) || value <= 0) return;
    if (await action.run(() => createLedgerJournal({
      voucher_no: voucher.trim(), entry_date: entryDate, narration: narration.trim(),
      lines: [
        { account_code: debitCode, debit: value.toFixed(2), credit: "0.00" },
        { account_code: creditCode, debit: "0.00", credit: value.toFixed(2) },
      ],
    }), "Balanced journal posted.")) {
      setVoucher(""); setNarration(""); setAmount("");
      trial.reload(); accounts.reload();
    }
  }
  async function closeMonth() {
    if (await action.run(() => closeLedgerPeriod({ period_start: periodStart, period_end: periodEnd, reason }), "Accounting period closed.")) periods.reload();
  }
  async function loadLedgerStatements() {
    const result = await action.run(async () => {
      const [pl, bs, cf] = await Promise.all([
        getLedgerProfitAndLoss(reportStart, reportEnd),
        getLedgerBalanceSheet(reportEnd),
        getLedgerCashFlow(reportStart, reportEnd),
      ]);
      return { pl, bs, cf };
    });
    if (result) setStatements(result);
  }

  return (
    <Section title="General Ledger controls" subtitle="Company-scoped Chart of Accounts, Trial Balance, controlled journal posting and period locks.">
      <Notice error={action.error || accounts.error || trial.error || periods.error} message={action.message} />
      <div className="wf-form-row">
        <PrimaryButton disabled={action.busy} onClick={seed}>Set up default Chart of Accounts</PrimaryButton>
        <Button onClick={() => { accounts.reload(); trial.reload(); periods.reload(); }}>Refresh ledger</Button>
      </div>
      {accountRows.length ? (
        <Table rows={accountRows} rowKey={(r) => r.code} columns={[
          { label: "Code", key: "code" }, { label: "Account", key: "name" },
          { label: "Type", key: "accountType" }, { label: "Normal balance", key: "normalBalance" },
        ]} />
      ) : <Empty title="Chart of Accounts not configured">Set up the default accounts before posting finance transactions.</Empty>}
      {trial.data ? (
        <div className="wf-stats">
          <Stat label="Trial Balance debit" value={fmtInr(trial.data.totalDebit)} />
          <Stat label="Trial Balance credit" value={fmtInr(trial.data.totalCredit)} />
          <Stat label="Balance check" value={trial.data.balanced ? "Balanced" : "Needs review"} />
        </div>
      ) : null}
      {canPost ? (
        <>
          <h3 className="wf-subhead">Manual journal entry</h3>
          <div className="wf-form-row">
            <Field label="Voucher number"><input value={voucher} onChange={(e) => setVoucher(e.target.value)} placeholder="JV-2026-001" /></Field>
            <Field label="Entry date"><input type="date" value={entryDate} onChange={(e) => setEntryDate(e.target.value)} /></Field>
            <Field label="Amount (INR)"><input type="number" min="0.01" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} /></Field>
          </div>
          <div className="wf-form-row">
            <Field label="Debit account"><select value={debitCode} onChange={(e) => setDebitCode(e.target.value)}><option value="">Select account</option>{accountRows.map((a) => <option key={a.code} value={a.code}>{a.code} — {a.name}</option>)}</select></Field>
            <Field label="Credit account"><select value={creditCode} onChange={(e) => setCreditCode(e.target.value)}><option value="">Select account</option>{accountRows.map((a) => <option key={a.code} value={a.code}>{a.code} — {a.name}</option>)}</select></Field>
            <Field label="Narration"><input value={narration} onChange={(e) => setNarration(e.target.value)} /></Field>
          </div>
          <PrimaryButton disabled={action.busy || !amount || !debitCode || !creditCode || debitCode === creditCode} onClick={postJournal}>Post balanced journal</PrimaryButton>
        </>
      ) : null}
      <h3 className="wf-subhead">Ledger-based financial statements</h3>
      <div className="wf-form-row">
        <Field label="From"><input type="date" value={reportStart} onChange={(e) => setReportStart(e.target.value)} /></Field>
        <Field label="To"><input type="date" value={reportEnd} onChange={(e) => setReportEnd(e.target.value)} /></Field>
        <PrimaryButton disabled={action.busy} onClick={loadLedgerStatements}>Build GL statements</PrimaryButton>
      </div>
      {statements ? <div className="wf-stats">
        <Stat label="Revenue" value={fmtInr(statements.pl.income)} />
        <Stat label="Expenses" value={fmtInr(statements.pl.expenses)} />
        <Stat label="Net profit" value={fmtInr(statements.pl.netProfit)} />
        <Stat label="Assets" value={fmtInr(statements.bs.assets)} />
        <Stat label="Liabilities + equity" value={fmtInr(statements.bs.liabilitiesAndEquity)} />
        <Stat label="Net cash movement" value={fmtInr(statements.cf.netCashMovement)} />
      </div> : null}
      {isChief ? (
        <>
          <h3 className="wf-subhead">Accounting period close</h3>
          <div className="wf-form-row">
            <Field label="Period start"><input type="date" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} /></Field>
            <Field label="Period end"><input type="date" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} /></Field>
            <Field label="Closing note"><input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Month-end review completed" /></Field>
          </div>
          <PrimaryButton disabled={action.busy} onClick={closeMonth}>Close accounting period</PrimaryButton>
        </>
      ) : null}
      {periods.data?.periods?.length ? <Table rows={periods.data.periods} rowKey={(r) => r.id} columns={[
        { label: "Period", render: (r) => `${fmtDate(r.start)} – ${fmtDate(r.end)}` },
        { label: "Status", key: "status" }, { label: "Closed at", render: (r) => fmtDate(r.closedAt) },
      ]} /> : null}
    </Section>
  );
}

function StatementTable({ groups, footer }) {
  const rows = [];
  groups.forEach(([title, group]) => {
    rows.push({ kind: "head", label: title });
    group.rows.forEach((r) => rows.push({ kind: "row", label: `${r.code ? `${r.code} · ` : ""}${r.name}`, amount: r.amount }));
    rows.push({ kind: "total", label: `Total ${title.toLowerCase()}`, amount: group.total });
  });
  footer.forEach(([label, amount]) => rows.push({ kind: "total", label, amount }));
  return (
    <div className="workspace-table-wrap">
      <table className="workspace-table">
        <tbody>
          {rows.map((r, i) => (
            <tr key={`${r.label}-${i}`} className={r.kind === "head" ? "wf-row-head" : r.kind === "total" ? "wf-row-total" : undefined}>
              <td>{r.label}</td>
              <td className="wf-right">{r.kind === "head" ? "" : fmtNum(r.amount)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SchedulesPanel() {
  const schedules = useLoader(getSchedules);
  const action = useAction();
  const [form, setForm] = useState({ name: "", reportType: "DOCUMENT_SUMMARY", frequency: "MONTHLY", firstRun: addDaysIso(0) });
  const [lastRun, setLastRun] = useState(null);
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  async function create() {
    const made = await action.run(
      () => createSchedule({ name: form.name.trim(), report_type: form.reportType, frequency: form.frequency, first_run: form.firstRun }),
      "Schedule created."
    );
    if (made) {
      setForm((f) => ({ ...f, name: "" }));
      schedules.reload();
    }
  }

  async function run(row) {
    const result = await action.run(() => scheduleAction(row.id, "run"), "Report run completed.");
    if (result) {
      setLastRun(result);
      schedules.reload();
    }
  }

  return (
    <Section title="Reporting schedules" subtitle={schedules.data?.note || "Plan recurring reports and run them when due."}>
      <Notice error={action.error || schedules.error} message={action.message} />
      <div className="wf-form-row">
        <Field label="Name"><input value={form.name} maxLength={255} onChange={set("name")} placeholder="e.g. Monthly management pack" /></Field>
        <Field label="Report">
          <select value={form.reportType} onChange={set("reportType")}>
            <option value="DOCUMENT_SUMMARY">Document summary (XLSX)</option>
            <option value="FINANCIAL_STATEMENTS">Financial statements (previous period)</option>
          </select>
        </Field>
        <Field label="Frequency">
          <select value={form.frequency} onChange={set("frequency")}>
            <option value="WEEKLY">Weekly</option>
            <option value="MONTHLY">Monthly</option>
            <option value="QUARTERLY">Quarterly</option>
          </select>
        </Field>
        <Field label="First run"><input type="date" value={form.firstRun} onChange={set("firstRun")} /></Field>
        <PrimaryButton disabled={action.busy || !form.name.trim()} onClick={create}>Add schedule</PrimaryButton>
      </div>
      <Table
        rows={schedules.data?.schedules}
        rowKey={(r) => r.id}
        empty="No schedules yet."
        columns={[
          { label: "Schedule", render: (r) => (<><strong>{r.name}</strong><small>{r.reportType === "DOCUMENT_SUMMARY" ? "Document summary" : "Financial statements"} · {r.frequency.toLowerCase()}</small></>) },
          { label: "Next run", render: (r) => (<>{fmtDate(r.nextRun)}{r.due ? <small className="wf-warn">Due now</small> : null}</>) },
          { label: "Last run", render: (r) => fmtDate(r.lastRunAt) },
          { label: "Status", render: (r) => <Pill value={r.status} /> },
          {
            label: "Actions",
            render: (r) => (
              <div className="workspace-actions">
                <Button tone="approve" busy={action.busy} onClick={() => run(r)}>Run now</Button>
                {r.status === "ACTIVE"
                  ? <Button onClick={async () => { if (await action.run(() => scheduleAction(r.id, "pause"))) schedules.reload(); }}>Pause</Button>
                  : <Button onClick={async () => { if (await action.run(() => scheduleAction(r.id, "resume"))) schedules.reload(); }}>Resume</Button>}
                <Button tone="reject" onClick={async () => { if (await action.run(() => deleteSchedule(r.id), "Schedule deleted.")) schedules.reload(); }}>Delete</Button>
              </div>
            ),
          },
        ]}
      />
      {lastRun?.statements ? (
        <p className="workspace-footnote">
          Statements built for {fmtDate(lastRun.period.start)} to {fmtDate(lastRun.period.end)}: net profit {fmtInr(lastRun.statements.profitAndLoss.netProfit)}. Use the export above for the full pack.
        </p>
      ) : null}
      {lastRun?.reportId ? <p className="workspace-footnote">A new report was added to the report history below.</p> : null}
    </Section>
  );
}
