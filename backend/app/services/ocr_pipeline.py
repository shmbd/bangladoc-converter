from __future__ import annotations

import csv
import io
import os
import re
import subprocess
from pathlib import Path
from typing import Literal

import cv2
import fitz
import numpy as np

if os.environ.get("BANGLADOC_LOW_MEMORY") == "1":
    cv2.setNumThreads(1)

from app.config import TESSDATA_BEST_DIR, TESSDATA_FAST_DIR, TESSERACT_CMD
from app.models import (
    ConversionSettings,
    OCRBlockItem,
    OCRFigureItem,
    OCRLineItem,
    OCRTableCell,
    OCRTableItem,
    OCRWordItem,
    PageOCRResult,
)
from app.services.bangla_text_utils import (
    classify_token_language,
    detect_legacy_ansi_encoding,
    normalize_bangla_unicode,
)

LIST_PREFIX_RE = re.compile(
    r"^(?:[•▪◦\-–—*]|\(?[০-৯0-9]{1,3}[.)]|\([ক-হa-zA-Z]\)|[ক-হ]\.)\s+"
)
PAGE_NUM_RE = re.compile(r"^[\s\-–—()\[\]পৃষ্ঠাPage০-৯0-9]{1,14}$", re.IGNORECASE)


def _rect_iou_or_containment(inner: list[float], outer: list[float]) -> float:
    ix0 = max(inner[0], outer[0])
    iy0 = max(inner[1], outer[1])
    ix1 = min(inner[2], outer[2])
    iy1 = min(inner[3], outer[3])
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    inter = (ix1 - ix0) * (iy1 - iy0)
    inner_area = max((inner[2] - inner[0]) * (inner[3] - inner[1]), 1e-3)
    return inter / inner_area


def _estimate_skew_angle(gray: np.ndarray) -> float:
    """Estimate small document skew angle in degrees [-6, +6] using morphological text lines."""
    h, w = gray.shape[:2]
    scale = 900.0 / max(h, w)
    small = cv2.resize(gray, (max(1, int(w * scale)), max(1, int(h * scale)))) if scale < 1.0 else gray
    blur = cv2.GaussianBlur(small, (3, 3), 0)
    _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 3))
    connected = cv2.dilate(binary, kernel, iterations=1)
    contours, _ = cv2.findContours(connected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    angles: list[float] = []
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        if cw > small.shape[1] * 0.12 and 4 < ch < small.shape[0] * 0.08:
            rect = cv2.minAreaRect(cnt)
            ang = rect[-1]
            if ang < -45:
                ang = 90 + ang
            elif ang > 45:
                ang = ang - 90
            if -6.5 <= ang <= 6.5:
                angles.append(float(ang))

    if len(angles) < 3:
        return 0.0
    med = float(np.median(angles))
    return med if abs(med) >= 0.35 else 0.0


def _preprocess_for_ocr(bgr_img: np.ndarray, high_accuracy: bool) -> tuple[np.ndarray, float, np.ndarray | None]:
    """Enhance contrast/sharpness and optionally deskew; returns (processed_gray, angle, M_inv)."""
    gray = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2GRAY)
    angle = _estimate_skew_angle(gray) if high_accuracy else 0.0
    m_inv: np.ndarray | None = None

    if abs(angle) >= 0.35:
        h, w = gray.shape[:2]
        center = (w / 2.0, h / 2.0)
        rot_mat = cv2.getRotationMatrix2D(center, angle, 1.0)
        m_inv = cv2.invertAffineTransform(rot_mat)
        gray = cv2.warpAffine(
            gray,
            rot_mat,
            (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )

    if high_accuracy:
        # Check contrast dynamic range; only apply CLAHE/denoising when scan is genuinely faded/noisy
        p5, p95 = np.percentile(gray, [5, 95])
        if (p95 - p5) < 135:
            if os.environ.get("BANGLADOC_LOW_MEMORY") == "1":
                denoised = cv2.GaussianBlur(gray, (3, 3), 0)
            else:
                denoised = cv2.fastNlMeansDenoising(gray, None, h=4, templateWindowSize=7, searchWindowSize=21)
            clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(12, 12))
            return clahe.apply(denoised), angle, m_inv
        # Mild unsharp/normalization for crisp Kar/Fola/Hasanta strokes
        norm_gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
        return norm_gray, angle, m_inv

    return gray, angle, m_inv


def _map_px_bbox_to_pt(
    px_box: tuple[float, float, float, float],
    px_to_pt: float,
    m_inv: np.ndarray | None,
    width_pt: float,
    height_pt: float,
) -> list[float]:
    x0, y0, x1, y1 = px_box
    if m_inv is not None:
        pts = np.array([[x0, y0, 1.0], [x1, y0, 1.0], [x1, y1, 1.0], [x0, y1, 1.0]], dtype=np.float64)
        mapped = (m_inv @ pts.T).T
        x0 = float(np.min(mapped[:, 0]))
        y0 = float(np.min(mapped[:, 1]))
        x1 = float(np.max(mapped[:, 0]))
        y1 = float(np.max(mapped[:, 1]))

    rx0 = max(0.0, min(width_pt, x0 * px_to_pt))
    ry0 = max(0.0, min(height_pt, y0 * px_to_pt))
    rx1 = max(rx0 + 1.0, min(width_pt, x1 * px_to_pt))
    ry1 = max(ry0 + 1.0, min(height_pt, y1 * px_to_pt))
    return [round(rx0, 2), round(ry0, 2), round(rx1, 2), round(ry1, 2)]


def _sample_ink_and_bg_colors(rgb_img: np.ndarray, bbox_pt: list[float], pt_to_px: float) -> tuple[list[int], list[int]]:
    """Sample actual foreground ink RGB and surrounding paper background RGB for faithful reconstruction."""
    h, w = rgb_img.shape[:2]
    x0 = max(0, min(w - 1, int(bbox_pt[0] * pt_to_px)))
    y0 = max(0, min(h - 1, int(bbox_pt[1] * pt_to_px)))
    x1 = max(x0 + 1, min(w, int(bbox_pt[2] * pt_to_px)))
    y1 = max(y0 + 1, min(h, int(bbox_pt[3] * pt_to_px)))

    crop = rgb_img[y0:y1, x0:x1]
    if crop.size == 0:
        return [20, 20, 20], [255, 255, 255]

    lum = 0.299 * crop[:, :, 0] + 0.587 * crop[:, :, 1] + 0.114 * crop[:, :, 2]
    p15 = float(np.percentile(lum, 15))
    p85 = float(np.percentile(lum, 85))

    ink_pixels = crop[lum <= p15]
    bg_pixels = crop[lum >= p85]

    ink = (
        [int(x) for x in np.median(ink_pixels, axis=0)]
        if len(ink_pixels) > 0
        else [20, 20, 20]
    )
    bg = (
        [int(x) for x in np.median(bg_pixels, axis=0)]
        if len(bg_pixels) > 0
        else [255, 255, 255]
    )
    return ink, bg


def _detect_bordered_tables(
    gray_img: np.ndarray,
    px_to_pt: float,
    width_pt: float,
    height_pt: float,
    page_num: int,
) -> tuple[list[OCRTableItem], np.ndarray]:
    """Detect ruled/bordered tables via OpenCV morphological horizontal & vertical line extraction."""
    h, w = gray_img.shape[:2]
    _, bw = cv2.threshold(gray_img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    h_len = max(25, w // 22)
    v_len = max(25, h // 28)
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_len, 1))
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_len))

    h_lines = cv2.morphologyEx(bw, cv2.MORPH_OPEN, h_kernel, iterations=1)
    v_lines = cv2.morphologyEx(bw, cv2.MORPH_OPEN, v_kernel, iterations=1)
    grid = cv2.add(h_lines, v_lines)
    grid_dilated = cv2.dilate(grid, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)), iterations=1)

    contours, _ = cv2.findContours(grid_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    tables: list[OCRTableItem] = []
    clean_grid_mask = np.zeros_like(gray_img)

    for t_idx, cnt in enumerate(contours):
        tx, ty, tw, th = cv2.boundingRect(cnt)
        if tw < w * 0.20 or th < h * 0.05:
            continue

        sub_h = h_lines[ty : ty + th, tx : tx + tw]
        sub_v = v_lines[ty : ty + th, tx : tx + tw]
        joints = cv2.bitwise_and(
            cv2.dilate(sub_h, np.ones((5, 5), np.uint8)),
            cv2.dilate(sub_v, np.ones((5, 5), np.uint8)),
        )
        n_labels, _, stats, centroids = cv2.connectedComponentsWithStats(joints)
        if n_labels < 9:  # Need at least 3x3 intersections (2x2 cells)
            continue

        xs = sorted(float(c[0] + tx) for c in centroids[1:])
        ys = sorted(float(c[1] + ty) for c in centroids[1:])

        def _cluster_1d(vals: list[float], tol: float) -> list[float]:
            if not vals:
                return []
            clusters = [[vals[0]]]
            for v in vals[1:]:
                if abs(v - clusters[-1][-1]) <= tol:
                    clusters[-1].append(v)
                else:
                    clusters.append([v])
            return [float(np.mean(c)) for c in clusters]

        col_edges = _cluster_1d(xs, tol=max(10.0, w * 0.015))
        row_edges = _cluster_1d(ys, tol=max(8.0, h * 0.010))

        if len(col_edges) < 3 or len(row_edges) < 3:
            continue
        if len(col_edges) == 2 and len(row_edges) == 2:
            continue

        # Record exact table grid lines into clean_grid_mask so OCR sees clean text without box borders
        clean_grid_mask[ty : ty + th, tx : tx + tw] = grid[ty : ty + th, tx : tx + tw]

        cells: list[OCRTableCell] = []
        n_rows = len(row_edges) - 1
        n_cols = len(col_edges) - 1
        for r in range(n_rows):
            for c in range(n_cols):
                cbox = _map_px_bbox_to_pt(
                    (col_edges[c], row_edges[r], col_edges[c + 1], row_edges[r + 1]),
                    px_to_pt,
                    None,
                    width_pt,
                    height_pt,
                )
                cells.append(OCRTableCell(row=r, col=c, bbox=cbox, text=""))

        t_bbox = _map_px_bbox_to_pt(
            (col_edges[0], row_edges[0], col_edges[-1], row_edges[-1]),
            px_to_pt,
            None,
            width_pt,
            height_pt,
        )
        tables.append(
            OCRTableItem(
                id=f"p{page_num}_tbl{t_idx + 1}",
                bbox=t_bbox,
                rows=n_rows,
                cols=n_cols,
                cells=cells,
            )
        )

    return tables, clean_grid_mask


def _extract_non_text_figures_from_scan(
    rgb_img: np.ndarray,
    gray_img: np.ndarray,
    text_bboxes_pt: list[list[float]],
    table_bboxes_pt: list[list[float]],
    pt_to_px: float,
    px_to_pt: float,
    width_pt: float,
    height_pt: float,
    page_num: int,
    figures_dir: Path,
) -> list[OCRFigureItem]:
    """Detect illustrations, diagrams, emblems, or photos in a scanned page by masking text & tables."""
    h, w = gray_img.shape[:2]
    page_area_px = float(h * w)

    _, ink_mask = cv2.threshold(gray_img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Mask out all recognized text boxes (with padding) and table boxes
    pad = max(6, int(6 * pt_to_px))
    for bx in text_bboxes_pt:
        x0 = max(0, int(bx[0] * pt_to_px) - pad)
        y0 = max(0, int(bx[1] * pt_to_px) - pad)
        x1 = min(w, int(bx[2] * pt_to_px) + pad)
        y1 = min(h, int(bx[3] * pt_to_px) + pad)
        ink_mask[y0:y1, x0:x1] = 0

    for tx in table_bboxes_pt:
        x0 = max(0, int(tx[0] * pt_to_px) - pad)
        y0 = max(0, int(tx[1] * pt_to_px) - pad)
        x1 = min(w, int(tx[2] * pt_to_px) + pad)
        y1 = min(h, int(tx[3] * pt_to_px) + pad)
        ink_mask[y0:y1, x0:x1] = 0

    # Connect nearby figure strokes/regions
    k_size = max(15, int(w * 0.02))
    closed = cv2.morphologyEx(
        ink_mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_RECT, (k_size, k_size)),
    )
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    figures: list[OCRFigureItem] = []
    figures_dir.mkdir(parents=True, exist_ok=True)

    for idx, cnt in enumerate(contours):
        fx, fy, fw, fh = cv2.boundingRect(cnt)
        area_ratio = (fw * fh) / page_area_px
        # Must be meaningful illustration/logo/diagram (>= 1.2% of page, <= 75% of page, non-line aspect)
        if area_ratio < 0.012 or area_ratio > 0.75:
            continue
        if fw < 45 or fh < 45:
            continue
        aspect = fw / max(fh, 1)
        if aspect > 12.0 or aspect < 0.08:
            continue

        crop_rgb = rgb_img[fy : fy + fh, fx : fx + fw]
        if float(np.std(crop_rgb)) < 12.0:
            continue

        fig_name = f"p{page_num}_fig{len(figures) + 1}.png"
        fig_path = figures_dir / fig_name
        cv2.imwrite(str(fig_path), cv2.cvtColor(crop_rgb, cv2.COLOR_RGB2BGR))

        f_bbox = _map_px_bbox_to_pt((fx, fy, fx + fw, fy + fh), px_to_pt, None, width_pt, height_pt)
        figures.append(
            OCRFigureItem(
                id=f"p{page_num}_fig{len(figures) + 1}",
                bbox=f_bbox,
                image_rel_path=f"figures/{fig_name}",
                width_px=fw,
                height_px=fh,
            )
        )

    return figures


def _run_tesseract_tsv(
    gray_img: np.ndarray,
    lang_flag: str,
    high_accuracy: bool,
    work_dir: Path,
    page_num: int,
) -> list[dict[str, str]]:
    """Invoke portable Tesseract 5.5.3 LSTM and return parsed TSV rows."""
    low_mem = os.environ.get("BANGLADOC_LOW_MEMORY") == "1"
    # On 0.1-vCPU cloud tiers (BANGLADOC_LOW_MEMORY=1), int8 quantized tessdata_fast runs 6-8x faster without timing out
    use_best = high_accuracy and not low_mem
    tessdata_dir = TESSDATA_BEST_DIR if use_best else TESSDATA_FAST_DIR
    if not (tessdata_dir / "ben.traineddata").exists():
        tessdata_dir = TESSDATA_BEST_DIR

    tmp_img = work_dir / f"_ocr_in_p{page_num}.png"
    cv2.imwrite(str(tmp_img), gray_img)

    cmd = [
        TESSERACT_CMD,
        str(tmp_img),
        "stdout",
        "--tessdata-dir",
        str(tessdata_dir),
        "-l",
        lang_flag,
        "--oem",
        "1",
        "--psm",
        "3",
        "-c",
        "preserve_interword_spaces=1",
        "-c",
        "tessedit_create_tsv=1",
    ]

    # Critical for 0.1 vCPU containers: OMP_THREAD_LIMIT=1 stops Tesseract spawning 64 OpenMP spin-wait threads!
    tess_env = os.environ.copy()
    tess_env["OMP_THREAD_LIMIT"] = "1"
    tess_env["OMP_NUM_THREADS"] = "1"

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            timeout=300,
            env=tess_env,
        )
        tsv_text = proc.stdout.decode("utf-8", errors="replace")
    finally:
        tmp_img.unlink(missing_ok=True)

    reader = csv.DictReader(io.StringIO(tsv_text), delimiter="\t", quoting=csv.QUOTE_NONE)
    return list(reader)


def _infer_alignment(
    bbox: list[float],
    col_left: float,
    col_right: float,
    is_full_width_line: bool = False,
) -> Literal["left", "center", "right", "justify"]:
    col_w = max(col_right - col_left, 1.0)
    left_gap = max(0.0, bbox[0] - col_left)
    right_gap = max(0.0, col_right - bbox[2])
    line_w = bbox[2] - bbox[0]

    if is_full_width_line and left_gap < col_w * 0.06 and right_gap < col_w * 0.06:
        return "justify"
    if left_gap > col_w * 0.08 and right_gap > col_w * 0.08 and abs(left_gap - right_gap) < col_w * 0.08:
        return "center"
    if left_gap > col_w * 0.30 and right_gap < col_w * 0.08:
        return "right"
    return "left"


def _extract_native_unicode_page(
    page: fitz.Page,
    page_num: int,
    output_idx: int,
    job_dir: Path,
    preserve_images: bool,
    preserve_tables: bool,
) -> PageOCRResult:
    """Extract clean native Unicode layout directly from digital-born PDF pages."""
    rect = page.rect
    width_pt = float(rect.width)
    height_pt = float(rect.height)

    figures: list[OCRFigureItem] = []
    if preserve_images:
        fig_dir = job_dir / "figures"
        fig_dir.mkdir(parents=True, exist_ok=True)
        for idx, info in enumerate(page.get_image_info(xrefs=True)):
            bbox = info.get("bbox")
            xref = info.get("xref", 0)
            if not bbox or not xref:
                continue
            bw = bbox[2] - bbox[0]
            bh = bbox[3] - bbox[1]
            if bw < 24 or bh < 24:
                continue
            if (bw * bh) / max(width_pt * height_pt, 1.0) > 0.90:
                continue
            try:
                pix = fitz.Pixmap(page.parent, xref)
                if pix.n - pix.alpha > 3:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                fname = f"p{page_num}_fig{len(figures) + 1}.png"
                pix.save(str(fig_dir / fname))
                figures.append(
                    OCRFigureItem(
                        id=f"p{page_num}_fig{len(figures) + 1}",
                        bbox=[round(float(v), 2) for v in bbox],
                        image_rel_path=f"figures/{fname}",
                        width_px=pix.width,
                        height_px=pix.height,
                    )
                )
            except Exception:
                pass

    tables: list[OCRTableItem] = []
    if preserve_tables:
        try:
            tf = page.find_tables()
            for t_idx, tbl in enumerate(tf.tables):
                extracted = tbl.extract()
                if not extracted or len(extracted) < 2:
                    continue
                n_rows = len(extracted)
                n_cols = max((len(r) for r in extracted), default=0)
                if n_cols < 2:
                    continue
                cells: list[OCRTableCell] = []
                for r_i, row_vals in enumerate(extracted):
                    for c_i, val in enumerate(row_vals):
                        cell_txt = normalize_bangla_unicode(str(val or ""))
                        # Approximate cell box from table bbox if individual cell rect unavailable
                        tb = tbl.bbox
                        cw = (tb[2] - tb[0]) / n_cols
                        ch = (tb[3] - tb[1]) / n_rows
                        cb = [
                            round(tb[0] + c_i * cw, 2),
                            round(tb[1] + r_i * ch, 2),
                            round(tb[0] + (c_i + 1) * cw, 2),
                            round(tb[1] + (r_i + 1) * ch, 2),
                        ]
                        cells.append(OCRTableCell(row=r_i, col=c_i, bbox=cb, text=cell_txt, confidence=99.0))
                tables.append(
                    OCRTableItem(
                        id=f"p{page_num}_tbl{t_idx + 1}",
                        bbox=[round(float(v), 2) for v in tbl.bbox],
                        rows=n_rows,
                        cols=n_cols,
                        cells=cells,
                    )
                )
        except Exception:
            pass

    pdict = page.get_text("dict")
    raw_blocks = pdict.get("blocks", [])
    words_raw = page.get_text("words")  # (x0, y0, x1, y1, word, block_no, line_no, word_no)
    words_by_bl: dict[tuple[int, int], list[tuple]] = {}
    for w_tup in words_raw:
        words_by_bl.setdefault((int(w_tup[5]), int(w_tup[6])), []).append(w_tup)

    all_sizes: list[float] = []
    for b in raw_blocks:
        if b.get("type") == 0:
            for ln in b.get("lines", []):
                for sp in ln.get("spans", []):
                    if sp.get("text", "").strip():
                        all_sizes.append(float(sp.get("size", 11.0)))
    median_fs = float(np.median(all_sizes)) if all_sizes else 11.0

    blocks_out: list[OCRBlockItem] = []
    total_words = 0

    for b_idx, b in enumerate(raw_blocks):
        if b.get("type") != 0:
            continue
        b_bbox = [round(float(v), 2) for v in b.get("bbox", [0, 0, width_pt, height_pt])]
        if any(_rect_iou_or_containment(b_bbox, t.bbox) > 0.65 for t in tables):
            continue

        lines_out: list[OCRLineItem] = []
        for l_idx, ln in enumerate(b.get("lines", [])):
            spans = ln.get("spans", [])
            raw_line = "".join(sp.get("text", "") for sp in spans)
            norm_line = normalize_bangla_unicode(raw_line)
            if not norm_line:
                continue

            l_bbox = [round(float(v), 2) for v in ln.get("bbox", b_bbox)]
            fs = float(np.median([float(sp.get("size", 11.0)) for sp in spans if sp.get("text", "").strip()] or [11.0]))
            is_bold = any("bold" in str(sp.get("font", "")).lower() or (int(sp.get("flags", 0)) & 16) for sp in spans)
            color_int = int(spans[0].get("color", 0)) if spans else 0
            ink_rgb = [(color_int >> 16) & 255, (color_int >> 8) & 255, color_int & 255]

            w_items: list[OCRWordItem] = []
            for w_idx, wt in enumerate(words_by_bl.get((b_idx, l_idx), [])):
                w_txt = normalize_bangla_unicode(str(wt[4]))
                if not w_txt:
                    continue
                total_words += 1
                w_items.append(
                    OCRWordItem(
                        id=f"p{page_num}_b{b_idx}_l{l_idx}_w{w_idx}",
                        text=w_txt,
                        bbox=[round(float(wt[0]), 2), round(float(wt[1]), 2), round(float(wt[2]), 2), round(float(wt[3]), 2)],
                        confidence=99.0,
                        language=classify_token_language(w_txt),
                    )
                )

            lines_out.append(
                OCRLineItem(
                    id=f"p{page_num}_b{b_idx}_l{l_idx}",
                    text=norm_line,
                    bbox=l_bbox,
                    font_size_pt=round(fs, 2),
                    confidence=99.0,
                    is_bold=is_bold,
                    alignment="left",
                    ink_rgb=ink_rgb,
                    bg_rgb=[255, 255, 255],
                    words=w_items,
                )
            )

        if not lines_out:
            continue

        avg_fs = float(np.mean([ln.font_size_pt for ln in lines_out]))
        first_txt = lines_out[0].text
        role: Literal["heading", "paragraph", "list_item", "page_number", "caption", "table_text"] = "paragraph"
        if len(lines_out) == 1 and (b_bbox[1] < height_pt * 0.08 or b_bbox[3] > height_pt * 0.91) and PAGE_NUM_RE.match(first_txt):
            role = "page_number"
        elif avg_fs >= median_fs * 1.20 and len(lines_out) <= 3:
            role = "heading"
        elif LIST_PREFIX_RE.match(first_txt):
            role = "list_item"

        blocks_out.append(
            OCRBlockItem(
                id=f"p{page_num}_b{b_idx}",
                role=role,
                bbox=b_bbox,
                alignment=lines_out[0].alignment,
                confidence=99.0,
                lines=lines_out,
            )
        )

    return PageOCRResult(
        page_number=page_num,
        output_page_index=output_idx,
        width_pt=round(width_pt, 2),
        height_pt=round(height_pt, 2),
        extraction_method="native_unicode",
        deskew_angle_deg=0.0,
        mean_confidence=99.0 if total_words > 0 else 100.0,
        low_confidence_word_count=0,
        blocks=blocks_out,
        tables=tables,
        figures=figures,
    )


def process_pdf_page(
    doc: fitz.Document,
    page_number: int,
    output_page_index: int,
    settings: ConversionSettings,
    job_dir: Path,
) -> PageOCRResult:
    """Process a single 1-indexed PDF page: detect reliable Unicode vs run full Bangla+English OCR."""
    page = doc[page_number - 1]
    rect = page.rect
    width_pt = float(rect.width)
    height_pt = float(rect.height)

    # 1. Check whether reliable Unicode text layer already exists without big scan image
    raw_text = (page.get_text("text") or "").strip()
    fonts = [f[3] for f in page.get_fonts() if len(f) > 3 and f[3]]
    legacy_ansi = detect_legacy_ansi_encoding(raw_text, fonts)

    large_scan_img = False
    page_area = max(width_pt * height_pt, 1.0)
    for img_info in page.get_image_info(xrefs=False):
        bbox = img_info.get("bbox")
        if bbox and ((bbox[2] - bbox[0]) * (bbox[3] - bbox[1])) / page_area >= 0.45:
            large_scan_img = True
            break

    if len(raw_text) >= 40 and not large_scan_img and not legacy_ansi:
        return _extract_native_unicode_page(
            page=page,
            page_num=page_number,
            output_idx=output_page_index,
            job_dir=job_dir,
            preserve_images=settings.preserve_images,
            preserve_tables=settings.preserve_tables,
        )

    # 2. Scanned / Image-based / Legacy ANSI page -> Render high-DPI raster & run OpenCV + Tesseract 5.5.3
    high_acc = settings.ocr_accuracy == "high"
    low_mem = os.environ.get("BANGLADOC_LOW_MEMORY") == "1"
    dpi = (175 if low_mem else 300) if high_acc else (150 if low_mem else 210)
    pt_to_px = dpi / 72.0
    px_to_pt = 72.0 / dpi

    pix = page.get_pixmap(dpi=dpi, alpha=False)
    rgb_img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    bgr_img = cv2.cvtColor(rgb_img, cv2.COLOR_RGB2BGR)
    raw_gray = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2GRAY)

    # Save clean rendered page background for Layout-Preserved PDF & visual QA diffing
    pages_cache_dir = job_dir / "page_renders"
    pages_cache_dir.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(pages_cache_dir / f"source_p{page_number}.png"), bgr_img)

    # Detect bordered tables on original unwarped grayscale BEFORE OCR so we can erase grid borders for clean cell OCR!
    tables: list[OCRTableItem] = []
    grid_mask = np.zeros_like(raw_gray)
    if settings.preserve_tables:
        tables, grid_mask = _detect_bordered_tables(raw_gray, px_to_pt, width_pt, height_pt, page_number)

    proc_gray, skew_deg, m_inv = _preprocess_for_ocr(bgr_img, high_accuracy=high_acc)
    if tables and m_inv is None and np.any(grid_mask > 0):
        proc_gray = proc_gray.copy()
        proc_gray[grid_mask > 0] = 255

    lang_map = {
        "auto": "ben+eng",
        "ben": "ben",
        "eng": "eng",
    }
    lang_flag = lang_map.get(settings.ocr_language, "ben+eng")

    tsv_rows = _run_tesseract_tsv(
        gray_img=proc_gray,
        lang_flag=lang_flag,
        high_accuracy=high_acc,
        work_dir=job_dir,
        page_num=page_number,
    )

    # Group TSV words into (block_num, par_num, line_num)
    grouped_lines: dict[tuple[int, int, int], list[OCRWordItem]] = {}
    all_words_flat: list[OCRWordItem] = []

    for r_idx, row in enumerate(tsv_rows):
        try:
            level = int(row.get("level", 0))
            if level != 5:
                continue
            conf = float(row.get("conf", -1))
            raw_tok = str(row.get("text") or "").strip()
            norm_tok = normalize_bangla_unicode(raw_tok)
            if not norm_tok or conf < 0:
                continue

            lx = float(row.get("left", 0))
            ly = float(row.get("top", 0))
            lw = float(row.get("width", 0))
            lh = float(row.get("height", 0))
            if lw < 2 or lh < 2:
                continue
            # Filter tiny low-confidence speckle noise
            if conf < 22 and len(norm_tok) <= 1 and norm_tok not in ("ও", "এ", "I", "a", "A"):
                continue

            w_bbox = _map_px_bbox_to_pt((lx, ly, lx + lw, ly + lh), px_to_pt, m_inv, width_pt, height_pt)
            b_no = int(row.get("block_num", 1))
            p_no = int(row.get("par_num", 1))
            l_no = int(row.get("line_num", 1))

            w_item = OCRWordItem(
                id=f"p{page_number}_b{b_no}p{p_no}_l{l_no}_w{r_idx}",
                text=norm_tok,
                bbox=w_bbox,
                confidence=round(conf, 1),
                language=classify_token_language(norm_tok),
            )
            grouped_lines.setdefault((b_no, p_no, l_no), []).append(w_item)
            all_words_flat.append(w_item)
        except Exception:
            continue

    # Assign words falling inside table cells into table structure
    words_in_tables: set[str] = set()
    for tbl in tables:
        cell_words_map: dict[tuple[int, int], list[OCRWordItem]] = {}
        for w_item in all_words_flat:
            if _rect_iou_or_containment(w_item.bbox, tbl.bbox) >= 0.55:
                words_in_tables.add(w_item.id)
                best_cell: OCRTableCell | None = None
                best_score = 0.0
                for cell in tbl.cells:
                    sc = _rect_iou_or_containment(w_item.bbox, cell.bbox)
                    if sc > best_score:
                        best_score = sc
                        best_cell = cell
                if best_cell is not None and best_score > 0.25:
                    cell_words_map.setdefault((best_cell.row, best_cell.col), []).append(w_item)

        for cell in tbl.cells:
            c_words = cell_words_map.get((cell.row, cell.col), [])
            if c_words:
                c_words.sort(key=lambda w: (round(w.bbox[1] / 6.0), w.bbox[0]))
                cell.text = normalize_bangla_unicode(" ".join(w.text for w in c_words))
                cell.confidence = round(float(np.mean([w.confidence for w in c_words])), 1)

    # Determine document body horizontal margins for alignment inference
    non_table_words = [w for w in all_words_flat if w.id not in words_in_tables]
    if non_table_words:
        col_left = float(np.percentile([w.bbox[0] for w in non_table_words], 8))
        col_right = float(np.percentile([w.bbox[2] for w in non_table_words], 92))
    else:
        col_left, col_right = width_pt * 0.1, width_pt * 0.9

    # Group lines into paragraph blocks (b_no, p_no)
    par_groups: dict[tuple[int, int], list[OCRLineItem]] = {}
    line_heights: list[float] = []

    for (b_no, p_no, l_no), w_list in sorted(grouped_lines.items()):
        rem_words = [w for w in w_list if w.id not in words_in_tables]
        if not rem_words:
            continue
        rem_words.sort(key=lambda w: w.bbox[0])
        line_txt = normalize_bangla_unicode(" ".join(w.text for w in rem_words))
        if not line_txt:
            continue

        lx0 = min(w.bbox[0] for w in rem_words)
        ly0 = min(w.bbox[1] for w in rem_words)
        lx1 = max(w.bbox[2] for w in rem_words)
        ly1 = max(w.bbox[3] for w in rem_words)
        l_bbox = [round(lx0, 2), round(ly0, 2), round(lx1, 2), round(ly1, 2)]

        # Median word height gives reliable font size unaffected by tall single brackets
        med_wh = float(np.median([w.bbox[3] - w.bbox[1] for w in rem_words]))
        fs_pt = round(max(6.5, min(48.0, med_wh * 0.78)), 1)
        line_heights.append(fs_pt)

        ink_rgb, bg_rgb = _sample_ink_and_bg_colors(rgb_img, l_bbox, pt_to_px)
        line_conf = round(float(np.mean([w.confidence for w in rem_words])), 1)

        par_groups.setdefault((b_no, p_no), []).append(
            OCRLineItem(
                id=f"p{page_number}_b{b_no}p{p_no}_l{l_no}",
                text=line_txt,
                bbox=l_bbox,
                font_size_pt=fs_pt,
                confidence=line_conf,
                is_bold=False,
                alignment="left",
                ink_rgb=ink_rgb,
                bg_rgb=bg_rgb,
                words=rem_words,
            )
        )

    median_fs = float(np.median(line_heights)) if line_heights else 11.5
    blocks_out: list[OCRBlockItem] = []

    for (b_no, p_no), lines in sorted(par_groups.items()):
        lines.sort(key=lambda ln: ln.bbox[1])
        bx0 = min(ln.bbox[0] for ln in lines)
        by0 = min(ln.bbox[1] for ln in lines)
        bx1 = max(ln.bbox[2] for ln in lines)
        by1 = max(ln.bbox[3] for ln in lines)
        b_bbox = [round(bx0, 2), round(by0, 2), round(bx1, 2), round(by1, 2)]

        avg_fs = float(np.mean([ln.font_size_pt for ln in lines]))
        b_conf = round(float(np.mean([ln.confidence for ln in lines])), 1)
        first_txt = lines[0].text

        role: Literal["heading", "paragraph", "list_item", "page_number", "caption", "table_text"] = "paragraph"
        if (
            len(lines) == 1
            and (by0 < height_pt * 0.085 or by1 > height_pt * 0.91)
            and PAGE_NUM_RE.match(first_txt)
        ):
            role = "page_number"
        elif avg_fs >= median_fs * 1.20 and len(lines) <= 3:
            role = "heading"
            for ln in lines:
                ln.is_bold = True
        elif LIST_PREFIX_RE.match(first_txt):
            role = "list_item"

        for idx_ln, ln in enumerate(lines):
            is_non_last = len(lines) > 1 and idx_ln < len(lines) - 1
            ln.alignment = _infer_alignment(ln.bbox, col_left, col_right, is_full_width_line=is_non_last)

        block_align = lines[0].alignment
        blocks_out.append(
            OCRBlockItem(
                id=f"p{page_number}_b{b_no}p{p_no}",
                role=role,
                bbox=b_bbox,
                alignment=block_align,
                confidence=b_conf,
                lines=lines,
            )
        )

    # Sort blocks in natural top-to-bottom reading order (handling multi-column safely via Y-band + X)
    blocks_out.sort(key=lambda b: (round(b.bbox[1] / 18.0), b.bbox[0]))

    # Extract non-text figures/illustrations from scan if requested
    figures: list[OCRFigureItem] = []
    if settings.preserve_images:
        all_line_boxes = [w.bbox for w in all_words_flat]
        all_tbl_boxes = [t.bbox for t in tables]
        figures = _extract_non_text_figures_from_scan(
            rgb_img=rgb_img,
            gray_img=raw_gray,
            text_bboxes_pt=all_line_boxes,
            table_bboxes_pt=all_tbl_boxes,
            pt_to_px=pt_to_px,
            px_to_pt=px_to_pt,
            width_pt=width_pt,
            height_pt=height_pt,
            page_num=page_number,
            figures_dir=job_dir / "figures",
        )

    mean_conf = round(float(np.mean([w.confidence for w in all_words_flat])), 1) if all_words_flat else 0.0
    low_conf_cnt = sum(1 for w in all_words_flat if w.confidence < 70.0)

    return PageOCRResult(
        page_number=page_number,
        output_page_index=output_page_index,
        width_pt=round(width_pt, 2),
        height_pt=round(height_pt, 2),
        extraction_method="tesseract_ocr",
        deskew_angle_deg=round(skew_deg, 2),
        mean_confidence=mean_conf,
        low_confidence_word_count=low_conf_cnt,
        blocks=blocks_out,
        tables=tables,
        figures=figures,
    )
