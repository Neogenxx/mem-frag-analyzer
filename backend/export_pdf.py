"""
export_pdf.py — Generate academic PDF report using reportlab.
Install: pip install reportlab
"""
from __future__ import annotations
import io
from typing import Optional

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, KeepTogether
    )
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def _conclusion(data: dict) -> str:
    """Rule-based auto-generated conclusion. No AI required."""
    lines = []
    metrics = data.get("metrics", {})
    ef = metrics.get("external_frag", 0)
    strategy = data.get("strategy", "unknown")
    comp = data.get("comparison")

    if ef > 0.5:
        lines.append(
            f"The simulation produced high external fragmentation ({ef:.1%}), "
            "indicating that memory became heavily scattered. "
            "Compaction would be needed to recover usable contiguous space."
        )
    elif ef > 0.2:
        lines.append(
            f"Moderate external fragmentation ({ef:.1%}) was observed. "
            "Some free blocks exist but are not contiguous enough for large requests."
        )
    else:
        lines.append(
            f"External fragmentation remained low ({ef:.1%}), "
            "indicating efficient use of memory under this workload."
        )

    if comp:
        strats = list(comp.keys())
        best_ef = min(strats, key=lambda s: comp[s].get("external_frag", 1))
        best_fa = min(strats, key=lambda s: comp[s].get("failed_allocs", 999))
        lines.append(
            f"In the strategy comparison, {best_ef.replace('_', ' ').title()} "
            f"achieved the lowest external fragmentation "
            f"({comp[best_ef]['external_frag']:.1%}). "
            f"{best_fa.replace('_', ' ').title()} had the fewest failed allocations "
            f"({comp[best_fa]['failed_allocs']})."
        )
        lines.append(
            "Best Fit minimises leftover fragments per allocation but requires "
            "scanning all free blocks. First Fit is faster but tends to fragment "
            "the beginning of memory. Worst Fit preserves small blocks but may "
            "exhaust large free regions quickly."
        )

    return " ".join(lines)


def generate_pdf(data: dict) -> bytes:
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("reportlab not installed. Run: pip install reportlab")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle("Title2", parent=styles["Title"],
                                  fontSize=20, spaceAfter=6)
    h2_style    = ParagraphStyle("H2", parent=styles["Heading2"],
                                  fontSize=13, spaceBefore=14, spaceAfter=4)
    normal      = styles["Normal"]
    code_style  = ParagraphStyle("Code", parent=normal, fontName="Courier",
                                  fontSize=9, leading=13)

    # ── Title ──────────────────────────────────
    story.append(Paragraph("MemSim — Memory Allocation Simulation Report", title_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    story.append(Spacer(1, 8))

    # ── Simulation metadata ────────────────────
    meta_data = [
        ["Seed",         str(data.get("seed", "N/A"))],
        ["Strategy",     data.get("strategy", "N/A").replace("_", " ").title()],
        ["Total Memory", f"{data.get('total_size', '?')} bytes"],
        ["Total Ticks",  str(data.get("tick", "?"))],
    ]
    meta_table = Table(meta_data, colWidths=[4*cm, 10*cm])
    meta_table.setStyle(TableStyle([
        ("FONTNAME",  (0,0), (-1,-1), "Helvetica"),
        ("FONTNAME",  (0,0), (0,-1),  "Helvetica-Bold"),
        ("FONTSIZE",  (0,0), (-1,-1), 10),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [colors.whitesmoke, colors.white]),
        ("BOX",       (0,0), (-1,-1), 0.5, colors.grey),
        ("INNERGRID", (0,0), (-1,-1), 0.25, colors.lightgrey),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 12))

    # ── Final Metrics ──────────────────────────
    story.append(Paragraph("Final Memory Metrics", h2_style))
    m = data.get("metrics", {})
    metrics_data = [
        ["Metric", "Value"],
        ["External Fragmentation", f"{m.get('external_frag', 0):.1%}"],
        ["Internal Fragmentation", f"{m.get('internal_frag', 0)} bytes"],
        ["Total Free Space",       f"{m.get('free_space', 0)} bytes"],
        ["Largest Free Block",     f"{m.get('largest_free', 0)} bytes"],
        ["Memory Utilization",     f"{m.get('utilization', 0):.1%}"],
        ["Free Block Count",       str(m.get("num_free_blocks", 0))],
    ]
    mt = Table(metrics_data, colWidths=[8*cm, 6*cm])
    mt.setStyle(TableStyle([
        ("FONTNAME",  (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTNAME",  (0,1), (-1,-1), "Helvetica"),
        ("FONTSIZE",  (0,0), (-1,-1), 10),
        ("BACKGROUND",(0,0), (-1,0),  colors.black),
        ("TEXTCOLOR", (0,0), (-1,0),  colors.white),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.whitesmoke, colors.white]),
        ("BOX",       (0,0), (-1,-1), 0.5, colors.grey),
        ("INNERGRID", (0,0), (-1,-1), 0.25, colors.lightgrey),
        ("TOPPADDING",    (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(mt)
    story.append(Spacer(1, 12))

    # ── Final Memory Block Table ───────────────
    story.append(Paragraph("Final Memory Layout", h2_style))
    blocks = data.get("blocks", [])
    if blocks:
        block_rows = [["Start", "End", "Size", "Status", "PID", "Int. Frag"]]
        for b in blocks:
            block_rows.append([
                str(b.get("start", "")),
                str(b.get("end", "")),
                str(b.get("size", "")),
                b.get("status", "").upper(),
                b.get("pid") or "—",
                str(b.get("internal_frag", 0)),
            ])
        bt = Table(block_rows, colWidths=[2.5*cm, 2.5*cm, 2*cm, 2.5*cm, 2.5*cm, 2.5*cm])
        bt.setStyle(TableStyle([
            ("FONTNAME",  (0,0), (-1,0),  "Helvetica-Bold"),
            ("FONTSIZE",  (0,0), (-1,-1), 9),
            ("BACKGROUND",(0,0), (-1,0),  colors.black),
            ("TEXTCOLOR", (0,0), (-1,0),  colors.white),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.whitesmoke, colors.white]),
            ("BOX",       (0,0), (-1,-1), 0.5, colors.grey),
            ("INNERGRID", (0,0), (-1,-1), 0.25, colors.lightgrey),
            ("TOPPADDING",    (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ]))
        story.append(bt)
    story.append(Spacer(1, 12))

    # ── Strategy Comparison ────────────────────
    comp = data.get("comparison")
    if comp:
        story.append(Paragraph("Strategy Comparison", h2_style))
        strats = list(comp.keys())
        headers = ["Metric"] + [s.replace("_", " ").title() for s in strats]
        keys = [
            ("External Fragmentation", lambda s, c: f"{c[s].get('external_frag',0):.1%}"),
            ("Internal Fragmentation", lambda s, c: f"{c[s].get('internal_frag',0)} B"),
            ("Free Space",             lambda s, c: f"{c[s].get('free_space',0)} B"),
            ("Largest Free Block",     lambda s, c: f"{c[s].get('largest_free',0)} B"),
            ("Failed Allocations",     lambda s, c: str(c[s].get("failed_allocs", 0))),
        ]
        crows = [headers]
        for label, fn in keys:
            crows.append([label] + [fn(s, comp) for s in strats])

        col_w = [5*cm] + [3.5*cm] * len(strats)
        ct = Table(crows, colWidths=col_w)
        ct.setStyle(TableStyle([
            ("FONTNAME",  (0,0), (-1,0),  "Helvetica-Bold"),
            ("FONTNAME",  (0,1), (-1,-1), "Helvetica"),
            ("FONTSIZE",  (0,0), (-1,-1), 9),
            ("BACKGROUND",(0,0), (-1,0),  colors.black),
            ("TEXTCOLOR", (0,0), (-1,0),  colors.white),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.whitesmoke, colors.white]),
            ("BOX",       (0,0), (-1,-1), 0.5, colors.grey),
            ("INNERGRID", (0,0), (-1,-1), 0.25, colors.lightgrey),
            ("TOPPADDING",    (0,0), (-1,-1), 3),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ]))
        story.append(ct)
        story.append(Spacer(1, 12))

    # ── Conclusion ─────────────────────────────
    story.append(Paragraph("Academic Conclusion", h2_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 4))
    story.append(Paragraph(_conclusion(data), normal))

    doc.build(story)
    return buf.getvalue()