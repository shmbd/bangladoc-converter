from __future__ import annotations

import html
import uuid
from pathlib import Path

from ebooklib import epub

from app.config import AVAILABLE_FONTS
from app.models import ConversionSettings, OCRBlockItem, OCRFigureItem, OCRTableItem, PageOCRResult


def _build_table_html(tbl: OCRTableItem, fixed_mode: bool = False) -> str:
    grid: dict[tuple[int, int], str] = {}
    for cell in tbl.cells:
        grid[(cell.row, cell.col)] = html.escape(cell.text)

    style_attr = ""
    if fixed_mode:
        x0, y0, x1, y1 = tbl.bbox
        style_attr = (
            f' style="position:absolute; left:{x0:.1f}px; top:{y0:.1f}px; '
            f'width:{max(20.0, x1 - x0):.1f}px; height:{max(16.0, y1 - y0):.1f}px;"'
        )

    rows_html: list[str] = [f'<table class="doc-table"{style_attr}>']
    for r in range(tbl.rows):
        rows_html.append("<tr>")
        tag = "th" if r == 0 else "td"
        for c in range(tbl.cols):
            val = grid.get((r, c), "")
            rows_html.append(f"<{tag}>{val}</{tag}>")
        rows_html.append("</tr>")
    rows_html.append("</table>")
    return "\n".join(rows_html)


def generate_epub3(
    ocr_pages: list[PageOCRResult],
    settings: ConversionSettings,
    job_dir: Path,
    source_filename: str,
    output_path: Path,
) -> Path:
    """Generate a valid EPUB 3 e-book (Reflowable or Fixed Original-Layout) with embedded Bangla font & TOC."""
    book = epub.EpubBook()
    book_id = f"urn:uuid:{uuid.uuid4()}"
    title = settings.doc_title.strip() or Path(source_filename).stem
    author = settings.doc_author.strip() or "BanglaDoc Digitized Edition"

    book.set_identifier(book_id)
    book.set_title(title)
    book.set_language("bn")
    book.add_metadata("DC", "language", "en")
    book.add_author(author)
    book.add_metadata(None, "meta", "", {"property": "dcterms:modified", "content": "2026-11-19T00:00:00Z"})

    is_fixed = settings.epub_layout == "fixed"
    if is_fixed:
        book.add_metadata(None, "meta", "pre-paginated", {"property": "rendition:layout"})
        book.add_metadata(None, "meta", "auto", {"property": "rendition:orientation"})
        book.add_metadata(None, "meta", "none", {"property": "rendition:spread"})

    font_face_css = ""
    if settings.embed_fonts:
        font_meta = AVAILABLE_FONTS.get(settings.bangla_font) or AVAILABLE_FONTS["hind_siliguri"]
        reg_path = Path(font_meta["regular"])
        if reg_path.exists():
            font_item = epub.EpubItem(
                uid="font_bangla_regular",
                file_name=f"fonts/{reg_path.name}",
                media_type="font/ttf",
                content=reg_path.read_bytes(),
            )
            book.add_item(font_item)
            font_face_css = f"""
@font-face {{
    font-family: 'EmbeddedBangla';
    src: url('../fonts/{reg_path.name}') format('truetype');
    font-weight: normal;
    font-style: normal;
}}
"""

    base_css = f"""{font_face_css}
body {{
    font-family: 'EmbeddedBangla', 'Noto Sans Bengali', 'Hind Siliguri', 'Kalpurush', 'Nirmala UI', sans-serif;
    line-height: 1.72;
    color: #18181b;
    margin: 0;
    padding: {"0" if is_fixed else "1.2rem 1.4rem"};
}}
h1, h2, h3 {{
    font-family: 'EmbeddedBangla', 'Noto Sans Bengali', 'Hind Siliguri', sans-serif;
    line-height: 1.38;
    color: #0f172a;
    margin-top: 1.3em;
    margin-bottom: 0.55em;
}}
p {{
    margin: 0.55em 0;
    text-align: justify;
}}
p.align-center {{ text-align: center; }}
p.align-right {{ text-align: right; }}
p.align-left {{ text-align: left; }}
ul.doc-list {{
    margin: 0.6em 0 0.6em 1.4em;
}}
figure.doc-figure {{
    margin: 1.1em auto;
    text-align: center;
}}
figure.doc-figure img {{
    max-width: 100%;
    height: auto;
    border-radius: 4px;
}}
table.doc-table {{
    width: 100%;
    border-collapse: collapse;
    margin: 1em 0;
    font-size: 0.94em;
}}
table.doc-table th, table.doc-table td {{
    border: 1px solid #94a3b8;
    padding: 0.45em 0.6em;
    text-align: left;
    vertical-align: top;
}}
table.doc-table th {{
    background-color: #f1f5f9;
    font-weight: bold;
}}
.page-canvas {{
    position: relative;
    background: #ffffff;
    overflow: hidden;
}}
.fixed-block {{
    position: absolute;
    margin: 0;
    padding: 0;
    line-height: 1.25;
}}
"""
    style_item = epub.EpubItem(
        uid="style_main",
        file_name="styles/bangla.css",
        media_type="text/css",
        content=base_css.encode("utf-8"),
    )
    book.add_item(style_item)

    # Register extracted figures into EPUB manifest
    registered_images: dict[str, str] = {}
    if settings.preserve_images:
        for p_res in ocr_pages:
            for fig in p_res.figures:
                if fig.image_rel_path in registered_images:
                    continue
                fig_disk = job_dir / fig.image_rel_path
                if fig_disk.exists():
                    epub_img_path = f"images/{fig_disk.name}"
                    img_item = epub.EpubItem(
                        uid=f"img_{fig.id}",
                        file_name=epub_img_path,
                        media_type="image/png",
                        content=fig_disk.read_bytes(),
                    )
                    book.add_item(img_item)
                    registered_images[fig.image_rel_path] = f"../{epub_img_path}"

    chapters: list[epub.EpubHtml] = []
    toc_links: list[epub.Link] = []

    if is_fixed:
        # Fixed-Layout EPUB 3: 1 XHTML document per page preserving exact coordinates
        for p_res in ocr_pages:
            w_int = max(400, int(round(p_res.width_pt)))
            h_int = max(500, int(round(p_res.height_pt)))
            elements_html: list[str] = [
                f'<div class="page-canvas" style="width:{w_int}px; height:{h_int}px;">'
            ]

            if settings.preserve_images:
                for fig in p_res.figures:
                    src = registered_images.get(fig.image_rel_path)
                    if src:
                        fx0, fy0, fx1, fy1 = fig.bbox
                        elements_html.append(
                            f'<img src="{src}" alt="Illustration" '
                            f'style="position:absolute; left:{fx0:.1f}px; top:{fy0:.1f}px; '
                            f'width:{max(10.0, fx1 - fx0):.1f}px; height:{max(10.0, fy1 - fy0):.1f}px;" />'
                        )

            if settings.preserve_tables:
                for tbl in p_res.tables:
                    elements_html.append(_build_table_html(tbl, fixed_mode=True))

            page_heading_label = f"পৃষ্ঠা {p_res.page_number} (Page {p_res.page_number})"
            found_heading = False
            for blk in p_res.blocks:
                if not found_heading and blk.role == "heading" and blk.lines:
                    page_heading_label = blk.lines[0].text[:70]
                    found_heading = True
                for ln in blk.lines:
                    lx0, ly0, lx1, ly1 = ln.bbox
                    r, g, b = ln.ink_rgb[:3]
                    weight = "bold" if (ln.is_bold or blk.role == "heading") else "normal"
                    elements_html.append(
                        f'<div class="fixed-block" style="left:{lx0:.1f}px; top:{ly0:.1f}px; '
                        f'width:{max(20.0, (lx1 - lx0) * 1.08):.1f}px; font-size:{ln.font_size_pt:.1f}px; '
                        f'font-weight:{weight}; color:rgb({r},{g},{b});">'
                        f"{html.escape(ln.text)}</div>"
                    )

            elements_html.append("</div>")
            chap_file = f"chapters/page_{p_res.output_page_index:03d}.xhtml"
            chap = epub.EpubHtml(
                title=page_heading_label,
                file_name=chap_file,
                lang="bn",
            )
            chap.add_item(style_item)
            # Add viewport meta for fixed-layout readers
            chap.content = (
                f'<?xml version="1.0" encoding="utf-8"?>'
                f'<!DOCTYPE html>'
                f'<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="bn" lang="bn">'
                f'<head><title>{html.escape(page_heading_label)}</title>'
                f'<meta name="viewport" content="width={w_int}, height={h_int}"/>'
                f'<link rel="stylesheet" type="text/css" href="../styles/bangla.css"/>'
                f'</head><body>{"".join(elements_html)}</body></html>'
            ).encode("utf-8")

            book.add_item(chap)
            chapters.append(chap)
            toc_links.append(epub.Link(chap_file, page_heading_label, f"toc_p{p_res.output_page_index}"))
    else:
        # Reflowable EPUB 3: Semantic chapters grouped by detected headings or page sections
        section_groups: list[tuple[str, list[str]]] = []
        current_title = title
        current_parts: list[str] = []

        for p_res in ocr_pages:
            # Merge blocks, tables, and figures in vertical Y reading order on this page
            renderables: list[tuple[float, str, object]] = []
            for blk in p_res.blocks:
                if blk.role == "page_number":
                    continue
                renderables.append((blk.bbox[1], "block", blk))
            if settings.preserve_tables:
                for tbl in p_res.tables:
                    renderables.append((tbl.bbox[1], "table", tbl))
            if settings.preserve_images:
                for fig in p_res.figures:
                    renderables.append((fig.bbox[1], "figure", fig))

            renderables.sort(key=lambda item: item[0])

            for _, kind, obj in renderables:
                if kind == "block":
                    blk_obj: OCRBlockItem = obj  # type: ignore[assignment]
                    full_txt = " ".join(ln.text for ln in blk_obj.lines).strip()
                    if not full_txt:
                        continue
                    if blk_obj.role == "heading":
                        if current_parts:
                            section_groups.append((current_title, current_parts))
                            current_parts = []
                        current_title = full_txt[:90]
                        current_parts.append(f"<h2>{html.escape(full_txt)}</h2>")
                    elif blk_obj.role == "list_item":
                        current_parts.append(f'<ul class="doc-list"><li>{html.escape(full_txt)}</li></ul>')
                    else:
                        align_cls = f"align-{blk_obj.alignment}"
                        current_parts.append(f'<p class="{align_cls}">{html.escape(full_txt)}</p>')
                elif kind == "table":
                    tbl_obj: OCRTableItem = obj  # type: ignore[assignment]
                    current_parts.append(_build_table_html(tbl_obj, fixed_mode=False))
                elif kind == "figure":
                    fig_obj: OCRFigureItem = obj  # type: ignore[assignment]
                    src = registered_images.get(fig_obj.image_rel_path)
                    if src:
                        current_parts.append(
                            f'<figure class="doc-figure"><img src="{src}" alt="Document Illustration"/></figure>'
                        )

        if current_parts or not section_groups:
            if not current_parts:
                current_parts.append("<p>(কোনো পাঠ্য শনাক্ত করা যায়নি / No text recognized)</p>")
            section_groups.append((current_title, current_parts))

        for idx, (sec_title, body_nodes) in enumerate(section_groups, start=1):
            chap_file = f"chapters/chapter_{idx:03d}.xhtml"
            chap = epub.EpubHtml(title=sec_title, file_name=chap_file, lang="bn")
            chap.add_item(style_item)
            body_str = "\n".join(body_nodes)
            if not body_str.lstrip().startswith("<h"):
                body_str = f"<h1>{html.escape(sec_title)}</h1>\n" + body_str
            chap.content = f"<div>\n{body_str}\n</div>"
            book.add_item(chap)
            chapters.append(chap)
            toc_links.append(epub.Link(chap_file, sec_title, f"chap_{idx}"))

    book.toc = tuple(toc_links)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", *chapters] if not is_fixed else chapters

    epub.write_epub(str(output_path), book, {})
    return output_path
