"""Automated PDF report generation using ReportLab.

Compiles the analysis results — colourised segmentation, detected objects,
land-cover distribution chart and statistics — into a downloadable PDF, matching
the 'Report Generation' stage of the methodology.
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.piecharts import Pie
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage,
)

from .constants import CLASS_HEX, CLASSES

_BRAND = colors.HexColor("#0B3D91")
_ACCENT = colors.HexColor("#2E7D32")


def _hex(c: str):
    return colors.HexColor(c)


def _land_cover_pie(percentages: dict[str, float]) -> Drawing:
    d = Drawing(240, 150)
    pie = Pie()
    pie.x, pie.y = 20, 15
    pie.width = pie.height = 120
    data, labels, cols = [], [], []
    for c in CLASSES:
        v = percentages.get(c, 0.0)
        if v <= 0:
            continue
        data.append(v)
        labels.append(f"{c} {v:.1f}%")
        cols.append(_hex(CLASS_HEX[c]))
    if not data:
        data, labels, cols = [1], ["No data"], [colors.grey]
    pie.data = data
    pie.labels = labels
    pie.slices.strokeWidth = 0.5
    for i, col in enumerate(cols):
        pie.slices[i].fillColor = col
    d.add(pie)
    return d


def generate_report(analysis: dict, out_path: Path,
                     original_path: Path, seg_path: Path, det_path: Path) -> Path:
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "BDTitle", parent=styles["Title"], textColor=_BRAND, fontSize=22, spaceAfter=4,
    )
    sub = ParagraphStyle("BDSub", parent=styles["Normal"], textColor=colors.grey, fontSize=9)
    h2 = ParagraphStyle("BDH2", parent=styles["Heading2"], textColor=_BRAND, fontSize=13)

    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=1.6 * cm, rightMargin=1.6 * cm,
        topMargin=1.4 * cm, bottomMargin=1.4 * cm,
        title=f"Bhu-Darpan Report — {analysis.get('name', '')}",
    )
    story = []

    # Header
    story.append(Paragraph("Bhu-Darpan", title_style))
    story.append(Paragraph("AI-based Satellite Image Analysis — Analysis Report", sub))
    story.append(Spacer(1, 6))
    meta = Table([
        ["Image", analysis.get("name", "—")],
        ["Analysis ID", analysis.get("id", "—")],
        ["Generated", analysis.get("created_at", "—")],
        ["Resolution", f"{analysis.get('width', '?')} × {analysis.get('height', '?')} px"],
        ["Model confidence", f"{analysis.get('confidence', 0)} %"],
    ], colWidths=[4 * cm, 11 * cm])
    meta.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), _BRAND),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, colors.lightgrey),
    ]))
    story.append(meta)
    story.append(Spacer(1, 10))

    # Imagery row: original + segmentation
    def _img(p: Path, wcm=7.6):
        img = RLImage(str(p))
        ratio = img.imageHeight / float(img.imageWidth)
        img.drawWidth = wcm * cm
        img.drawHeight = wcm * cm * ratio
        return img

    story.append(Paragraph("Land-Cover Segmentation", h2))
    imgs = Table([[_img(original_path), _img(seg_path)],
                  ["Original", "Segmented land cover"]], colWidths=[7.8 * cm, 7.8 * cm])
    imgs.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 1), (-1, 1), 8),
        ("TEXTCOLOR", (0, 1), (-1, 1), colors.grey),
    ]))
    story.append(imgs)
    story.append(Spacer(1, 8))

    # Land cover distribution: pie + table
    pct = analysis.get("land_cover", {})
    rows = [["Class", "Coverage"]]
    for c in CLASSES:
        rows.append([c, f"{pct.get(c, 0.0):.2f} %"])
    dist_table = Table(rows, colWidths=[4 * cm, 3 * cm])
    dist_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _BRAND),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F6FB")]),
    ]))
    combo = Table([[_land_cover_pie(pct), dist_table]], colWidths=[8 * cm, 7.5 * cm])
    combo.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.append(Paragraph("Land-Cover Distribution", h2))
    story.append(combo)
    story.append(Spacer(1, 10))

    # Object detection
    story.append(Paragraph("Object Detection", h2))
    story.append(_img(det_path, wcm=10))
    story.append(Spacer(1, 4))
    counts = analysis.get("object_counts", {})
    if counts:
        crow = [["Object", "Count"]] + [[k, str(v)] for k, v in counts.items()]
    else:
        crow = [["Object", "Count"], ["—", "0"]]
    ctable = Table(crow, colWidths=[5 * cm, 3 * cm])
    ctable.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
    ]))
    story.append(ctable)
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Generated by Bhu-Darpan - AI-based Satellite Image Analysis System.",
        sub,
    ))

    doc.build(story)
    return out_path
