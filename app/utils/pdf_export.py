import os
from io import BytesIO

from flask import current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

TEAL = colors.HexColor("#115569")
GREEN = colors.HexColor("#469971")


def invoice_pdf(invoice):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm, title=invoice.invoice_no)
    ss = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=ss["Normal"], fontSize=9, textColor=colors.grey)
    story = []

    logo = os.path.join(current_app.static_folder, "img", "logo_600.png")
    if os.path.exists(logo):
        story.append(Image(logo, width=5 * cm, height=5 * cm * 0.727))
    story += [Spacer(1, 8), Paragraph(f"<b>TAX INVOICE</b> &nbsp; {invoice.invoice_no}", ss["Heading2"]),
              Paragraph(f"Date: {invoice.created_at:%d %b %Y, %I:%M %p}", ss["Normal"]),
              Paragraph(f"Customer: {invoice.customer.name if invoice.customer else 'Walk-in customer'}", ss["Normal"]),
              Paragraph(f"Payment: {invoice.payment_mode.upper()}", ss["Normal"]), Spacer(1, 12)]

    rows = [["Medicine", "Batch", "Exp", "Qty", "MRP", "Disc", "GST%", "Amount"]]
    for it in invoice.items:
        rows.append([it.medicine.display_name, it.batch.batch_no, f"{it.batch.expiry_date:%m/%y}", it.quantity,
                     f"{it.unit_price:.2f}", f"{it.discount_amount:.2f}", f"{it.gst_percent:g}", f"{it.line_total:.2f}"])
    table = Table(rows, repeatRows=1, colWidths=[5.2 * cm, 2.2 * cm, 1.5 * cm, 1 * cm, 1.8 * cm, 1.6 * cm, 1.3 * cm, 2 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f7f6")]),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, GREEN),
    ]))
    story += [table, Spacer(1, 12)]

    totals = Table([["Subtotal (MRP)", f"Rs. {invoice.subtotal:.2f}"], ["Discount", f"- Rs. {invoice.discount:.2f}"],
                    ["GST included", f"Rs. {invoice.gst_amount:.2f}"], ["TOTAL", f"Rs. {invoice.total:.2f}"]],
                   colWidths=[4 * cm, 3.5 * cm], hAlign="RIGHT")
    totals.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                                ("LINEABOVE", (0, -1), (-1, -1), 0.8, TEAL)]))
    story += [totals, Spacer(1, 20),
              Paragraph("Prices are inclusive of GST. Medicines once sold are returnable only if unopened and "
                        "within the store's return window.", small),
              Paragraph(current_app.config["STORE_NAME"], small)]
    doc.build(story)
    buf.seek(0)
    return buf
