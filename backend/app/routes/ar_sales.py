"""AR sales invoice approvals and Stripe Checkout collection endpoints."""
from __future__ import annotations

import json
import uuid
import smtplib
from email.message import EmailMessage
from fastapi import Response
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated

import requests
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.permissions import require_roles
from app.models.sales_invoice import SalesInvoice, SalesInvoiceEvent, SalesInvoiceLine, StripePayment, StripeRefund
from app.models.ledger import JournalLine
from app.models.user import User
from app.services.notifications import notify_user, notify_roles
from app.services.posting import post_ar_collection, post_ar_invoice_recognition
from app.services.ar_billing import calculate_invoice_totals, money, stripe_signature_valid
from app.services.invoice_pdf import render_sales_invoice_pdf

router = APIRouter(tags=["AR Sales Invoices"])


def _audit_invoice(db: Session, invoice: SalesInvoice, actor_id: int | None, action: str,
                   from_status: str | None = None, to_status: str | None = None,
                   reason: str | None = None, details: dict | None = None):
    db.add(SalesInvoiceEvent(tenant_id=invoice.tenant_id, invoice_id=invoice.id, actor_id=actor_id,
        action=action, from_status=from_status, to_status=to_status, reason=reason, details=details or {}))
class InvoiceLineIn(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit_price: Decimal = Field(ge=0, max_digits=16, decimal_places=2)


class SalesInvoiceIn(BaseModel):
    customer_name: str = Field(min_length=1, max_length=255)
    customer_email: EmailStr
    customer_gstin: str | None = Field(default=None, max_length=20)
    invoice_date: date
    due_date: date
    gst_rate: Decimal = Field(default=Decimal("18"), ge=0, le=28)
    lines: list[InvoiceLineIn] = Field(min_length=1, max_length=100)


def _invoice_or_404(db: Session, user: User, invoice_id: int) -> SalesInvoice:
    invoice = db.execute(select(SalesInvoice).options(joinedload(SalesInvoice.lines)).where(
        SalesInvoice.id == invoice_id, SalesInvoice.tenant_id == user.tenant_id
    )).unique().scalar_one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail="Sales invoice not found")
    if invoice.owner_id != user.id and user.role_name not in {"Finance Manager", "Administrator", "Chief Accountant"}:
        raise HTTPException(status_code=404, detail="Sales invoice not found")
    return invoice




def _apply_refund_accounting(db: Session, invoice: SalesInvoice, refund: StripeRefund, actor_id: int | None):
    if refund.status != "SUCCEEDED":
        return
    if Decimal(str(invoice.amount_paid)) < Decimal(str(refund.amount)):
        raise HTTPException(status_code=409, detail="Refund amount exceeds the remaining collected balance.")
    invoice.amount_paid = money(Decimal(str(invoice.amount_paid)) - Decimal(str(refund.amount)))
    invoice.status = "PARTIALLY_PAID" if invoice.amount_paid > 0 else "APPROVED"
    voucher = post_ar_collection(db, invoice.owner_id, invoice.id, date.today(), Decimal(str(refund.amount)),
                                 f"Refund to {invoice.customer_name}", reference=f"REFUND-{refund.id}")
    rows = db.scalars(select(JournalLine).where(
        JournalLine.owner_id == invoice.owner_id, JournalLine.voucher_no == voucher
    )).all()
    for row in rows:
        row.debit, row.credit = row.credit, row.debit
        row.source_type = "AR_REFUND"
        row.narration = f"Stripe refund {refund.stripe_refund_id}: {refund.reason or 'Customer refund'}"[:500]
    _audit_invoice(db, invoice, actor_id, "STRIPE_REFUND_SUCCEEDED", "PAID", invoice.status,
                   details={"refundId": refund.stripe_refund_id, "amount": str(refund.amount)})


def _view(invoice: SalesInvoice) -> dict:
    return {
        "id": invoice.id, "invoiceNumber": invoice.invoice_number, "customerName": invoice.customer_name,
        "customerEmail": invoice.customer_email, "customerGstin": invoice.customer_gstin,
        "invoiceDate": invoice.invoice_date.isoformat(), "dueDate": invoice.due_date.isoformat(),
        "subtotal": str(invoice.subtotal), "gstRate": str(invoice.gst_rate), "gstAmount": str(invoice.gst_amount),
        "totalAmount": str(invoice.total_amount), "amountPaid": str(invoice.amount_paid), "status": invoice.status,
        "rejectionReason": invoice.rejection_reason, "emailStatus": invoice.email_status,
        "emailedAt": invoice.emailed_at.isoformat() if invoice.emailed_at else None,
        "lines": [{"description": x.description, "quantity": str(x.quantity), "unitPrice": str(x.unit_price), "lineTotal": str(x.line_total)} for x in invoice.lines],
    }


@router.post("/agents/accounts-receivable/sales-invoices", status_code=201)
def create_sales_invoice(body: SalesInvoiceIn, db: Session = Depends(get_db), user: User = Depends(require_roles("Finance User"))):
    if body.due_date < body.invoice_date:
        raise HTTPException(status_code=422, detail="Due date cannot be before invoice date")
    try:
        line_totals, subtotal, gst_amount, grand_total = calculate_invoice_totals(body.lines, body.gst_rate)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    line_rows = [SalesInvoiceLine(description=line.description.strip(), quantity=line.quantity, unit_price=line.unit_price, line_total=line_total) for line, line_total in zip(body.lines, line_totals)]
    invoice = SalesInvoice(
        tenant_id=user.tenant_id, owner_id=user.id, customer_name=body.customer_name.strip(),
        customer_email=str(body.customer_email), customer_gstin=body.customer_gstin,
        invoice_date=body.invoice_date, due_date=body.due_date, subtotal=subtotal,
        gst_rate=body.gst_rate, gst_amount=gst_amount, total_amount=grand_total,
        status="DRAFT", lines=line_rows,
    )
    db.add(invoice); db.flush()
    _audit_invoice(db, invoice, user.id, "DRAFT_CREATED", None, "DRAFT")
    db.commit(); db.refresh(invoice)
    return _view(invoice)


@router.get("/agents/accounts-receivable/sales-invoices")
def list_sales_invoices(db: Session = Depends(get_db), user: User = Depends(require_roles("Finance User", "Finance Manager", "Chief Accountant", "Administrator"))):
    stmt = select(SalesInvoice).options(joinedload(SalesInvoice.lines)).where(SalesInvoice.tenant_id == user.tenant_id).order_by(SalesInvoice.created_at.desc())
    if user.role_name == "Finance User":
        stmt = stmt.where(SalesInvoice.owner_id == user.id)
    return {"invoices": [_view(x) for x in db.scalars(stmt).unique().all()]}


@router.post("/agents/accounts-receivable/sales-invoices/{invoice_id}/submit")
def submit_sales_invoice(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("Finance User"))):
    invoice = _invoice_or_404(db, user, invoice_id)
    if invoice.owner_id != user.id or invoice.status not in {"DRAFT", "REJECTED"}:
        raise HTTPException(status_code=409, detail="Only the owning Finance User can submit a draft or rejected invoice")
    previous = invoice.status
    invoice.status = "PENDING_MANAGER_APPROVAL"; invoice.rejection_reason = None
    _audit_invoice(db, invoice, user.id, "SUBMITTED", previous, invoice.status)
    notify_roles(db, user.tenant_id, {"Finance Manager"}, "AR_MANAGER_APPROVAL", "AR invoice awaiting review", f"Sales invoice #{invoice.id} is awaiting Finance Manager approval.", "/employees/accounts-receivable")
    notify_roles(db, user.tenant_id, {"Chief Accountant"}, "AR_MONITORING", "New AR invoice submitted", f"Sales invoice #{invoice.id} was submitted for approval. This is a monitoring alert; AR approval remains with Finance Manager and Administrator.", "/employees/accounts-receivable")
    db.commit(); return {"status": invoice.status}


@router.post("/agents/accounts-receivable/sales-invoices/{invoice_id}/manager-approve")
def manager_approve_sales_invoice(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("Finance Manager"))):
    invoice = _invoice_or_404(db, user, invoice_id)
    if invoice.owner_id == user.id:
        raise HTTPException(status_code=403, detail="You cannot approve your own invoice")
    if invoice.status != "PENDING_MANAGER_APPROVAL":
        raise HTTPException(status_code=409, detail="Invoice is not awaiting Finance Manager approval")
    previous = invoice.status
    invoice.status = "PENDING_ADMIN_APPROVAL"; invoice.manager_approved_by = user.id; invoice.manager_approved_at = datetime.now(timezone.utc)
    _audit_invoice(db, invoice, user.id, "MANAGER_APPROVED", previous, invoice.status)
    notify_roles(db, user.tenant_id, {"Administrator"}, "AR_ADMIN_APPROVAL", "AR invoice awaiting final approval", f"Sales invoice #{invoice.id} passed Finance Manager review.", "/employees/accounts-receivable")
    notify_roles(db, user.tenant_id, {"Chief Accountant"}, "AR_MONITORING", "AR invoice passed first approval", f"Sales invoice #{invoice.id} passed Finance Manager review and is awaiting Administrator final approval.", "/employees/accounts-receivable")
    db.commit(); return {"status": invoice.status}


class RejectBody(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


@router.post("/agents/accounts-receivable/sales-invoices/{invoice_id}/admin-approve")
def admin_approve_sales_invoice(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("Administrator"))):
    invoice = _invoice_or_404(db, user, invoice_id)
    if invoice.owner_id == user.id:
        raise HTTPException(status_code=403, detail="You cannot approve your own invoice")
    if invoice.status != "PENDING_ADMIN_APPROVAL":
        raise HTTPException(status_code=409, detail="Invoice is not awaiting Administrator approval")
    previous = invoice.status
    invoice.status = "APPROVED"; invoice.admin_approved_by = user.id; invoice.admin_approved_at = datetime.now(timezone.utc)
    invoice.invoice_number = f"AR-{invoice.tenant_id}-{invoice.id:08d}"
    # Recognize the approved sales invoice once in the General Ledger.
    post_ar_invoice_recognition(
        db, invoice.owner_id, invoice.tenant_id, invoice.id, invoice.invoice_date,
        Decimal(str(invoice.subtotal)), Decimal(str(invoice.gst_amount)), invoice.customer_name,
    )
    _audit_invoice(db, invoice, user.id, "ADMIN_FINAL_APPROVED", previous, invoice.status, details={"invoice_number": invoice.invoice_number})
    notify_user(db, db.get(User, invoice.owner_id), "AR_INVOICE_APPROVED", "Sales invoice approved", f"Invoice {invoice.invoice_number} is approved and ready to send to the customer.", "/employees/accounts-receivable")
    db.commit(); return {"status": invoice.status, "invoiceNumber": invoice.invoice_number}


@router.post("/agents/accounts-receivable/sales-invoices/{invoice_id}/reject")
def reject_sales_invoice(invoice_id: int, body: RejectBody, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role_name not in {"Finance Manager", "Administrator"}:
        raise HTTPException(status_code=403, detail="Only Finance Manager or Administrator can reject AR invoices")
    invoice = _invoice_or_404(db, user, invoice_id)
    expected = "PENDING_MANAGER_APPROVAL" if user.role_name == "Finance Manager" else "PENDING_ADMIN_APPROVAL"
    if invoice.status != expected or invoice.owner_id == user.id:
        raise HTTPException(status_code=409, detail="Invoice is not awaiting your approval")
    previous = invoice.status
    invoice.status = "REJECTED"; invoice.rejection_reason = body.reason.strip()
    invoice.rejected_by, invoice.rejected_at = user.id, datetime.now(timezone.utc)  # NEW: E3 actor/time fields.
    _audit_invoice(db, invoice, user.id, "REJECTED", previous, invoice.status, reason=invoice.rejection_reason)
    notify_user(db, db.get(User, invoice.owner_id), "AR_INVOICE_REJECTED", "Sales invoice rejected", f"Invoice #{invoice.id} was rejected. Reason: {invoice.rejection_reason}", "/employees/accounts-receivable")
    db.commit(); return {"status": invoice.status, "reason": invoice.rejection_reason}


@router.get("/agents/accounts-receivable/sales-invoices/{invoice_id}/history")
def sales_invoice_history(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("Finance User", "Finance Manager", "Chief Accountant", "Administrator"))):
    invoice = _invoice_or_404(db, user, invoice_id)
    events = db.scalars(select(SalesInvoiceEvent).where(
        SalesInvoiceEvent.invoice_id == invoice.id, SalesInvoiceEvent.tenant_id == user.tenant_id
    ).order_by(SalesInvoiceEvent.created_at.asc(), SalesInvoiceEvent.id.asc())).all()
    return {"events": [{"action": e.action, "fromStatus": e.from_status, "toStatus": e.to_status,
        "reason": e.reason, "details": e.details, "actorId": e.actor_id, "createdAt": e.created_at.isoformat()} for e in events]}


@router.get("/agents/accounts-receivable/sales-invoices/{invoice_id}/pdf")
def download_sales_invoice_pdf(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    invoice = _invoice_or_404(db, user, invoice_id)
    if invoice.status not in {"APPROVED", "PARTIALLY_PAID", "PAID"} or not invoice.invoice_number:
        raise HTTPException(status_code=409, detail="PDF is available only after Administrator final approval")
    pdf = render_sales_invoice_pdf(invoice)
    return Response(content=pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{invoice.invoice_number}.pdf"',
        "Cache-Control": "private, no-store",
    })


@router.post("/agents/accounts-receivable/sales-invoices/{invoice_id}/send-email")
def email_sales_invoice(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("Finance User"))):
    invoice = _invoice_or_404(db, user, invoice_id)
    if invoice.owner_id != user.id or invoice.status not in {"APPROVED", "PARTIALLY_PAID", "PAID"} or not invoice.invoice_number:
        raise HTTPException(status_code=409, detail="Only the owning Finance User can email a finally approved invoice")
    if not all([settings.smtp_host, settings.smtp_from_email]):
        raise HTTPException(status_code=503, detail="Email is not configured. Set SMTP_HOST and SMTP_FROM_EMAIL.")
    message = EmailMessage()
    message["Subject"] = f"Tax invoice {invoice.invoice_number} from Azentmart"
    message["From"] = settings.smtp_from_email
    message["To"] = invoice.customer_email
    message.set_content(f"Dear {invoice.customer_name},\n\nPlease find attached invoice {invoice.invoice_number} for INR {invoice.total_amount}.\nDue date: {invoice.due_date.isoformat()}.\n\nRegards,\nAzentmart Finance")
    pdf = render_sales_invoice_pdf(invoice)
    message.add_attachment(pdf, maintype="application", subtype="pdf", filename=f"{invoice.invoice_number}.pdf")
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
        invoice.email_status = "SENT"; invoice.emailed_at = datetime.now(timezone.utc); invoice.email_error = None
        _audit_invoice(db, invoice, user.id, "CUSTOMER_EMAIL_SENT", invoice.status, invoice.status, details={"recipient": invoice.customer_email})
        db.commit()
        return {"status": "SENT", "emailedAt": invoice.emailed_at.isoformat()}
    except Exception as exc:
        invoice.email_status = "FAILED"; invoice.email_error = str(exc)[:2000]
        _audit_invoice(db, invoice, user.id, "CUSTOMER_EMAIL_FAILED", invoice.status, invoice.status, reason="SMTP delivery failed")
        db.commit()
        raise HTTPException(status_code=502, detail="Email delivery failed. You can retry after checking SMTP settings.") from exc


@router.get("/agents/accounts-receivable/stripe-status")
def stripe_gateway_status(user: User = Depends(require_roles("Finance User"))):
    """Finance User-only Stripe readiness status; never returns secret values."""
    return {
        "provider": "Stripe",
        "secretKeyConfigured": bool(settings.stripe_secret_key),
        "publishableKeyConfigured": bool(settings.stripe_publishable_key),
        "webhookSecretConfigured": bool(settings.stripe_webhook_secret),
        "currency": (settings.stripe_currency or "inr").upper(),
        "configurationSource": "backend environment",
    }


@router.post("/agents/accounts-receivable/sales-invoices/{invoice_id}/stripe-checkout")
def create_stripe_checkout(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("Finance User"))):
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe is not configured. Add STRIPE_SECRET_KEY to backend environment.")
    invoice = _invoice_or_404(db, user, invoice_id)
    if invoice.owner_id != user.id or invoice.status != "APPROVED":
        raise HTTPException(status_code=409, detail="Only the owning Finance User can collect payment for an Administrator-approved invoice")
    if invoice.amount_paid >= invoice.total_amount:
        raise HTTPException(status_code=409, detail="Invoice is already fully paid")
    remaining = money(invoice.total_amount - invoice.amount_paid)
    currency = (settings.stripe_currency or "inr").lower()
    key = f"ar-invoice-{invoice.id}-{uuid.uuid4().hex}"
    form = {
        "mode": "payment", "success_url": f"{settings.frontend_url}/employees/accounts-receivable?payment=success&session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{settings.frontend_url}/employees/accounts-receivable?payment=cancelled&invoice_id={invoice.id}",
        "customer_email": invoice.customer_email, "client_reference_id": str(invoice.id),
        "metadata[invoice_id]": str(invoice.id), "metadata[tenant_id]": str(invoice.tenant_id),
        "line_items[0][quantity]": "1", "line_items[0][price_data][currency]": currency,
        "line_items[0][price_data][unit_amount]": str(int(remaining * 100)),
        "line_items[0][price_data][product_data][name]": f"Invoice {invoice.invoice_number}",
    }
    try:
        response = requests.post("https://api.stripe.com/v1/checkout/sessions", data=form,
            auth=(settings.stripe_secret_key, ""), headers={"Idempotency-Key": key}, timeout=20)
        response.raise_for_status(); session = response.json()
    except requests.RequestException as exc:
        detail = "Stripe checkout could not be created"
        if getattr(exc, "response", None) is not None:
            try: detail = exc.response.json().get("error", {}).get("message", detail)
            except Exception: pass
        raise HTTPException(status_code=502, detail=detail) from exc
    payment = db.scalar(select(StripePayment).where(StripePayment.checkout_session_id == session["id"]))
    if payment is None:
        db.add(StripePayment(tenant_id=invoice.tenant_id, invoice_id=invoice.id, checkout_session_id=session["id"], amount=remaining, currency=currency, status="PENDING", payer_email=invoice.customer_email))  # CHANGED: preserve payer identity snapshot.
        _audit_invoice(db, invoice, user.id, "STRIPE_CHECKOUT_CREATED", invoice.status, invoice.status, details={"checkout_session_id": session["id"], "amount": str(remaining)})
        db.commit()
    return {"checkoutUrl": session.get("url"), "sessionId": session["id"], "amount": str(remaining), "currency": currency}


@router.post("/payments/stripe/webhook")
async def stripe_webhook(request: Request, stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None, db: Session = Depends(get_db)):
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Stripe webhook secret is not configured")
    payload = await request.body()
    if not stripe_signature or not stripe_signature_valid(payload, stripe_signature, settings.stripe_webhook_secret):
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature")
    try: event = json.loads(payload)
    except json.JSONDecodeError: raise HTTPException(status_code=400, detail="Invalid webhook payload")
    event_id, event_type = event.get("id"), event.get("type")
    if not event_id:
        raise HTTPException(status_code=400, detail="Missing Stripe event ID")
    already = db.scalar(select(StripePayment).where(StripePayment.stripe_event_id == event_id))
    if already:
        return {"received": True, "duplicate": True}
    supported_events = {
        "checkout.session.completed", "checkout.session.async_payment_succeeded",
        "checkout.session.async_payment_failed", "checkout.session.expired", "refund.updated",
    }
    if event_type not in supported_events:
        return {"received": True, "ignored": event_type}
    obj = event.get("data", {}).get("object", {})
    if event_type == "refund.updated":
        refund = db.scalar(select(StripeRefund).where(StripeRefund.stripe_refund_id == obj.get("id")).with_for_update())
        if refund is None:
            return {"received": True, "ignored": "refund_not_registered"}
        invoice = db.scalar(select(SalesInvoice).where(
            SalesInvoice.id == refund.invoice_id, SalesInvoice.tenant_id == refund.tenant_id
        ).with_for_update())
        if invoice is None:
            raise HTTPException(status_code=404, detail="Refund invoice no longer exists.")
        stripe_status = (obj.get("status") or "pending").upper()
        previous_status = refund.status
        refund.status = stripe_status
        if stripe_status == "SUCCEEDED" and previous_status != "SUCCEEDED":
            _apply_refund_accounting(db, invoice, refund, None)
        db.commit()
        return {"received": True, "refundId": refund.id, "status": refund.status}
    session_id = obj.get("id")
    payment = db.scalar(select(StripePayment).where(StripePayment.checkout_session_id == session_id).with_for_update())
    if payment is None:
        raise HTTPException(status_code=404, detail="Checkout session is not associated with an invoice")
    invoice = db.scalar(select(SalesInvoice).where(SalesInvoice.id == payment.invoice_id, SalesInvoice.tenant_id == payment.tenant_id).with_for_update())
    if invoice is None:
        raise HTTPException(status_code=404, detail="Associated invoice no longer exists")
    metadata = obj.get("metadata") or {}
    if str(metadata.get("invoice_id", "")) != str(invoice.id) or str(metadata.get("tenant_id", "")) != str(invoice.tenant_id):
        raise HTTPException(status_code=409, detail="Stripe metadata does not match the stored invoice")
    if event_type in {"checkout.session.expired", "checkout.session.async_payment_failed"}:
        if payment.status == "PENDING":
            payment.status = "FAILED"
            payment.stripe_event_id = event_id
            db.commit()
        return {"received": True, "invoiceId": invoice.id, "paymentStatus": payment.status}
    if event_type == "checkout.session.completed" and obj.get("payment_status") != "paid":
        return {"received": True, "ignored": "checkout_not_paid"}
    if invoice.status not in {"APPROVED", "PARTIALLY_PAID"}:
        raise HTTPException(status_code=409, detail="Invoice is not eligible for payment posting")
    if payment.status == "PAID":
        return {"received": True, "duplicate": True}
    received = Decimal(str(obj.get("amount_total", 0))) / Decimal("100")
    if received != payment.amount or obj.get("currency", "").lower() != payment.currency:
        raise HTTPException(status_code=409, detail="Stripe amount or currency does not match the stored checkout")
    payment.status = "PAID"; payment.stripe_event_id = event_id; payment.payment_intent_id = obj.get("payment_intent")
    payment.paid_at = datetime.now(timezone.utc)
    invoice.amount_paid = money(Decimal(str(invoice.amount_paid)) + received)
    previous_invoice_status = invoice.status
    invoice.status = "PAID" if invoice.amount_paid >= invoice.total_amount else "PARTIALLY_PAID"
    _audit_invoice(db, invoice, None, "STRIPE_PAYMENT_CONFIRMED", previous_invoice_status, invoice.status,
                   details={"stripe_event_id": event_id, "amount": str(received), "payment_intent_id": payment.payment_intent_id, "paid_by_customer_email": payment.payer_email, "paid_at": payment.paid_at.isoformat(), "actor": "Stripe webhook"})
    # Journal posting is part of the same DB transaction. Stripe will retry on failure.
    post_ar_collection(db, invoice.owner_id, invoice.id, date.today(), received, invoice.customer_name, reference=str(payment.id))
    notify_user(db, db.get(User, invoice.owner_id), "AR_PAYMENT_RECEIVED", "Customer payment received", f"Stripe confirmed INR {received} against invoice {invoice.invoice_number}.", "/employees/accounts-receivable")
    db.commit()
    return {"received": True, "invoiceId": invoice.id, "status": invoice.status}


class RefundRequest(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=16, decimal_places=2)
    reason: str | None = Field(default=None, max_length=255)


@router.post("/agents/accounts-receivable/sales-invoices/{invoice_id}/stripe-refunds", status_code=201)
def refund_stripe_payment(invoice_id: int, body: RefundRequest,
                          db: Session = Depends(get_db),
                          user: User = Depends(require_roles("Administrator"))):
    """Administrator-initiated Stripe refund with durable idempotency record."""
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe is not configured.")
    invoice = _invoice_or_404(db, user, invoice_id)
    if invoice.amount_paid <= 0:
        raise HTTPException(status_code=409, detail="There is no collected payment to refund.")
    amount = money(body.amount)
    if amount > Decimal(str(invoice.amount_paid)):
        raise HTTPException(status_code=422, detail="Refund amount cannot exceed the collected amount.")
    payment = db.scalar(select(StripePayment).where(
        StripePayment.invoice_id == invoice.id, StripePayment.tenant_id == user.tenant_id,
        StripePayment.status == "PAID", StripePayment.payment_intent_id.is_not(None)
    ).order_by(StripePayment.paid_at.desc()))
    if payment is None:
        raise HTTPException(status_code=409, detail="No paid Stripe payment with a payment intent was found.")
    if amount > Decimal(str(payment.amount)):
        raise HTTPException(status_code=422, detail="Refund amount cannot exceed the selected Stripe payment amount.")

    refund = StripeRefund(tenant_id=user.tenant_id, invoice_id=invoice.id, stripe_payment_id=payment.id,
        amount=amount, reason=body.reason, status="REQUESTED", requested_by=user.id)
    db.add(refund)
    db.commit()
    db.refresh(refund)

    payload = {"payment_intent": payment.payment_intent_id, "amount": str(int(amount * 100))}
    if body.reason:
        payload["metadata[reason]"] = body.reason[:255]
    try:
        response = requests.post("https://api.stripe.com/v1/refunds", data=payload,
            auth=(settings.stripe_secret_key, ""),
            headers={"Idempotency-Key": f"ar-refund-{refund.id}"}, timeout=20)
        response.raise_for_status()
        stripe_refund = response.json()
    except requests.RequestException as exc:
        refund.status = "FAILED"
        db.commit()
        raise HTTPException(status_code=502, detail="Stripe refund request failed. The failed request is recorded for audit.") from exc

    refund.stripe_refund_id = stripe_refund.get("id")
    refund.status = (stripe_refund.get("status") or "PENDING").upper()
    if stripe_refund.get("status") == "succeeded":
        refund.status = "SUCCEEDED"
        _apply_refund_accounting(db, invoice, refund, user.id)
    else:
        _audit_invoice(db, invoice, user.id, "STRIPE_REFUND_REQUESTED", invoice.status, invoice.status,
                       details={"refundId": refund.stripe_refund_id, "status": refund.status, "amount": str(amount)})
    db.commit()
    return {"refundId": refund.stripe_refund_id, "status": refund.status, "amount": str(amount)}
