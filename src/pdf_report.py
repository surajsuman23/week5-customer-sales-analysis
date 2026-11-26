"""Build analysis_report.pdf with ReportLab (executive summary, tables, charts, recommendations)."""

from datetime import date
from pathlib import Path

import matplotlib
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from .insights import churn_insights, merged_insights, recommendations, rupees, sales_insights

# DejaVu Sans ships with matplotlib and supports the ₹ symbol
_FONT_DIR = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
pdfmetrics.registerFont(TTFont("DejaVu", str(_FONT_DIR / "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(_FONT_DIR / "DejaVuSans-Bold.ttf")))

_base = getSampleStyleSheet()
STYLES = {
    "title": ParagraphStyle("t", parent=_base["Title"], fontName="DejaVu-Bold", fontSize=20, spaceAfter=6),
    "subtitle": ParagraphStyle("st", parent=_base["Normal"], fontName="DejaVu", fontSize=10,
                               textColor=colors.grey, alignment=TA_CENTER, spaceAfter=14),
    "h1": ParagraphStyle("h1", parent=_base["Heading1"], fontName="DejaVu-Bold", fontSize=15,
                         textColor=colors.HexColor("#1F4E79"), spaceBefore=10, spaceAfter=6),
    "h2": ParagraphStyle("h2", parent=_base["Heading2"], fontName="DejaVu-Bold", fontSize=12, spaceAfter=4),
    "body": ParagraphStyle("b", parent=_base["BodyText"], fontName="DejaVu", fontSize=9.5, leading=13),
    "note": ParagraphStyle("n", parent=_base["BodyText"], fontName="DejaVu", fontSize=8.5, leading=11,
                           textColor=colors.HexColor("#7A4B00"), backColor=colors.HexColor("#FFF4E0"),
                           borderPadding=5, spaceBefore=4, spaceAfter=8),
    "cell": ParagraphStyle("c", fontName="DejaVu", fontSize=8, leading=10),
}


def _table(df, money_cols=(), index_name=None, col_widths=None):
    """Convert a DataFrame to a styled ReportLab table."""
    frame = df.copy()
    for col in money_cols:
        if col in frame.columns:
            frame[col] = frame[col].map(rupees)
    header = [index_name or (frame.index.name or "")] + [str(c) for c in frame.columns]
    rows = [[str(idx)] + [f"{v:,}" if isinstance(v, int) else str(v) for v in row]
            for idx, row in zip(frame.index, frame.itertuples(index=False))]
    table = Table([header] + rows, colWidths=col_widths, hAlign="LEFT", repeatRows=1)
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "DejaVu"),
        ("FONTNAME", (0, 0), (-1, 0), "DejaVu-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EEF3F8")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B0B7C3")),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table


def _bullets(lines):
    return [Paragraph(f"• {line}", STYLES["body"]) for line in lines]


def _image(path, width=16.5 * cm):
    img = Image(str(path))
    ratio = img.imageHeight / img.imageWidth
    img.drawWidth, img.drawHeight = width, width * ratio
    return img


def build_pdf(results, chart_paths, out_path):
    r = results
    k, ck = r["kpis"], r["churn_kpis"]
    story = [
        Paragraph("Customer Sales Analysis Report", STYLES["title"]),
        Paragraph(f"Week 5 · Data Science Internship · Data: {k['date_start']} to {k['date_end']} · "
                  f"Generated {date.today().isoformat()}", STYLES["subtitle"]),
        Paragraph("Executive Summary", STYLES["h1"]),
    ]

    kpi_rows = [
        ["Total revenue", rupees(k["total_revenue"]), "Customers (sales)", f"{k['unique_customers']}"],
        ["Orders / units", f"{k['total_orders']} / {k['total_units']}", "Avg order value", rupees(k["avg_order_value"])],
        ["Top-10 customer share", f"{r['top10_share']}%", "Best product", r["product"].index[0]],
        ["Retention rate (500 customers)", f"{ck['retention_rate_%']}%", "Churn rate", f"{ck['churn_rate_%']}%"],
    ]
    kpi = Table(kpi_rows, colWidths=[5.6 * cm, 3.0 * cm, 3.6 * cm, 3.2 * cm], hAlign="LEFT")
    kpi.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "DejaVu"), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (1, 0), (1, -1), "DejaVu-Bold"), ("FONTNAME", (3, 0), (3, -1), "DejaVu-Bold"),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EEF3F8")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.white), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [kpi, Spacer(1, 8)]
    story += _bullets(sales_insights(r)[:3] + churn_insights(r)[:3])
    story.append(Paragraph(
        "Data note: sales_data.csv (100 orders) and customer_churn.csv (500 customers) share no customer key. "
        "customer_data.csv links the first 100 churn profiles to CUST001-CUST100 in order so that merging can be "
        "practised. Any finding that uses the merged table is illustrative only. Churn findings use the full "
        "500-customer file and are real.", STYLES["note"]))

    story += [Paragraph("Recommendations", STYLES["h2"])] + _bullets(recommendations(r))

    # --- Customers
    story += [PageBreak(), Paragraph("1. Customer Analysis", STYLES["h1"]), _image(chart_paths[0], 15 * cm)]
    top = r["customer_value"].head(10)[["Revenue", "Units", "Region", "Product", "Cumulative_Share_%"]]
    story += [Spacer(1, 6), _table(top, money_cols=["Revenue"], index_name="Customer")]

    # --- Regions & products
    story += [PageBreak(), Paragraph("2. Regional Distribution and Products", STYLES["h1"]),
              _image(chart_paths[4], 9.5 * cm),
              _table(r["region"], money_cols=["Revenue", "Avg_Order", "Max_Order"]), Spacer(1, 8),
              _table(r["product"], money_cols=["Revenue", "Avg_Price"])]

    # --- Trends
    story += [PageBreak(), Paragraph("3. Sales Patterns and Trends", STYLES["h1"]), _image(chart_paths[1], 15 * cm),
              _table(r["monthly"].fillna("-"), money_cols=["Revenue", "Revenue_per_Day"]), Spacer(1, 6),
              Paragraph("April 2024 has only 9 days of data, so months are compared on revenue per day.", STYLES["body"]),
              Spacer(1, 6), _table(r["weekday"], money_cols=["Revenue", "Avg_Order"])]

    # --- Cross-selling proxy
    story += [PageBreak(), Paragraph("4. Region × Product Affinity (cross-selling proxy)", STYLES["h1"]),
              Paragraph("Every customer placed one order, so products bought together cannot be measured. Instead, "
                        "lift shows how much more (or less) of each product sells in a region than the overall mix.",
                        STYLES["body"]),
              _image(chart_paths[2], 15.5 * cm), _table(r["affinity"])]
    story += _bullets(sales_insights(r)[3:])

    # --- Retention
    story += [PageBreak(), Paragraph("5. Customer Retention (500 customers)", STYLES["h1"]), _image(chart_paths[3], 16.5 * cm)]
    story += _bullets(churn_insights(r))
    story += [Spacer(1, 6), _table(r["churn_contract"]), Spacer(1, 6), _table(r["churn_tenure"]),
              Spacer(1, 6), _table(r["churn_payment"])]

    # --- Merged + limitations
    story += [PageBreak(), Paragraph("6. Merged Sales + Customer Data (illustrative)", STYLES["h1"]),
              _table(r["merged_contract"], money_cols=["Revenue", "Avg_Order"])]
    story += _bullets(merged_insights(r))
    story += [Paragraph("7. Methodology", STYLES["h1"])] + _bullets([
        "Cleaning: whitespace/casing fixed with pandas string methods, dates and numbers coerced, duplicates and "
        "invalid rows removed, Total_Sales recomputed where it did not equal Quantity x Price.",
        "Date parts: year, month, day, weekday, ISO week and weekend flag extracted with the .dt accessor.",
        "Aggregations: named groupby().agg() per region, month, product and weekday; transform() for within-region "
        "shares; pct_change() for month-on-month growth; rank() for product ranks.",
        "Filtering: AND (high-value orders in North/South), OR (Laptop or bulk orders), NOT (weekend large orders "
        "excluding Headphones) and an AND/OR at-risk customer filter.",
        "Pivot tables: region x product revenue (with totals), month x product units, region x month order count/mean, "
        "tenure band x contract churn rate.",
        "Merge: left join of customer_data.csv onto orders with validate='many_to_one' and a row-count check.",
    ])
    story += [Paragraph("8. Limitations", STYLES["h1"])] + _bullets([
        "Only 100 orders over about 3 months; each customer appears once, so no repeat-purchase or basket analysis.",
        "The sales/customer link is simulated (no shared key in the source files).",
        f"In the churn file, {r['total_charges_flag_%']}% of customers have TotalCharges below half of "
        "MonthlyCharges x Tenure, so TotalCharges was not used for lifetime-value estimates.",
        "No cost data, so the report covers revenue, not profit.",
    ])

    doc = SimpleDocTemplate(str(out_path), pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            topMargin=1.6 * cm, bottomMargin=1.6 * cm, title="Customer Sales Analysis Report")

    def _footer(canvas, doc_):
        canvas.setFont("DejaVu", 7.5)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(A4[0] - 1.8 * cm, 1 * cm, f"Page {doc_.page}")
        canvas.drawString(1.8 * cm, 1 * cm, "Week 5 · Customer Sales Analysis")

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return Path(out_path)
