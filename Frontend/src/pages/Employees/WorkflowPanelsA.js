import React, { useMemo, useState } from "react";

import useAuth from "../../hooks/useAuth";
import { getDocuments } from "../../services/documentsService";
import {
  getApExceptions, resolveApException, getPaymentReady, getPaymentBatches, createPaymentBatch,
  submitPaymentBatch, approvePaymentBatch, rejectPaymentBatch,
  markBatchPaid, cancelBatch, downloadBatch, uploadBatchPaymentProof, getBatchPaymentProof,
  getCollectionPriorities, getCashForecast, markCollected, getReminders, generateReminder,
  getSalesInvoices, createSalesInvoice, submitSalesInvoice, managerApproveSalesInvoice,
  adminApproveSalesInvoice, rejectSalesInvoice, createStripeCheckout, emailSalesInvoice, downloadSalesInvoicePdf, refundStripePayment,
  getStripeGatewayStatus,
  markReminderSent, getDisputes, createDispute, updateDispute,
  getChartOfAccounts, loadDefaultChart, suggestCoding, acceptCoding,
  getReconExceptions, resolveReconException, downloadReconStatement,
} from "../../services/workflowService";
import {
  BarChart, Button, Empty, Field, Notice, NoteInline, Pill, PrimaryButton, Section, Stat, Table,
  addDaysIso, fmtDate, fmtInr, fmtNum, isoDate, useAction, useLoader,
} from "./workflowUi";

/* ============================ Accounts Payable ============================ */

export function ApPanel() {
  const { currentUser } = useAuth();
  const canPay = currentUser?.role_name === "Finance User";
  const canApproveBatch = currentUser?.role_name === "Chief Accountant";
  const exceptions = useLoader(getApExceptions);
  const ready = useLoader(getPaymentReady);
  const batches = useLoader(getPaymentBatches);
  const action = useAction();
  const [resolving, setResolving] = useState(null);
  const [selected, setSelected] = useState({});
  const [batchName, setBatchName] = useState("");
  const [paymentDate, setPaymentDate] = useState(addDaysIso(3));

  const invoices = ready.data?.invoices || [];
  const chosen = invoices.filter((i) => selected[i.documentId]);
  const chosenTotal = chosen.reduce((sum, i) => sum + i.amount, 0);

  function refreshAll() {
    exceptions.reload();
    ready.reload();
    batches.reload();
  }

  async function resolve(row, note) {
    const done = await action.run(() => resolveApException(row.documentId, row.code, note), "Exception resolved.");
    if (done) {
      setResolving(null);
      exceptions.reload();
    }
  }

  async function reopen(row) {
    const done = await action.run(() => resolveApException(row.documentId, row.code, null, true), "Exception reopened.");
    if (done) exceptions.reload();
  }

  async function createBatch() {
    const done = await action.run(
      () => createPaymentBatch({ name: batchName.trim(), paymentDate, documentIds: chosen.map((i) => i.documentId) }),
      "Payment batch created."
    );
    if (done) {
      setSelected({});
      setBatchName("");
      refreshAll();
    }
  }

  return (
    <>
      <Section
        title="Exception queue"
        subtitle="Invoices that need attention before they can be paid. Resolve each with a short note."
      >
        <Notice error={action.error || exceptions.error} message={action.message} />
        <div className="wf-stats">
          <Stat label="Open" value={exceptions.data?.openCount ?? "—"} />
          <Stat label="Resolved" value={exceptions.data?.resolvedCount ?? "—"} />
        </div>
        <Table
          loading={exceptions.loading}
          rows={exceptions.data?.exceptions}
          rowKey={(r) => `${r.documentId}-${r.code}`}
          empty={exceptions.loading ? "Checking invoices..." : "No exceptions. Every payable invoice looks clean."}
          columns={[
            { label: "Invoice", render: (r) => (<><strong>{r.invoiceNumber || r.documentName}</strong><small>{r.vendor || "Vendor not extracted"}</small></>) },
            { label: "Issue", render: (r) => (<><strong>{r.code.replace(/_/g, " ")}</strong><small className="wf-wrap">{r.detail}</small></>) },
            { label: "Severity", render: (r) => <Pill value={r.severity} /> },
            { label: "Amount", align: "right", render: (r) => (r.amount === null ? "—" : fmtNum(r.amount)) },
            { label: "Status", render: (r) => (<><Pill value={r.status} />{r.resolutionNote ? <small className="wf-wrap">{r.resolutionNote}</small> : null}</>) },
            {
              label: "Action",
              render: (r) =>
                r.status === "OPEN" ? (
                  resolving === `${r.documentId}-${r.code}` ? (
                    <NoteInline
                      placeholder="How was it resolved?"
                      confirmLabel="Resolve"
                      busy={action.busy}
                      onConfirm={(note) => resolve(r, note)}
                      onCancel={() => setResolving(null)}
                    />
                  ) : (
                    <Button onClick={() => setResolving(`${r.documentId}-${r.code}`)}>Resolve</Button>
                  )
                ) : (
                  <Button busy={action.busy} onClick={() => reopen(r)}>Reopen</Button>
                ),
            },
          ]}
        />
      </Section>

      <Section
        title="Payment-ready invoices"
        subtitle="Approved, valid, non-duplicate invoices not yet in a batch. Select invoices to build a payment batch."
      >
        {invoices.length === 0 ? (
          <Empty title="Nothing ready to pay">Approve valid invoices first. They will appear here.</Empty>
        ) : (
          <>
            <Table
              rows={invoices}
              rowKey={(r) => r.documentId}
              columns={[
                {
                  label: "Pay",
                  render: (r) => (
                    <input
                      type="checkbox"
                      aria-label={`Select ${r.invoiceNumber || r.documentName}`}
                      checked={Boolean(selected[r.documentId])}
                      onChange={(e) => setSelected((s) => ({ ...s, [r.documentId]: e.target.checked }))}
                    />
                  ),
                },
                { label: "Vendor", render: (r) => (<><strong>{r.vendor || "—"}</strong><small>{r.invoiceNumber || r.documentName}</small></>) },
                { label: "Due", render: (r) => fmtDate(r.dueDate) },
                { label: "GL", render: (r) => r.accountCode || "—" },
                { label: "Amount", align: "right", render: (r) => fmtNum(r.amount) },
              ]}
            />
            <div className="wf-form-row">
              <Field label="Batch name">
                <input value={batchName} maxLength={255} onChange={(e) => setBatchName(e.target.value)} placeholder="e.g. Week 45 supplier run" />
              </Field>
              <Field label="Payment date">
                <input type="date" value={paymentDate} min={isoDate()} onChange={(e) => setPaymentDate(e.target.value)} />
              </Field>
              <PrimaryButton disabled={!canPay || action.busy || chosen.length === 0 || !batchName.trim() || !paymentDate} onClick={createBatch}>
                Create batch ({chosen.length} · {fmtInr(chosenTotal)})
              </PrimaryButton>
            </div>
          </>
        )}
      </Section>

      <Section title="Payment batches" subtitle="Finance User submits batches. Chief Accountant authorizes them. Finance User then records payment posting.">
        <Notice error={batches.error || action.error} message={action.message} />
        <Table
          rows={batches.data?.batches}
          rowKey={(r) => r.id}
          empty="No payment batches yet."
          columns={[
            {
              label: "Batch",
              render: (r) => (
                <>
                  <strong>{r.name}</strong>
                  <small>Pay on {fmtDate(r.paymentDate)}</small>
                  {r.approvalNote ? <small>{r.approvalNote}</small> : null}
                  {r.rejectionReason ? <small className="wf-wrap">Reason: {r.rejectionReason}</small> : null}
                </>
              ),
            },
            { label: "Invoices", align: "right", render: (r) => r.itemCount },
            { label: "Total", align: "right", render: (r) => fmtInr(r.totalAmount) },
            { label: "Status", render: (r) => <Pill value={r.status} /> },
            {
              label: "Actions",
              render: (r) => (
                <div className="workspace-actions">
                  <Button onClick={() => action.run(() => downloadBatch(r))}>Export XLSX</Button>
                  {r.paymentProofFilename ? <Button onClick={async () => { const result = await action.run(() => getBatchPaymentProof(r.id)); if (result?.url) window.open(result.url, "_blank", "noopener,noreferrer"); }}>View payment proof</Button> : null}

                  {r.status === "DRAFT" && canPay ? (
                    <Button
                      tone="approve"
                      busy={action.busy}
                      onClick={async () => {
                        if (await action.run(() => submitPaymentBatch(r.id), "Batch submitted to Chief Accountant.")) refreshAll();
                      }}
                    >
                      Submit for approval
                    </Button>
                  ) : null}

                  {r.status === "PENDING_CA_APPROVAL" && canApproveBatch ? (
                    <>
                      <Button
                        tone="approve"
                        busy={action.busy}
                        onClick={async () => {
                          if (await action.run(() => approvePaymentBatch(r.id), "Payment batch approved.")) refreshAll();
                        }}
                      >
                        Approve
                      </Button>
                      <Button
                        tone="reject"
                        busy={action.busy}
                        onClick={async () => {
                          const reason = window.prompt("Enter the reason for rejecting this payment batch:");
                          if (!reason || !reason.trim()) return;
                          if (await action.run(() => rejectPaymentBatch(r.id, reason.trim()), "Payment batch rejected.")) refreshAll();
                        }}
                      >
                        Reject
                      </Button>
                    </>
                  ) : null}

                  {r.status === "APPROVED" && canPay ? (
                    <Button
                      tone="approve"
                      busy={action.busy}
                      onClick={async () => {
                        const picker = document.createElement("input");
                        picker.type = "file"; picker.accept = ".pdf,.png,.jpg,.jpeg";
                        picker.onchange = async () => {
                          const proof = picker.files?.[0]; if (!proof) return;
                          if (proof.size > 5 * 1024 * 1024) { window.alert("Payment proof must be 5 MB or smaller."); return; }
                          const uploaded = await action.run(() => uploadBatchPaymentProof(r.id, proof), "Payment proof uploaded securely.");
                          if (!uploaded) return;
                          const transferReference = window.prompt("Enter bank transfer UTR / transaction reference:");
                          if (!transferReference || transferReference.trim().length < 4) return;
                          const bankName = window.prompt("Enter bank name (optional):") || "";
                          const transferDate = window.prompt("Enter transfer date (YYYY-MM-DD):", new Date().toISOString().slice(0, 10));
                          if (!transferDate || !/^\d{4}-\d{2}-\d{2}$/.test(transferDate)) return;
                          if (!window.confirm("Confirm that the supplier bank transfer is completed and the UTR is correct?")) return;
                          if (await action.run(() => markBatchPaid(r.id, { transferReference: transferReference.trim(), bankName, transferDate, proofReference: proof.name }), "Manual bank transfer recorded and journal posted.")) refreshAll();
                        };
                        picker.click();
                      }}
                    >
                      Mark paid
                    </Button>
                  ) : null}

                  {(r.status === "DRAFT" || r.status === "REJECTED") && canPay ? (
                    <Button
                      tone="reject"
                      busy={action.busy}
                      onClick={async () => {
                        if (!window.confirm("Cancel this batch and release its invoices?")) return;
                        if (await action.run(() => cancelBatch(r.id), "Batch cancelled. Invoices are available again.")) refreshAll();
                      }}
                    >
                      Cancel
                    </Button>
                  ) : null}
                </div>
              ),
            },
          ]}
        />
        {canApproveBatch ? (
          <p className="workspace-footnote">Review submitted batches. Approval is required before payment can be recorded.</p>
        ) : canPay ? (
          <p className="workspace-footnote">Submit each draft batch for Chief Accountant approval. Only approved batches can be marked paid.</p>
        ) : (
          <p className="workspace-footnote">Payment batch actions are available to Finance Users and Chief Accountants according to their approval stage.</p>
        )}
      </Section>
    </>
  );
}

/* ========================== Accounts Receivable =========================== */

export function ArPanel() {
  const { currentUser } = useAuth();
  const priorities = useLoader(getCollectionPriorities);
  const salesInvoices = useLoader(getSalesInvoices);
  const reminders = useLoader(getReminders);
  const disputes = useLoader(getDisputes);
  const [delay, setDelay] = useState(0);
  const forecast = useLoader(() => getCashForecast(delay));
  const action = useAction();
  const [openReminder, setOpenReminder] = useState(null);
  const [disputeFor, setDisputeFor] = useState(null);
  const [disputeReason, setDisputeReason] = useState("");
  const [closing, setClosing] = useState(null);
  const [invoiceDraft, setInvoiceDraft] = useState({ customerName: "", customerEmail: "", description: "", quantity: "1", unitPrice: "", gstRate: "18", dueDate: addDaysIso(30) });

  async function draft(row, useAi) {
    const made = await action.run(() => generateReminder(row.documentId, useAi), "Reminder drafted. Review it below, then copy and send it yourself.");
    if (made) {
      setOpenReminder(made.id);
      reminders.reload();
    }
  }

  async function openDispute(row) {
    const made = await action.run(
      () => createDispute({ documentId: row.documentId, reason: disputeReason.trim() }),
      "Dispute case opened."
    );
    if (made) {
      setDisputeFor(null);
      setDisputeReason("");
      disputes.reload();
      priorities.reload();
    }
  }

  async function copyBody(reminder) {
    try {
      await navigator.clipboard.writeText(`Subject: ${reminder.subject}\n\n${reminder.body}`);
      action.setMessage("Reminder copied to the clipboard.");
    } catch {
      action.setError("Could not copy. Select the text and copy it manually.");
    }
  }

  const weeks = forecast.data?.weeks || [];

  async function saveInvoiceDraft(event) {
    event.preventDefault();
    const result = await action.run(() => createSalesInvoice({
      customer_name: invoiceDraft.customerName.trim(), customer_email: invoiceDraft.customerEmail.trim(),
      invoice_date: new Date().toISOString().slice(0, 10), due_date: invoiceDraft.dueDate,
      gst_rate: Number(invoiceDraft.gstRate),
      lines: [{ description: invoiceDraft.description.trim(), quantity: Number(invoiceDraft.quantity), unit_price: Number(invoiceDraft.unitPrice) }],
    }), "Customer invoice draft created.");
    if (result) {
      setInvoiceDraft({ customerName: "", customerEmail: "", description: "", quantity: "1", unitPrice: "", gstRate: "18", dueDate: addDaysIso(30) });
      salesInvoices.reload();
    }
  }

  async function approveSalesInvoice(row, stage) {
    const run = stage === "manager" ? managerApproveSalesInvoice : adminApproveSalesInvoice;
    if (await action.run(() => run(row.id), stage === "manager" ? "Sent to Administrator for final approval." : "Sales invoice finally approved and numbered.")) salesInvoices.reload();
  }

  async function rejectSalesInvoiceRow(row) {
    const reason = window.prompt("Enter the reason for rejecting this sales invoice:");
    if (!reason || reason.trim().length < 3) return;
    if (await action.run(() => rejectSalesInvoice(row.id, reason.trim()), "Sales invoice rejected with reason.")) salesInvoices.reload();
  }

  async function startStripePayment(row) {
    const result = await action.run(() => createStripeCheckout(row.id), "Stripe checkout created.");
    if (result?.checkoutUrl) window.location.assign(result.checkoutUrl);
  }

  async function refundCustomer(row) {
    const raw = window.prompt(`Refund amount (maximum ${row.amountPaid} INR):`);
    if (!raw) return;
    const value = Number(raw);
    if (!Number.isFinite(value) || value <= 0) return;
    const reason = window.prompt("Refund reason:");
    if (!reason || reason.trim().length < 3) return;
    if (await action.run(() => refundStripePayment(row.id, value.toFixed(2), reason.trim()), "Stripe refund requested.")) salesInvoices.reload();
  }

  return (
    <>
      {currentUser?.role_name === "Finance User" ? <StripeGatewaySetupPanel /> : null}
      {currentUser?.role_name === "Finance User" ? (
        <Section title="Create customer sales invoice" subtitle="Create a draft. Finance Manager reviews first; Administrator gives final approval before Stripe payment is enabled.">
          <Notice error={action.error || salesInvoices.error} message={action.message} />
          <form className="wf-form-row" onSubmit={saveInvoiceDraft}>
            <Field label="Customer name"><input required maxLength={255} value={invoiceDraft.customerName} onChange={(e) => setInvoiceDraft((v) => ({ ...v, customerName: e.target.value }))} /></Field>
            <Field label="Customer email"><input required type="email" value={invoiceDraft.customerEmail} onChange={(e) => setInvoiceDraft((v) => ({ ...v, customerEmail: e.target.value }))} /></Field>
            <Field label="Product / service"><input required maxLength={500} value={invoiceDraft.description} onChange={(e) => setInvoiceDraft((v) => ({ ...v, description: e.target.value }))} /></Field>
            <Field label="Quantity"><input required type="number" min="0.001" step="0.001" value={invoiceDraft.quantity} onChange={(e) => setInvoiceDraft((v) => ({ ...v, quantity: e.target.value }))} /></Field>
            <Field label="Unit price"><input required type="number" min="0.01" step="0.01" value={invoiceDraft.unitPrice} onChange={(e) => setInvoiceDraft((v) => ({ ...v, unitPrice: e.target.value }))} /></Field>
            <Field label="GST %"><select value={invoiceDraft.gstRate} onChange={(e) => setInvoiceDraft((v) => ({ ...v, gstRate: e.target.value }))}><option value="0">0%</option><option value="5">5%</option><option value="12">12%</option><option value="18">18%</option><option value="28">28%</option></select></Field>
            <Field label="Due date"><input required type="date" value={invoiceDraft.dueDate} onChange={(e) => setInvoiceDraft((v) => ({ ...v, dueDate: e.target.value }))} /></Field>
            <PrimaryButton type="submit" disabled={action.busy}>Save draft</PrimaryButton>
          </form>
        </Section>
      ) : null}
      <Section title="Sales invoice approvals and Stripe collections" subtitle="Finance User → Finance Manager → Administrator. Stripe checkout is available only after final approval." actions={<a className="workspace-action" href="https://services.gst.gov.in/services/searchtp" target="_blank" rel="noopener noreferrer">GST Check ↗</a>}>
        <Notice error={action.error || salesInvoices.error} message={action.message} />
        <Table loading={salesInvoices.loading} rows={salesInvoices.data?.invoices || []} rowKey={(r) => r.id} empty="No customer sales invoices created yet." columns={[
          { label: "Invoice", render: (r) => <><strong>{r.invoiceNumber || `Draft #${r.id}`}</strong><small>{r.customerName} · {r.customerEmail}</small></> },
          { label: "Total", align: "right", render: (r) => fmtInr(Number(r.totalAmount)) },
          { label: "Paid", align: "right", render: (r) => fmtInr(Number(r.amountPaid)) },
          { label: "Due", render: (r) => fmtDate(r.dueDate) },
          { label: "Status", render: (r) => <><Pill value={r.status} />{r.rejectionReason ? <small className="wf-wrap">{r.rejectionReason}</small> : null}<small>Email: {r.emailStatus || "NOT_SENT"}</small></> },
          { label: "Actions", render: (r) => <div className="workspace-actions">
            {currentUser?.role_name === "Finance User" && ["DRAFT", "REJECTED"].includes(r.status) ? <Button busy={action.busy} onClick={async () => { if (await action.run(() => submitSalesInvoice(r.id), "Submitted to Finance Manager.")) salesInvoices.reload(); }}>Submit</Button> : null}
            {currentUser?.role_name === "Finance Manager" && r.status === "PENDING_MANAGER_APPROVAL" ? <><Button tone="approve" busy={action.busy} onClick={() => approveSalesInvoice(r, "manager")}>Approve</Button><Button tone="reject" busy={action.busy} onClick={() => rejectSalesInvoiceRow(r)}>Reject</Button></> : null}
            {currentUser?.role_name === "Administrator" && r.status === "PENDING_ADMIN_APPROVAL" ? <><Button tone="approve" busy={action.busy} onClick={() => approveSalesInvoice(r, "admin")}>Final approve</Button><Button tone="reject" busy={action.busy} onClick={() => rejectSalesInvoiceRow(r)}>Reject</Button></> : null}
            {currentUser?.role_name === "Finance User" && ["APPROVED", "PARTIALLY_PAID"].includes(r.status) ? <><Button busy={action.busy} onClick={async () => { if (await action.run(() => downloadSalesInvoicePdf(r.id, r.invoiceNumber), "Invoice PDF downloaded.")) {} }}>PDF</Button><Button busy={action.busy} onClick={async () => { if (await action.run(() => emailSalesInvoice(r.id), "Invoice emailed to customer.")) salesInvoices.reload(); }}>Email</Button><Button tone="approve" busy={action.busy} onClick={() => startStripePayment(r)}>Pay via Stripe</Button></> : null}
            {currentUser?.role_name === "Administrator" && Number(r.amountPaid) > 0 ? <Button tone="reject" busy={action.busy} onClick={() => refundCustomer(r)}>Refund</Button> : null}
          </div> },
        ]} />
      </Section>
      <Section
        title="Collection priorities"
        subtitle="Ranked by days overdue and balance size. Scores are calculated, not AI-estimated."
      >
        <Notice error={action.error || priorities.error} message={action.message} />
        <div className="wf-stats">
          <Stat label="Open balance" value={fmtInr(priorities.data?.openBalance)} />
          <Stat label="Overdue" value={fmtInr(priorities.data?.overdueBalance)} />
        </div>
        <Table
          loading={priorities.loading}
          rows={priorities.data?.priorities}
          rowKey={(r) => r.documentId}
          empty={priorities.loading ? "Ranking receivables..." : "No open receivables with an amount. Upload receivable invoices first."}
          columns={[
            { label: "#", render: (r) => r.rank },
            { label: "Customer", render: (r) => (<><strong>{r.customer}</strong><small>{r.invoiceNumber || r.documentName}</small></>) },
            { label: "Amount", align: "right", render: (r) => fmtNum(r.amount) },
            { label: "Due", render: (r) => (<>{fmtDate(r.dueDate)}{r.daysOverdue ? <small>{r.daysOverdue} days overdue</small> : null}</>) },
            { label: "Stage", render: (r) => <Pill value={r.stage} /> },
            { label: "Score", align: "right", render: (r) => (<strong title={r.reason}>{r.priorityScore}</strong>) },
            {
              label: "Actions",
              render: (r) =>
                disputeFor === r.documentId ? (
                  <div className="wf-note-inline">
                    <input value={disputeReason} maxLength={2000} autoFocus placeholder="What is the customer disputing?" onChange={(e) => setDisputeReason(e.target.value)} />
                    <Button tone="approve" busy={action.busy} disabled={disputeReason.trim().length < 3} onClick={() => openDispute(r)}>Open case</Button>
                    <Button onClick={() => setDisputeFor(null)}>Cancel</Button>
                  </div>
                ) : (
                  <div className="workspace-actions">
                    <Button busy={action.busy} onClick={() => draft(r, false)}>Draft reminder</Button>
                    <Button busy={action.busy} onClick={() => draft(r, true)} title="Gemini rewrites the wording only. Facts and amounts are kept.">Draft with AI</Button>
                    <Button onClick={() => { setDisputeFor(r.documentId); setDisputeReason(""); }}>{r.hasOpenDispute ? "Dispute open" : "Dispute"}</Button>
                    <Button tone="approve" busy={action.busy} onClick={async () => { if (await action.run(() => markCollected(r.documentId), "Marked as collected.")) { priorities.reload(); forecast.reload(); } }}>Collected</Button>
                  </div>
                ),
            },
          ]}
        />
      </Section>

      <Section title="Reminder drafts" subtitle="Drafts only. No email is sent from here. Copy the text, send it from your own mailbox, then mark it as sent.">
        <Table
          rows={reminders.data?.reminders}
          rowKey={(r) => r.id}
          empty="No reminders drafted yet."
          columns={[
            { label: "Customer", render: (r) => (<><strong>{r.customer || "—"}</strong><small>{r.documentName}</small></>) },
            { label: "Stage", render: (r) => <Pill value={r.stage} /> },
            { label: "Subject", render: (r) => (<>{r.subject}{r.aiGenerated ? <small>AI-worded, review before sending</small> : null}</>) },
            { label: "Status", render: (r) => <Pill value={r.status} /> },
            {
              label: "Actions",
              render: (r) => (
                <div className="workspace-actions">
                  <Button onClick={() => setOpenReminder(openReminder === r.id ? null : r.id)}>{openReminder === r.id ? "Hide" : "View"}</Button>
                  <Button onClick={() => copyBody(r)}>Copy</Button>
                  {r.status === "DRAFT" ? (
                    <Button tone="approve" busy={action.busy} onClick={async () => { if (await action.run(() => markReminderSent(r.id), "Marked as sent.")) reminders.reload(); }}>Mark sent</Button>
                  ) : null}
                </div>
              ),
            },
          ]}
        />
        {(reminders.data?.reminders || []).filter((r) => r.id === openReminder).map((r) => (
          <pre className="wf-letter" key={r.id}>{`Subject: ${r.subject}\n\n${r.body}`}</pre>
        ))}
      </Section>

      <Section title="Dispute cases" subtitle="Track customer disputes from open to resolved.">
        <Notice error={disputes.error} />
        <Table
          rows={disputes.data?.disputes}
          rowKey={(r) => r.id}
          empty="No disputes. Use the Dispute button on a receivable to open one."
          columns={[
            { label: "Customer", render: (r) => (<><strong>{r.customer}</strong><small>{r.amount !== null ? fmtInr(r.amount) : "Amount not set"}</small></>) },
            { label: "Reason", render: (r) => (<><span className="wf-wrap">{r.reason}</span>{r.resolutionNote ? <small className="wf-wrap">Resolution: {r.resolutionNote}</small> : null}</>) },
            { label: "Status", render: (r) => <Pill value={r.status} /> },
            {
              label: "Actions",
              render: (r) =>
                closing === r.id ? (
                  <NoteInline
                    placeholder="How was it resolved?"
                    confirmLabel="Close case"
                    busy={action.busy}
                    onCancel={() => setClosing(null)}
                    onConfirm={async (note) => { if (await action.run(() => updateDispute(r.id, "RESOLVED", note), "Dispute resolved.")) { setClosing(null); disputes.reload(); priorities.reload(); } }}
                  />
                ) : (
                  <div className="workspace-actions">
                    {r.status === "OPEN" ? <Button onClick={async () => { if (await action.run(() => updateDispute(r.id, "IN_REVIEW"), "Moved to review.")) disputes.reload(); }}>Start review</Button> : null}
                    {r.status !== "RESOLVED" ? <Button tone="approve" onClick={() => setClosing(r.id)}>Resolve</Button> : <Button onClick={async () => { if (await action.run(() => updateDispute(r.id, "OPEN"), "Case reopened.")) disputes.reload(); }}>Reopen</Button>}
                  </div>
                ),
            },
          ]}
        />
      </Section>

      <Section
        title="Cash forecast inputs"
        subtitle="Expected inflows by week from due dates of unpaid receivables. Use the delay to see slower-paying customers."
        actions={
          <Field label="Customers pay (days late)">
            <input type="number" min="0" max="365" value={delay} onChange={(e) => setDelay(Math.max(0, Math.min(365, Number(e.target.value) || 0)))} />
          </Field>
        }
      >
        <Notice error={forecast.error} />
        {weeks.length > 0 ? (
          <>
            <BarChart items={weeks.map((w) => ({ label: `W${w.week}`, value: w.expectedInflow }))} format={fmtInr} />
            <div className="wf-stats">
              <Stat label="Overdue (timing unknown)" value={fmtInr(forecast.data.overdueTimingUnknown)} />
              <Stat label="Beyond 12 weeks" value={fmtInr(forecast.data.beyondHorizon)} />
              <Stat label="No due date" value={fmtInr(forecast.data.noDueDate)} />
            </div>
            <p className="workspace-footnote">{forecast.data.note}</p>
            <div style={{ marginTop: 8 }}>
              <Button busy={forecast.loading} onClick={forecast.reload}>Recalculate</Button>
            </div>
          </>
        ) : null}
      </Section>
    </>
  );
}

// NEW: Configuration visibility is restricted to Finance User. Secret values never leave the backend.
function StripeGatewaySetupPanel() {
  const gateway = useLoader(getStripeGatewayStatus);
  const data = gateway.data;
  return (
    <Section title="Payment gateway setup" subtitle="Finance User-only Stripe configuration status. API keys remain in the backend environment and are never displayed here.">
      <Notice error={gateway.error} />
      {data ? (
        <div className="wf-stats">
          <Stat label="PROVIDER" value={data.provider} />
          <Stat label="SECRET KEY" value={data.secretKeyConfigured ? "Configured" : "Missing"} />
          <Stat label="PUBLISHABLE KEY" value={data.publishableKeyConfigured ? "Configured" : "Missing"} />
          <Stat label="WEBHOOK SECRET" value={data.webhookSecretConfigured ? "Configured" : "Missing"} />
          <Stat label="CURRENCY" value={data.currency} />
        </div>
      ) : gateway.loading ? <p className="workspace-footnote">Checking Stripe configuration…</p> : null}
      <p className="workspace-footnote">Configuration source: backend environment. Add or rotate credentials on the server; this page intentionally does not expose secret values.</p>
    </Section>
  );
}

/* ========================== Invoice Processing ============================ */

function ConfidenceCell({ doc }) {
  if (doc.extractionConfidence === null || doc.extractionConfidence === undefined) {
    return <small>Not scored</small>;
  }
  const pct = Math.round(doc.extractionConfidence * 100);
  const weak = Object.entries(doc.fieldConfidence || {}).filter(([, v]) => v < 0.5).map(([k]) => k.replace(/_/g, " "));
  return (
    <div title={weak.length ? `Weak fields: ${weak.join(", ")}` : "All key fields found"}>
      <div className="wf-meter"><div className={`wf-meter-fill${doc.lowConfidence ? " low" : ""}`} style={{ width: `${pct}%` }} /></div>
      <strong>{pct}%</strong>
      {doc.lowConfidence ? <small className="wf-warn">Below 75%: please review</small> : null}
      {weak.length ? <small className="wf-wrap">Check: {weak.slice(0, 3).join(", ")}</small> : null}
    </div>
  );
}

export function InvoicePanel() {
  const docs = useLoader(async () => {
    const list = await getDocuments();
    const items = Array.isArray(list) ? list : list?.documents || [];
    return items.filter((d) => ["Invoice", "Accounts Payable"].includes(d.category));
  });
  const chart = useLoader(getChartOfAccounts);
  const action = useAction();
  const [picked, setPicked] = useState({});

  const accounts = useMemo(
    () => (chart.data?.accounts || []).filter((a) => ["EXPENSE", "ASSET"].includes(String(a.type).toUpperCase())),
    [chart.data]
  );

  async function suggest(doc, useAi) {
    const result = await action.run(() => suggestCoding(doc.id, useAi), "Suggestion saved. Accept it or choose another account.");
    if (result) {
      setPicked((p) => ({ ...p, [doc.id]: result.suggestion.code }));
      docs.reload();
    }
  }

  async function accept(doc) {
    const code = picked[doc.id] || doc.suggestedAccountCode;
    if (!code) return;
    if (await action.run(() => acceptCoding(doc.id, code), "GL account saved.")) docs.reload();
  }

  return (
    <Section
      title="Extraction confidence and GL coding"
      subtitle="Each invoice gets a confidence score from field checks (totals add up, dates in order, fields present). Coding suggestions only use accounts from your chart."
      actions={
        accounts.length === 0 && !chart.loading ? (
          <Button tone="approve" busy={action.busy} onClick={async () => { if (await action.run(() => loadDefaultChart(), "Standard chart of accounts loaded.")) chart.reload(); }}>
            Load standard chart of accounts
          </Button>
        ) : null
      }
    >
      <Notice error={action.error || docs.error || chart.error} message={action.message} />
      {accounts.length === 0 && !chart.loading ? (
        <p className="workspace-footnote">You have no chart of accounts yet. Load the standard chart (or import your ledger under Financial Reporting) to get coding suggestions.</p>
      ) : null}
      <Table
        loading={docs.loading}
        rows={docs.data}
        rowKey={(r) => r.id}
        empty={docs.loading ? "Loading invoices..." : "No invoices yet. Upload invoices above."}
        columns={[
          { label: "Invoice", render: (r) => (<><strong>{r.invoiceNumber || r.name}</strong><small>{r.vendorName || "Vendor not extracted"}</small></>) },
          { label: "Total", align: "right", render: (r) => (r.totalAmount ? fmtNum(r.totalAmount) : "—") },
          { label: "Confidence", render: (r) => <ConfidenceCell doc={r} /> },
          {
            label: "GL account",
            render: (r) => (
              <div>
                {r.codingStatus && r.codingStatus !== "NONE" ? <Pill value={r.codingStatus} /> : <small>No suggestion</small>}
                {r.suggestedAccountCode ? (
                  <small className="wf-wrap">
                    Suggested: {r.suggestedAccountCode} {r.suggestedAccountName} ({Math.round((r.codingConfidence || 0) * 100)}%, {r.codingSource === "AI" ? "AI" : "keyword rule"})
                  </small>
                ) : null}
                {r.accountCode ? <small>Coded to {r.accountCode}</small> : null}
              </div>
            ),
          },
          {
            label: "Actions",
            render: (r) => (
              <div className="workspace-actions">
                <Button busy={action.busy} disabled={accounts.length === 0} onClick={() => suggest(r, false)}>Suggest</Button>
                <Button busy={action.busy} disabled={accounts.length === 0} onClick={() => suggest(r, true)} title="Gemini chooses, but only from your chart.">Suggest with AI</Button>
                <select
                  aria-label="GL account"
                  className="wf-select"
                  value={picked[r.id] ?? r.accountCode ?? r.suggestedAccountCode ?? ""}
                  onChange={(e) => setPicked((p) => ({ ...p, [r.id]: e.target.value }))}
                >
                  <option value="">Choose account</option>
                  {accounts.map((a) => (<option key={a.code} value={a.code}>{a.code} · {a.name}</option>))}
                </select>
                <Button tone="approve" busy={action.busy} disabled={!(picked[r.id] || r.suggestedAccountCode)} onClick={() => accept(r)}>Save</Button>
              </div>
            ),
          },
        ]}
      />
    </Section>
  );
}

/* ============================== Reconciliation ============================ */

export function ReconPanel() {
  const docs = useLoader(async () => {
    const list = await getDocuments();
    const items = Array.isArray(list) ? list : list?.documents || [];
    return items.filter((d) => d.category === "Reconciliation" && /\.(xlsx|xlsm)$/i.test(d.name));
  });
  const [docId, setDocId] = useState("");
  const [data, setData] = useState(null);
  const [resolving, setResolving] = useState(null);
  const action = useAction();

  async function load(id = docId) {
    if (!id) return;
    const result = await action.run(() => getReconExceptions(id));
    if (result) setData(result);
    else setData(null);
  }

  async function resolve(row, status, note) {
    const result = await action.run(() => resolveReconException(docId, row.itemKey, status, note), status === "OPEN" ? "Item reopened." : "Item updated.");
    if (result) {
      setData((d) => ({ ...d, ...result }));
      setResolving(null);
    }
  }

  const totals = data?.totals;
  return (
    <Section
      title="Reconciliation exceptions and statement"
      subtitle="Every unmatched cashbook or bank item becomes a case you can resolve or write off. The statement summarises the run."
    >
      <Notice error={action.error || docs.error} message={action.message} />
      <div className="wf-form-row">
        <Field label="Reconciled workbook">
          <select value={docId} onChange={(e) => { setDocId(e.target.value); setData(null); }}>
            <option value="">Choose a workbook</option>
            {(docs.data || []).map((d) => (<option key={d.id} value={d.id}>{d.name}</option>))}
          </select>
        </Field>
        <PrimaryButton disabled={!docId || action.busy} onClick={() => load()}>Load exceptions</PrimaryButton>
        {data ? <Button onClick={() => action.run(() => downloadReconStatement(docId, data.documentName))}>Download statement (XLSX)</Button> : null}
      </div>
      {(docs.data || []).length === 0 && !docs.loading ? <p className="workspace-footnote">Upload a reconciliation workbook and run the reconciliation first.</p> : null}
      {totals ? (
        <div className="wf-stats">
          <Stat label="Matched pairs" value={totals.matchedCount} note={fmtNum(totals.matchedTotal)} />
          <Stat label="Open: not on bank" value={totals.openCashbookCount} note={fmtNum(totals.openCashbookTotal)} />
          <Stat label="Open: not in cashbook" value={totals.openBankCount} note={fmtNum(totals.openBankTotal)} />
          <Stat label="Resolved" value={totals.resolvedCount} />
          <Stat label="Written off" value={totals.writtenOffCount} note={fmtNum(totals.writtenOffTotal)} />
        </div>
      ) : null}
      {data ? (
        <Table
          rows={data.exceptions}
          rowKey={(r) => r.itemKey}
          empty="No exceptions. Everything matched."
          columns={[
            { label: "Side", render: (r) => (r.side === "CASHBOOK" ? "Cashbook" : "Bank") },
            { label: "Item", render: (r) => (<><strong>{r.description}</strong><small>Row {r.row} · {fmtDate(r.date)}</small></>) },
            { label: "Amount", align: "right", render: (r) => fmtNum(r.amount) },
            { label: "Why", render: (r) => <span className="wf-wrap">{r.reasonText}</span> },
            { label: "Status", render: (r) => (<><Pill value={r.status} />{r.note ? <small className="wf-wrap">{r.note}</small> : null}</>) },
            {
              label: "Action",
              render: (r) =>
                r.status !== "OPEN" ? (
                  <Button busy={action.busy} onClick={() => resolve(r, "OPEN")}>Reopen</Button>
                ) : resolving && resolving.key === r.itemKey ? (
                  <NoteInline
                    placeholder={resolving.status === "WRITTEN_OFF" ? "Why is it written off?" : "How was it resolved?"}
                    confirmLabel={resolving.status === "WRITTEN_OFF" ? "Write off" : "Resolve"}
                    busy={action.busy}
                    onConfirm={(note) => resolve(r, resolving.status, note)}
                    onCancel={() => setResolving(null)}
                  />
                ) : (
                  <div className="workspace-actions">
                    <Button tone="approve" onClick={() => setResolving({ key: r.itemKey, status: "RESOLVED" })}>Resolve</Button>
                    <Button tone="reject" onClick={() => setResolving({ key: r.itemKey, status: "WRITTEN_OFF" })}>Write off</Button>
                  </div>
                ),
            },
          ]}
        />
      ) : null}
    </Section>
  );
}
