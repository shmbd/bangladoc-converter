from __future__ import annotations

import zipfile
from pathlib import Path

from docx import Document as DocxDocument
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from app.models import ConversionSettings, OCRBlockItem, OCRFigureItem, OCRTableItem, PageOCRResult


def _set_run_bangla_font(run, font_family: str, size_pt: float, bold: bool = False, rgb: list[int] | None = None):
    run.font.name = font_family
    run.font.size = Pt(max(8.0, min(36.0, size_pt)))
    run.bold = bold
    if rgb and len(rgb) >= 3:
        run.font.color.rgb = RGBColor(int(rgb[0]), int(rgb[1]), int(rgb[2]))

    r_pr = run._r.get_or_add_rPr()
    r_fonts = r_pr.find(qn("w:rFonts"))
    if r_fonts is None:
        r_fonts = OxmlElement("w:rFonts")
        r_pr.append(r_fonts)
    r_fonts.set(qn("w:ascii"), font_family)
    r_fonts.set(qn("w:hAnsi"), font_family)
    r_fonts.set(qn("w:cs"), font_family)


def generate_txt_export(ocr_pages: list[PageOCRResult], output_path: Path) -> Path:
    """Export clean NFC Unicode Bangla & English text organized page-by-page."""
    sections: list[str] = []
    for p_res in ocr_pages:
        lines_buf: list[str] = [f"=== পৃষ্ঠা {p_res.page_number} | Page {p_res.page_number} ==="]
        items: list[tuple[float, str]] = []
        for blk in p_res.blocks:
            txt = "\n".join(ln.text for ln in blk.lines).strip()
            if txt:
                items.append((blk.bbox[1], txt))
        for tbl in p_res.tables:
            grid: dict[tuple[int, int], str] = {(c.row, c.col): c.text for c in tbl.cells}
            t_rows = []
            for r in range(tbl.rows):
                t_rows.append(" | ".join(grid.get((r, c), "") for c in range(tbl.cols)))
            items.append((tbl.bbox[1], "\n".join(t_rows)))

        items.sort(key=lambda x: x[0])
        for _, content in items:
            lines_buf.append(content)
        sections.append("\n\n".join(lines_buf))

    output_path.write_text("\n\n\n".join(sections) + "\n", encoding="utf-8")
    return output_path


def generate_docx_export(
    ocr_pages: list[PageOCRResult],
    settings: ConversionSettings,
    job_dir: Path,
    output_path: Path,
) -> Path:
    """Generate editable Microsoft Word (.docx) with Complex Script Bangla font styling, tables, and images."""
    doc = DocxDocument()
    font_map = {
        "hind_siliguri": "Hind Siliguri",
        "noto_sans_bengali": "Noto Sans Bengali",
        "noto_serif_bengali": "Noto Serif Bengali",
        "kalpurush": "Kalpurush",
    }
    font_family = font_map.get(settings.bangla_font, "Nirmala UI")

    align_map = {
        "left": WD_ALIGN_PARAGRAPH.LEFT,
        "center": WD_ALIGN_PARAGRAPH.CENTER,
        "right": WD_ALIGN_PARAGRAPH.RIGHT,
        "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
    }

    for idx_page, p_res in enumerate(ocr_pages):
        # Set page dimensions to match source PDF page
        sec = doc.sections[-1] if idx_page == 0 else doc.add_section()
        sec.page_width = Pt(p_res.width_pt)
        sec.page_height = Pt(p_res.height_pt)
        sec.top_margin = Inches(0.65)
        sec.bottom_margin = Inches(0.65)
        sec.left_margin = Inches(0.70)
        sec.right_margin = Inches(0.70)

        elements: list[tuple[float, str, object]] = []
        for blk in p_res.blocks:
            elements.append((blk.bbox[1], "block", blk))
        if settings.preserve_tables:
            for tbl in p_res.tables:
                elements.append((tbl.bbox[1], "table", tbl))
        if settings.preserve_images:
            for fig in p_res.figures:
                elements.append((fig.bbox[1], "figure", fig))

        elements.sort(key=lambda item: item[0])

        for _, kind, obj in elements:
            if kind == "block":
                blk_obj: OCRBlockItem = obj  # type: ignore[assignment]
                text_str = " ".join(ln.text for ln in blk_obj.lines).strip()
                if not text_str:
                    continue
                avg_fs = sum(ln.font_size_pt for ln in blk_obj.lines) / max(len(blk_obj.lines), 1)
                ink = blk_obj.lines[0].ink_rgb if blk_obj.lines else [20, 20, 20]
                is_head = blk_obj.role == "heading"

                p = doc.add_paragraph()
                p.alignment = align_map.get(blk_obj.alignment, WD_ALIGN_PARAGRAPH.LEFT)
                run = p.add_run(text_str)
                _set_run_bangla_font(run, font_family, avg_fs, bold=is_head, rgb=ink)

            elif kind == "table":
                tbl_obj: OCRTableItem = obj  # type: ignore[assignment]
                if tbl_obj.rows > 0 and tbl_obj.cols > 0:
                    w_tbl = doc.add_table(rows=tbl_obj.rows, cols=tbl_obj.cols)
                    w_tbl.style = "Table Grid"
                    for cell in tbl_obj.cells:
                        if 0 <= cell.row < tbl_obj.rows and 0 <= cell.col < tbl_obj.cols:
                            w_cell = w_tbl.cell(cell.row, cell.col)
                            w_cell.text = ""
                            cp = w_cell.paragraphs[0]
                            crun = cp.add_run(cell.text)
                            _set_run_bangla_font(crun, font_family, 10.5, bold=(cell.row == 0))

            elif kind == "figure":
                fig_obj: OCRFigureItem = obj  # type: ignore[assignment]
                fig_disk = job_dir / fig_obj.image_rel_path
                if fig_disk.exists():
                    try:
                        disp_w_in = max(1.0, min(5.8, (fig_obj.bbox[2] - fig_obj.bbox[0]) / 72.0))
                        fp = doc.add_paragraph()
                        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        fp.add_run().add_picture(str(fig_disk), width=Inches(disp_w_in))
                    except Exception:
                        pass

    doc.save(str(output_path))
    return output_path


def create_all_formats_zip(files_to_pack: dict[str, Path], zip_path: Path) -> Path:
    """Create a single downloadable ZIP archive containing all generated output formats."""
    with zipfile.ZipFile(str(zip_path), "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arcname, disk_path in files_to_pack.items():
            if disk_path.exists():
                zf.write(str(disk_path), arcname=arcname)
    return zip_path
