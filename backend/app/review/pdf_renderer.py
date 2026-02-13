"""
PDF Renderer: pure rendering of PDF export payload to bytes.

Input must be the output of build_pdf_export_input only. No validator, no
re-evaluation of evidence or alignment, no inference. This layer is
presentation-only. Any logic that changes meaning is a defect.
"""

import io
from typing import Dict, List, Any, Optional

from app.review.pdf_export_contract import PDF_EXPORT_SECTION_ORDER


def _require_sections(payload: dict) -> None:
    """Raise RuntimeError if any required section is missing. Do not silently continue."""
    if not isinstance(payload, dict):
        raise RuntimeError(
            "PDF renderer requires export payload from build_pdf_export_input. Got non-dict."
        )
    missing = [s for s in PDF_EXPORT_SECTION_ORDER if s not in payload]
    if missing:
        raise RuntimeError(
            f"PDF renderer requires all sections. Missing: {missing}. "
            "Payload must be the output of build_pdf_export_input."
        )


def _safe(s: Any) -> str:
    """Escape for reportlab Paragraph (avoid XML/HTML interpretation)."""
    if s is None:
        return ""
    t = str(s).strip()
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return t


def render_programme_review_pdf(export_payload: dict) -> bytes:
    """
    Render the PDF export payload (output of build_pdf_export_input) to PDF bytes.
    Pure rendering only. No conditional logic that changes meaning.
    """
    _require_sections(export_payload)

    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        PageBreak,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name="SectionTitle",
        parent=styles["Heading1"],
        fontSize=12,
        spaceAfter=6,
    )
    body_style = styles["Normal"]
    story: List[Any] = []

    # ---- Cover / Metadata ----
    cover = export_payload.get("cover") or {}
    story.append(Paragraph("Programme Review Pack", styles["Title"]))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(f"<b>Project ID:</b> {_safe(cover.get('project_id'))}", body_style))
    story.append(Paragraph(f"<b>Programme name:</b> {_safe(cover.get('programme_name'))}", body_style))
    story.append(Paragraph(f"<b>Submission stage:</b> {_safe(cover.get('submission_stage'))}", body_style))
    story.append(Paragraph(f"<b>Submission ID:</b> {_safe(cover.get('submission_id'))}", body_style))
    story.append(Paragraph(f"<b>Created at:</b> {_safe(cover.get('created_at'))}", body_style))
    story.append(Paragraph(f"<b>Previous submission ID:</b> {_safe(cover.get('previous_submission_id') or '—')}", body_style))
    story.append(Spacer(1, 0.3 * inch))

    # ---- Legal Acceptability ----
    story.append(Paragraph("Legal Acceptability", title_style))
    acc = export_payload.get("legal_acceptability") or {}
    story.append(Paragraph(f"<b>Acceptability status:</b> {_safe(acc.get('acceptability_status'))}", body_style))
    story.append(Paragraph(f"<b>Overall status:</b> {_safe(acc.get('overall_status'))}", body_style))
    story.append(Paragraph(_safe(acc.get("legal_note")), body_style))
    story.append(Spacer(1, 0.2 * inch))

    # ---- Mandatory Obligations ----
    story.append(Paragraph("Mandatory Obligations Status", title_style))
    mos = export_payload.get("mandatory_obligations_status") or {}
    story.append(Paragraph(
        f"Total mandatory: {mos.get('total_mandatory', 0)} | "
        f"Aligned: {mos.get('aligned_count', 0)} | "
        f"Not aligned: {mos.get('not_aligned_count', 0)}",
        body_style,
    ))
    not_rep = list(mos.get("not_represented") or [])
    if not_rep:
        table_data = [["Obligation", "Evidence mode", "Canonical match", "Required action"]]
        for row in not_rep:
            table_data.append([
                _safe(row.get("obligation_name")),
                _safe(row.get("evidence_mode")),
                _safe(row.get("canonical_match_string")),
                _safe(row.get("required_action")),
            ])
        t = Table(table_data, colWidths=[1.2 * inch, 1 * inch, 1.2 * inch, 2.6 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(Spacer(1, 0.1 * inch))
        story.append(t)
    story.append(Spacer(1, 0.2 * inch))

    # ---- Planner Guidance (Required Actions) ----
    story.append(Paragraph("Planner Guidance", title_style))
    pg = export_payload.get("planner_guidance") or {}
    required_before = list(pg.get("required_before_next_submission") or [])
    for i, item in enumerate(required_before, 1):
        if isinstance(item, dict):
            ra = item.get("required_action")
            story.append(Paragraph(f"{i}. {_safe(ra)}", body_style))
        else:
            story.append(Paragraph(f"{i}. {_safe(item)}", body_style))
    if not required_before:
        story.append(Paragraph("None.", body_style))
    resolved = list(pg.get("resolved_obligations") or [])
    if resolved:
        story.append(Paragraph("<b>Resolved obligations:</b>", body_style))
        for r in resolved:
            story.append(Paragraph(f"• {_safe(r.get('obligation_name') or r.get('obligation_id'))}", body_style))
    unchanged = list(pg.get("unchanged_blockers") or [])
    if unchanged:
        story.append(Paragraph("<b>Unchanged blockers:</b>", body_style))
        for u in unchanged:
            story.append(Paragraph(f"• {_safe(u.get('obligation_name'))}", body_style))
    advisory = list(pg.get("advisory_notes") or [])
    for note in advisory:
        story.append(Paragraph(_safe(note), body_style))
    story.append(Spacer(1, 0.2 * inch))

    # ---- Submission Evolution ----
    story.append(Paragraph("Submission Evolution", title_style))
    evo = export_payload.get("submission_evolution") or {}
    story.append(Paragraph(f"<b>Status change:</b> {_safe(evo.get('status_change'))}", body_style))
    became_aligned = list(evo.get("became_aligned") or [])
    if became_aligned:
        for a in became_aligned:
            story.append(Paragraph(f"Became aligned: {_safe(a.get('obligation_name'))}", body_style))
    became_unaligned = list(evo.get("became_unaligned") or [])
    if became_unaligned:
        for u in became_unaligned:
            story.append(Paragraph(f"Became unaligned: {_safe(u.get('obligation_name'))}", body_style))
    story.append(Spacer(1, 0.2 * inch))

    # ---- Diagnostics Summary ----
    story.append(Paragraph("Diagnostics Summary", title_style))
    diag = export_payload.get("diagnostics_summary") or {}
    story.append(Paragraph(_safe(diag.get("diagnostics_summary")), body_style))
    failure_table = list(diag.get("failure_table") or [])
    if failure_table:
        for row in failure_table:
            story.append(Paragraph(
                f"• {_safe(row.get('obligation_name') or row.get('original_contract_text'))}: "
                f"{_safe(row.get('required_action'))}",
                body_style,
            ))
    story.append(Spacer(1, 0.2 * inch))

    # ---- Governance ----
    story.append(Paragraph("Governance", title_style))
    gov = export_payload.get("governance") or {}
    story.append(Paragraph(f"<b>Latest acceptance decision:</b> {_safe(gov.get('latest_acceptance_decision') or '—')}", body_style))
    story.append(Paragraph(f"<b>Latest acceptance comments:</b> {_safe(gov.get('latest_acceptance_comments') or '—')}", body_style))
    story.append(Paragraph(_safe(gov.get("governance_note")), body_style))
    for h in (gov.get("acceptance_history") or []):
        story.append(Paragraph(
            f"• {_safe(h.get('decision'))} by {_safe(h.get('decided_by'))} at {_safe(h.get('decided_at'))}",
            body_style,
        ))
    story.append(Spacer(1, 0.2 * inch))

    # ---- Footer ----
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(
        "Programme Review Pack — generated from stored submission and acceptance data. "
        "Acceptability is determined under NEC Clause 31.",
        ParagraphStyle(name="Footer", parent=body_style, fontSize=8, textColor=colors.grey),
    ))

    doc.build(story)
    return buffer.getvalue()
