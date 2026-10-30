import fitz


class PdfExtractionError(ValueError):
    pass


def extract_pdf(data: bytes) -> str:
    try:
        with fitz.open(stream=data, filetype="pdf") as document:
            if document.is_encrypted:
                raise PdfExtractionError("This PDF is password-protected. Please provide an unlocked PDF.")
            pages = [page.get_text("text") for page in document]
    except PdfExtractionError:
        raise
    except Exception as exc:
        raise PdfExtractionError("The PDF could not be opened. Check that it is a valid, uncorrupted PDF.") from exc
    text = "\n".join(pages).strip()
    if len(text) < 40:
        raise PdfExtractionError("This PDF has little or no selectable text. OCR is not configured; paste the requirements manually or configure local OCR.")
    return text
