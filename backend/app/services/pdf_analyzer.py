from __future__ import annotations

from pathlib import Path

import fitz

from app.models import PageInspectionInfo, UploadInspectResponse
from app.services.bangla_text_utils import detect_legacy_ansi_encoding


class PDFValidationError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def inspect_uploaded_pdf(
    pdf_path: Path,
    upload_id: str,
    original_filename: str,
    thumbs_dir: Path,
) -> UploadInspectResponse:
    if not pdf_path.exists() or pdf_path.stat().st_size < 16:
        raise PDFValidationError("EMPTY_FILE", "The uploaded file is empty or unreadable.")

    head = pdf_path.read_bytes()[:1024]
    if b"%PDF-" not in head:
        raise PDFValidationError(
            "INVALID_FORMAT",
            "Unsupported file format. Please upload a valid PDF (.pdf) document.",
        )

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        raise PDFValidationError(
            "CORRUPTED_PDF",
            f"This PDF appears corrupted or malformed and could not be opened ({exc}).",
        ) from exc

    try:
        if doc.needs_pass:
            raise PDFValidationError(
                "ENCRYPTED_PDF",
                "This PDF is password-protected/encrypted. Please unlock the PDF before uploading.",
            )

        if doc.page_count == 0:
            raise PDFValidationError("ZERO_PAGES", "This PDF contains zero pages.")

        thumbs_dir.mkdir(parents=True, exist_ok=True)
        meta = doc.metadata or {}
        pages_info: list[PageInspectionInfo] = []

        for idx in range(doc.page_count):
            page = doc[idx]
            rect = page.rect
            raw_text = page.get_text("text") or ""
            stripped = raw_text.strip()
            char_count = len(stripped)
            images = page.get_images(full=True)
            img_count = len(images)
            fonts = [f[3] for f in page.get_fonts() if len(f) > 3 and f[3]]

            legacy_suspect = detect_legacy_ansi_encoding(stripped, fonts)

            # Check if a large raster image covers >= 50% of page area (typical scanned page)
            large_scan_img = False
            page_area = max(rect.width * rect.height, 1.0)
            for img_info in page.get_image_info(xrefs=False):
                bbox = img_info.get("bbox")
                if bbox:
                    iw = max(0.0, bbox[2] - bbox[0])
                    ih = max(0.0, bbox[3] - bbox[1])
                    if (iw * ih) / page_area >= 0.45:
                        large_scan_img = True
                        break

            if legacy_suspect:
                mode = "legacy_ansi_suspect"
                has_reliable_text = False
            elif char_count >= 40 and not large_scan_img:
                mode = "digital_text"
                has_reliable_text = True
            elif char_count >= 40 and large_scan_img:
                mode = "hybrid"
                has_reliable_text = True
            else:
                mode = "scanned_image"
                has_reliable_text = False

            # Render crisp thumbnail for preview grid (up to first 60 pages eagerly, lazy on demand beyond)
            thumb_name = f"thumb_{idx + 1}.png"
            thumb_path = thumbs_dir / thumb_name
            if not thumb_path.exists() and idx < 60:
                scale = min(1.0, 260.0 / max(rect.width, 1.0))
                pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                pix.save(str(thumb_path))

            pages_info.append(
                PageInspectionInfo(
                    page_number=idx + 1,
                    width_pt=round(float(rect.width), 2),
                    height_pt=round(float(rect.height), 2),
                    has_reliable_text=has_reliable_text,
                    has_legacy_encoding_suspect=legacy_suspect,
                    image_count=img_count,
                    char_count=char_count,
                    mode_detected=mode,
                    thumbnail_url=f"/api/uploads/{upload_id}/pages/{idx + 1}/thumbnail",
                )
            )

        return UploadInspectResponse(
            upload_id=upload_id,
            filename=original_filename,
            file_size_bytes=pdf_path.stat().st_size,
            page_count=doc.page_count,
            title=str(meta.get("title") or "").strip(),
            author=str(meta.get("author") or "").strip(),
            is_encrypted=False,
            pages=pages_info,
        )
    finally:
        doc.close()
