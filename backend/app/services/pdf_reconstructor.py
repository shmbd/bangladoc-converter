from __future__ import annotations

from pathlib import Path

import cv2
import fitz
import numpy as np

from app.models import ConversionSettings, OCRLineItem, PageOCRResult
from app.services.harfbuzz_renderer import PageVectorAccumulator


def _distribute_line_words_for_invisible_layer(acc: PageVectorAccumulator, line: OCRLineItem):
    """Add invisible words using exact word bboxes, or proportionally across line bbox if manually edited."""
    joined_words = " ".join(w.text for w in line.words).strip()
    if line.words and joined_words == line.text.strip():
        for w in line.words:
            acc.add_invisible_word(w.text, w.bbox, font_size_hint=line.font_size_pt)
        return

    # Line was manually edited by user -> distribute tokens proportionally across line.bbox
    tokens = [t for t in line.text.split(" ") if t]
    if not tokens:
        return
    x0, y0, x1, y1 = line.bbox
    total_w = max(x1 - x0, 8.0)
    total_chars = max(sum(len(t) for t in tokens), 1)
    cursor_x = x0
    for tok in tokens:
        share = total_w * (len(tok) / total_chars)
        acc.add_invisible_word(tok, [cursor_x, y0, min(x1, cursor_x + max(share, 4.0)), y1], font_size_hint=line.font_size_pt)
        cursor_x += share


def generate_searchable_pdf(
    source_pdf_path: Path,
    ocr_pages: list[PageOCRResult],
    settings: ConversionSettings,
    output_path: Path,
) -> Path:
    """Mode A: Appearance-preserving Searchable PDF with aligned invisible NFC Unicode text layer."""
    src_doc = fitz.open(str(source_pdf_path))
    out_doc = fitz.open()

    try:
        for p_res in ocr_pages:
            p_idx = p_res.page_number - 1
            if p_res.extraction_method == "native_unicode":
                # Keep native digital page directly unless legacy
                out_doc.insert_pdf(src_doc, from_page=p_idx, to_page=p_idx)
                continue

            # Check if source page had legacy garbled text layer; if so, flatten visual look cleanly
            src_page = src_doc[p_idx]
            has_existing_raw_txt = bool((src_page.get_text("text") or "").strip())
            if has_existing_raw_txt:
                # Flatten visual appearance at 240 DPI so broken ANSI text doesn't pollute Ctrl+F / Copy
                pix = src_page.get_pixmap(dpi=240, alpha=False)
                new_page = out_doc.new_page(width=p_res.width_pt, height=p_res.height_pt)
                new_page.insert_image(new_page.rect, pixmap=pix)
            else:
                out_doc.insert_pdf(src_doc, from_page=p_idx, to_page=p_idx)
                new_page = out_doc[-1]

            acc = PageVectorAccumulator(new_page, font_key=settings.bangla_font)
            for block in p_res.blocks:
                for line in block.lines:
                    _distribute_line_words_for_invisible_layer(acc, line)

            for tbl in p_res.tables:
                for cell in tbl.cells:
                    if cell.text.strip():
                        acc.add_invisible_word(cell.text, cell.bbox)

            acc.commit()

        meta_title = settings.doc_title.strip() or (src_doc.metadata or {}).get("title") or source_pdf_path.stem
        meta_author = settings.doc_author.strip() or (src_doc.metadata or {}).get("author") or ""
        out_doc.set_metadata(
            {
                "title": meta_title,
                "author": meta_author,
                "creator": "BanglaDoc Converter — Searchable Unicode Engine",
                "producer": "BanglaDoc Converter (PyMuPDF + HarfBuzz + Tesseract 5)",
            }
        )
        out_doc.save(str(output_path), garbage=3, deflate=True)
        return output_path
    finally:
        out_doc.close()
        src_doc.close()


def generate_editable_pdf(
    ocr_pages: list[PageOCRResult],
    settings: ConversionSettings,
    job_dir: Path,
    output_path: Path,
) -> Path:
    """Mode B: Clean Reconstructed PDF with HarfBuzz vector Bangla typography, figures, and vector tables."""
    out_doc = fitz.open()

    try:
        for p_res in ocr_pages:
            page = out_doc.new_page(width=p_res.width_pt, height=p_res.height_pt)

            # 1. Place preserved figures/illustrations at exact original coordinates
            if settings.preserve_images:
                for fig in p_res.figures:
                    fig_file = job_dir / fig.image_rel_path
                    if fig_file.exists():
                        try:
                            page.insert_image(fitz.Rect(*fig.bbox), filename=str(fig_file))
                        except Exception:
                            pass

            # 2. Draw vector table grids & subtle header shading
            if settings.preserve_tables and p_res.tables:
                shape = page.new_shape()
                for tbl in p_res.tables:
                    for cell in tbl.cells:
                        crect = fitz.Rect(*cell.bbox)
                        fill_col = (0.95, 0.96, 0.98) if cell.row == 0 else None
                        shape.draw_rect(crect)
                        shape.finish(color=(0.35, 0.38, 0.44), fill=fill_col, width=0.65)
                shape.commit()

            # 3. Render HarfBuzz-shaped Bangla/English vector lines + coordinate-locked NFC Unicode text
            acc = PageVectorAccumulator(page, font_key=settings.bangla_font)
            for block in p_res.blocks:
                is_heading = block.role == "heading"
                for line in block.lines:
                    acc.add_visible_shaped_line(
                        text=line.text,
                        bbox=line.bbox,
                        fontsize=line.font_size_pt,
                        bold=line.is_bold or is_heading,
                        ink_rgb=line.ink_rgb,
                        alignment="left" if settings.preserve_layout else block.alignment,
                        fit_to_box=True,
                    )

            if settings.preserve_tables:
                for tbl in p_res.tables:
                    for cell in tbl.cells:
                        if not cell.text.strip():
                            continue
                        pad_x = 3.5
                        pad_y = 2.5
                        cb = [
                            cell.bbox[0] + pad_x,
                            cell.bbox[1] + pad_y,
                            max(cell.bbox[0] + pad_x + 8.0, cell.bbox[2] - pad_x),
                            max(cell.bbox[1] + pad_y + 6.0, cell.bbox[3] - pad_y),
                        ]
                        cell_h = cb[3] - cb[1]
                        est_fs = min(11.5, max(7.5, cell_h * 0.55))
                        acc.add_visible_shaped_line(
                            text=cell.text,
                            bbox=cb,
                            fontsize=est_fs,
                            bold=(cell.row == 0),
                            ink_rgb=[20, 24, 35],
                            alignment="left",
                            fit_to_box=True,
                        )

            acc.commit()

        out_doc.set_metadata(
            {
                "title": settings.doc_title.strip() or "BanglaDoc Editable Document",
                "author": settings.doc_author.strip(),
                "creator": "BanglaDoc Converter — Vector Bangla Reconstruction Engine",
                "producer": "BanglaDoc Converter (HarfBuzz + PyMuPDF)",
            }
        )
        out_doc.save(str(output_path), garbage=3, deflate=True)
        return output_path
    finally:
        out_doc.close()


def generate_layout_preserved_pdf(
    source_pdf_path: Path,
    ocr_pages: list[PageOCRResult],
    settings: ConversionSettings,
    job_dir: Path,
    output_path: Path,
) -> Path:
    """Mode C: Hybrid Layout-Preserved PDF — keeps original graphical canvas, surgically replaces text with crisp vector Bangla."""
    src_doc = fitz.open(str(source_pdf_path))
    out_doc = fitz.open()

    try:
        for p_res in ocr_pages:
            p_idx = p_res.page_number - 1
            if p_res.extraction_method == "native_unicode":
                out_doc.insert_pdf(src_doc, from_page=p_idx, to_page=p_idx)
                continue

            cached_png = job_dir / "page_renders" / f"source_p{p_res.page_number}.png"
            if cached_png.exists():
                bgr_canvas = cv2.imread(str(cached_png))
            else:
                pix = src_doc[p_idx].get_pixmap(dpi=220, alpha=False)
                rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
                bgr_canvas = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

            img_h, img_w = bgr_canvas.shape[:2]
            sx = img_w / max(p_res.width_pt, 1.0)
            sy = img_h / max(p_res.height_pt, 1.0)

            # Surgically inpaint/fill recognized text boxes (conf >= 50) with local sampled paper color
            for block in p_res.blocks:
                for line in block.lines:
                    if line.confidence < 50.0:
                        continue
                    x0 = max(0, int(line.bbox[0] * sx) - 2)
                    y0 = max(0, int(line.bbox[1] * sy) - 2)
                    x1 = min(img_w, int(line.bbox[2] * sx) + 2)
                    y1 = min(img_h, int(line.bbox[3] * sy) + 2)
                    r, g, b = line.bg_rgb[:3]
                    cv2.rectangle(bgr_canvas, (x0, y0), (x1, y1), (int(b), int(g), int(r)), thickness=-1)

            for tbl in p_res.tables:
                for cell in tbl.cells:
                    if not cell.text.strip() or cell.confidence < 50.0:
                        continue
                    # Shrink slightly inside cell so original table border lines stay 100% intact!
                    margin_x = max(3, int(2.5 * sx))
                    margin_y = max(3, int(2.5 * sy))
                    x0 = max(0, int(cell.bbox[0] * sx) + margin_x)
                    y0 = max(0, int(cell.bbox[1] * sy) + margin_y)
                    x1 = min(img_w, int(cell.bbox[2] * sx) - margin_x)
                    y1 = min(img_h, int(cell.bbox[3] * sy) - margin_y)
                    if x1 > x0 and y1 > y0:
                        sub = bgr_canvas[y0:y1, x0:x1]
                        med_bgr = [int(v) for v in np.percentile(sub.reshape(-1, 3), 85, axis=0)]
                        cv2.rectangle(bgr_canvas, (x0, y0), (x1, y1), tuple(med_bgr), thickness=-1)

            ok, jpg_buf = cv2.imencode(".jpg", bgr_canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            page = out_doc.new_page(width=p_res.width_pt, height=p_res.height_pt)
            if ok:
                page.insert_image(page.rect, stream=jpg_buf.tobytes())

            acc = PageVectorAccumulator(page, font_key=settings.bangla_font)
            for block in p_res.blocks:
                is_heading = block.role == "heading"
                for line in block.lines:
                    if line.confidence >= 50.0:
                        acc.add_visible_shaped_line(
                            text=line.text,
                            bbox=line.bbox,
                            fontsize=line.font_size_pt,
                            bold=line.is_bold or is_heading,
                            ink_rgb=line.ink_rgb,
                            alignment="left",
                            fit_to_box=True,
                        )
                    else:
                        # Keep original visual ink for low-confidence zone + invisible selectable text
                        _distribute_line_words_for_invisible_layer(acc, line)

            for tbl in p_res.tables:
                for cell in tbl.cells:
                    if not cell.text.strip():
                        continue
                    if cell.confidence >= 50.0:
                        cb = [
                            cell.bbox[0] + 3.5,
                            cell.bbox[1] + 2.5,
                            max(cell.bbox[0] + 10.0, cell.bbox[2] - 3.5),
                            max(cell.bbox[1] + 8.0, cell.bbox[3] - 2.5),
                        ]
                        est_fs = min(11.5, max(7.5, (cb[3] - cb[1]) * 0.55))
                        acc.add_visible_shaped_line(
                            text=cell.text,
                            bbox=cb,
                            fontsize=est_fs,
                            bold=(cell.row == 0),
                            ink_rgb=[20, 20, 20],
                            alignment="left",
                            fit_to_box=True,
                        )
                    else:
                        acc.add_invisible_word(cell.text, cell.bbox)

            acc.commit()

        out_doc.set_metadata(
            {
                "title": settings.doc_title.strip() or source_pdf_path.stem,
                "author": settings.doc_author.strip(),
                "creator": "BanglaDoc Converter — Hybrid Layout-Preserved Engine",
                "producer": "BanglaDoc Converter",
            }
        )
        out_doc.save(str(output_path), garbage=3, deflate=True)
        return output_path
    finally:
        out_doc.close()
        src_doc.close()
