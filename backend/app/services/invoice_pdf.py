"""Server-side PDF renderer for approved customer sales invoices."""
from xml.sax.saxutils import escape


def render_sales_invoice_pdf(invoice) -> bytes:
    # Imported lazily so the API can still start before optional PDF extras are installed.
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=18*mm, bottomMargin=18*mm)
    styles = getSampleStyleSheet()
    story = [Paragraph("AZENTMART — TAX INVOICE", styles["Title"]), Spacer(1, 8*mm)]
    story.append(Paragraph(f"<b>Invoice:</b> {escape(invoice.invoice_number or 'DRAFT')} &nbsp;&nbsp; <b>Status:</b> {escape(invoice.status)}", styles["Normal"]))
    story.append(Paragraph(f"<b>Customer:</b> {escape(invoice.customer_name)}<br/><b>Email:</b> {escape(invoice.customer_email)}<br/><b>GSTIN:</b> {escape(invoice.customer_gstin or '—')}", styles["Normal"]))
    story.append(Paragraph(f"<b>Invoice date:</b> {invoice.invoice_date.isoformat()} &nbsp;&nbsp; <b>Due date:</b> {invoice.due_date.isoformat()}", styles["Normal"]))
    story.append(Spacer(1, 8*mm))
    rows = [["Description", "Qty", "Unit price (INR)", "Line total (INR)"]]
    for line in invoice.lines:
        rows.append([Paragraph(escape(line.description), styles["BodyText"]), str(line.quantity), _money(line.unit_price), _money(line.line_total)])
    rows.extend([
        ["", "", "Subtotal", _money(invoice.subtotal)],
        ["", "", f"GST ({invoice.gst_rate}%)", _money(invoice.gst_amount)],
        ["", "", "Grand total", _money(invoice.total_amount)],
        ["", "", "Amount paid", _money(invoice.amount_paid)],
        ["", "", "Balance due", _money(invoice.total_amount - invoice.amount_paid)],
    ])
    table = Table(rows, colWidths=[86*mm, 18*mm, 40*mm, 40*mm], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#10243A")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#CBD5E1")),
        ("ALIGN", (1,1), (-1,-1), "RIGHT"),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("BACKGROUND", (0,-3), (-1,-1), colors.HexColor("#EFF6FF")),
        ("FONTNAME", (2,-3), (-1,-1), "Helvetica-Bold"),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 7), ("RIGHTPADDING", (0,0), (-1,-1), 7),
        ("TOPPADDING", (0,0), (-1,-1), 7), ("BOTTOMPADDING", (0,0), (-1,-1), 7),
    ]))
    story.extend([table, Spacer(1, 8*mm), Paragraph("Thank you for your business.", styles["Normal"])])
    doc.build(story)
    return buffer.getvalue()


def _money(value):
    return f"{value:,.2f}"
