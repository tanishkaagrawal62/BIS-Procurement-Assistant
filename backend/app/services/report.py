from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def make_report(analysis: dict) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm)
    styles = getSampleStyleSheet()
    story = [Paragraph("BIS Assist — Standards Recommendation Report", styles["Title"]), Spacer(1, 5 * mm)]
    location = f"<br/>Location: {escape(analysis['location'])}" if analysis.get("location") else ""
    story.append(Paragraph(f"Analysis ID: {escape(analysis['id'])}<br/>Date: {escape(analysis['created_at'])}<br/>Tender: {escape(analysis['tender_name'])}{location}", styles["BodyText"]))
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("Key parameters extracted from input", styles["Heading2"]))
    requirements = analysis.get("requirements", {})
    labels = {
        "product": "Product", "quantity": "Quantity", "materials": "Materials", "dimensions": "Dimensions / values",
        "grades": "Grades / classes", "referenced_standards": "Referenced standards", "testing": "Testing",
        "safety": "Safety", "performance": "Performance", "application": "Application",
    }
    for key, label in labels.items():
        value = requirements.get(key)
        values = [value.get("value")] if key == "product" and isinstance(value, dict) else [item.get("value") for item in value or [] if isinstance(item, dict)]
        values = [item for item in values if item]
        if values:
            story.append(Paragraph(f"<b>{escape(label)}:</b> {escape(', '.join(dict.fromkeys(values)))}", styles["BodyText"]))
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("Recommendations", styles["Heading2"]))
    if not analysis["recommendations"]:
        story.append(Paragraph("No sufficiently supported recommendation was found in the loaded catalogue.", styles["BodyText"]))
    for item in analysis["recommendations"]:
        standard = item["standard"]
        story.append(Paragraph(f"{item['rank']}. {escape(standard['is_number'])} — {escape(standard['title'])}", styles["Heading3"]))
        matched_terms = ", ".join(item.get("evidence") or []) or "related product and specification keywords"
        story.append(Paragraph(f"<b>Why recommended:</b> This BIS record matched tender terms: {escape(matched_terms)}.", styles["BodyText"]))
        source_url = escape(standard["source_url"], {'"': "&quot;"})
        story.append(Paragraph(
            f"Relevance ranking indicator: {item['combined_score'] * 100:.1f}%<br/>"
            f"Verification state: {escape(standard['verification_state'])}<br/>"
            f"Status: {escape(standard['status'] or 'Unable to verify current status')}<br/>"
            f"Last checked: {escape(standard['source_checked_at'] or 'Not checked')}<br/>"
            f"Provenance: {escape(standard['provenance'])}<br/>"
            f'Official source: <link href="{source_url}" color="blue">{escape(standard["source_url"])}</link>',
            styles["BodyText"],
        ))
        story.append(Spacer(1, 3 * mm))
    document.build(story, onFirstPage=lambda canvas, doc: (canvas.saveState(), canvas.setFillColor(colors.HexColor("#687386")), canvas.setFont("Helvetica", 8), canvas.drawString(18 * mm, 10 * mm, "BIS Assist · source and verification details shown above"), canvas.restoreState()))
    return output.getvalue()
