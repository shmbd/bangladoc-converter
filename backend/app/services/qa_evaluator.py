from __future__ import annotations

from pathlib import Path

import cv2
import fitz
import numpy as np

from app.models import PageOCRResult, PageQASummary, QAReport
from app.services.bangla_text_utils import analyze_bangla_metrics


def _compute_visual_similarity(
    src_page: fitz.Page,
    conv_page: fitz.Page,
    diff_save_path: Path | None = None,
) -> float:
    """Render both pages at identical resolution, compute visual layout similarity %, and optionally save diff map."""
    target_w = 520
    s_scale = target_w / max(src_page.rect.width, 1.0)
    c_scale = target_w / max(conv_page.rect.width, 1.0)

    s_pix = src_page.get_pixmap(matrix=fitz.Matrix(s_scale, s_scale), alpha=False)
    c_pix = conv_page.get_pixmap(matrix=fitz.Matrix(c_scale, c_scale), alpha=False)

    s_arr = np.frombuffer(s_pix.samples, dtype=np.uint8).reshape(s_pix.height, s_pix.width, 3)
    c_arr = np.frombuffer(c_pix.samples, dtype=np.uint8).reshape(c_pix.height, c_pix.width, 3)

    if c_arr.shape[:2] != s_arr.shape[:2]:
        c_arr = cv2.resize(c_arr, (s_arr.shape[1], s_arr.shape[0]), interpolation=cv2.INTER_AREA)

    s_gray = cv2.cvtColor(s_arr, cv2.COLOR_RGB2GRAY)
    c_gray = cv2.cvtColor(c_arr, cv2.COLOR_RGB2GRAY)

    # Blur slightly so sub-pixel font smoothing differences don't penalize faithful layout
    s_blur = cv2.GaussianBlur(s_gray, (7, 7), 1.5)
    c_blur = cv2.GaussianBlur(c_gray, (7, 7), 1.5)

    abs_diff = cv2.absdiff(s_blur, c_blur)
    mae = float(np.mean(abs_diff)) / 255.0
    similarity = max(0.0, min(100.0, (1.0 - mae) * 100.0))

    if diff_save_path is not None:
        diff_save_path.parent.mkdir(parents=True, exist_ok=True)
        heat = cv2.applyColorMap(cv2. convertScaleAbs(abs_diff, alpha=2.2), cv2.COLORMAP_JET)
        blended = cv2.addWeighted(cv2.cvtColor(c_arr, cv2.COLOR_RGB2BGR), 0.72, heat, 0.28, 0)
        cv2.imwrite(str(diff_save_path), blended)

    return round(similarity, 2)


def evaluate_conversion_quality(
    source_pdf_path: Path,
    ocr_pages: list[PageOCRResult],
    searchable_pdf_path: Path | None,
    layout_pdf_path: Path | None,
    editable_pdf_path: Path | None,
    job_dir: Path,
) -> QAReport:
    """Run comprehensive QA checks across OCR accuracy, Unicode integrity, selectable text, and visual similarity."""
    src_doc = fitz.open(str(source_pdf_path))
    s_doc = fitz.open(str(searchable_pdf_path)) if searchable_pdf_path and searchable_pdf_path.exists() else None
    l_doc = fitz.open(str(layout_pdf_path)) if layout_pdf_path and layout_pdf_path.exists() else None
    e_doc = fitz.open(str(editable_pdf_path)) if editable_pdf_path and editable_pdf_path.exists() else None

    try:
        all_text_chunks: list[str] = []
        total_words = 0
        low_conf_words = 0
        headings_cnt = 0
        paragraphs_cnt = 0
        tables_cnt = 0
        images_cnt = 0
        confidences: list[float] = []

        per_page_summaries: list[PageQASummary] = []
        searchable_sims: list[float] = []
        layout_sims: list[float] = []
        editable_sims: list[float] = []
        flagged_pages: list[int] = []
        warnings: list[str] = []

        for idx, p_res in enumerate(ocr_pages):
            src_page = src_doc[p_res.page_number - 1]
            page_txt_parts: list[str] = []

            tables_cnt += len(p_res.tables)
            images_cnt += len(p_res.figures)

            for blk in p_res.blocks:
                if blk.role == "heading":
                    headings_cnt += 1
                elif blk.role == "paragraph":
                    paragraphs_cnt += 1
                for ln in blk.lines:
                    page_txt_parts.append(ln.text)
                    if ln.words:
                        for w in ln.words:
                            total_words += 1
                            confidences.append(w.confidence)
                            if w.confidence < 70.0:
                                low_conf_words += 1
                    else:
                        toks = [t for t in ln.text.split() if t]
                        total_words += len(toks)
                        confidences.append(ln.confidence)

            for tbl in p_res.tables:
                for c in tbl.cells:
                    if c.text.strip():
                        page_txt_parts.append(c.text)

            page_joined = "\n".join(page_txt_parts)
            all_text_chunks.append(page_joined)
            p_metrics = analyze_bangla_metrics(page_joined)

            s_sim = 100.0
            if s_doc and idx < s_doc.page_count:
                s_sim = _compute_visual_similarity(src_page, s_doc[idx])
            searchable_sims.append(s_sim)

            diff_file = job_dir / "qa_diffs" / f"diff_p{p_res.page_number}.png"
            l_sim = s_sim
            if l_doc and idx < l_doc.page_count:
                l_sim = _compute_visual_similarity(src_page, l_doc[idx], diff_save_path=diff_file)
            layout_sims.append(l_sim)

            e_sim = l_sim
            if e_doc and idx < e_doc.page_count:
                e_sim = _compute_visual_similarity(
                    src_page,
                    e_doc[idx],
                    diff_save_path=diff_file if l_doc is None else None,
                )
            editable_sims.append(e_sim)

            p_res.layout_similarity_score = l_sim if l_doc else s_sim
            sig_diff = (l_sim < 82.0) if l_doc else (e_sim < 75.0)
            if sig_diff:
                flagged_pages.append(p_res.page_number)

            per_page_summaries.append(
                PageQASummary(
                    page_number=p_res.page_number,
                    output_page_index=p_res.output_page_index,
                    mean_confidence=p_res.mean_confidence,
                    low_confidence_words=p_res.low_confidence_word_count,
                    layout_similarity_pct=s_sim if s_doc else l_sim,
                    editable_similarity_pct=e_sim,
                    significant_diff_flagged=sig_diff,
                    bangla_chars=int(p_metrics["bangla_char_count"]),
                    english_chars=int(p_metrics["english_char_count"]),
                    juktakkhor_count=int(p_metrics["juktakkhor_count"]),
                )
            )

        # Verify actual PDF selectable Unicode extraction from generated PDF
        pdf_to_verify = s_doc or l_doc or e_doc
        selectable_ok = True
        unicode_ok = True
        order_ok = True
        converted_pages = len(ocr_pages)

        if pdf_to_verify is not None:
            converted_pages = pdf_to_verify.page_count
            extracted_pdf_text = "\n".join(
                pdf_to_verify[i].get_text("text") for i in range(pdf_to_verify.page_count)
            )
            pdf_metrics = analyze_bangla_metrics(extracted_pdf_text)
            unicode_ok = bool(pdf_metrics["unicode_integrity_passed"])
            order_ok = bool(pdf_metrics["character_order_valid"])
            if total_words > 0 and len(extracted_pdf_text.strip()) == 0:
                selectable_ok = False
                warnings.append("Converted PDF text layer appears empty despite recognized words.")

        doc_metrics = analyze_bangla_metrics("\n".join(all_text_chunks))
        mean_conf = round(float(np.mean(confidences)), 1) if confidences else 0.0
        page_consistent = converted_pages == len(ocr_pages)

        if low_conf_words > 0:
            warnings.append(
                f"{low_conf_words} word(s) had OCR confidence below 70%. Review highlighted regions in the Preview editor to verify or refine spelling."
            )
        if flagged_pages:
            warnings.append(
                f"Page(s) {', '.join(map(str, flagged_pages))} show noticeable visual differences in reconstructed mode; use Searchable PDF mode for 100% original visual fidelity."
            )

        return QAReport(
            overall_passed=bool(unicode_ok and selectable_ok and page_consistent),
            mean_ocr_confidence=mean_conf,
            unicode_integrity_passed=unicode_ok,
            character_order_valid=order_ok,
            selectable_text_verified=selectable_ok,
            page_count_consistent=page_consistent,
            source_selected_pages=len(ocr_pages),
            converted_page_count=converted_pages,
            total_words=total_words,
            low_confidence_words=low_conf_words,
            bangla_char_count=int(doc_metrics["bangla_char_count"]),
            english_char_count=int(doc_metrics["english_char_count"]),
            bangla_numeral_count=int(doc_metrics["bangla_numeral_count"]),
            juktakkhor_count=int(doc_metrics["juktakkhor_count"]),
            kar_fola_count=int(doc_metrics["kar_fola_count"]),
            headings_detected=headings_cnt,
            paragraphs_detected=paragraphs_cnt,
            tables_preserved=tables_cnt,
            images_preserved=images_cnt,
            searchable_layout_similarity_pct=round(float(np.mean(searchable_sims or [100.0])), 2),
            layout_preserved_similarity_pct=round(float(np.mean(layout_sims or [95.0])), 2),
            editable_layout_similarity_pct=round(float(np.mean(editable_sims or [90.0])), 2),
            flagged_pages=flagged_pages,
            per_page=per_page_summaries,
            warnings=warnings,
        )
    finally:
        src_doc.close()
        if s_doc:
            s_doc.close()
        if l_doc:
            l_doc.close()
        if e_doc:
            e_doc.close()
