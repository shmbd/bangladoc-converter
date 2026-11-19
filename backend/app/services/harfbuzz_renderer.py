from __future__ import annotations

import unicodedata
from pathlib import Path

import fitz
import uharfbuzz as hb
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont

from app.config import AVAILABLE_FONTS


class CubicRecordingPen(BasePen):
    """Decomposes TrueType quadratic contours (including oncurve-less contours) into PDF cubic Béziers."""

    def __init__(self, glyph_set):
        super().__init__(glyph_set)
        self.value: list[tuple[str, tuple]] = []

    def _moveTo(self, p0):
        self.value.append(("moveTo", (p0,)))

    def _lineTo(self, p1):
        self.value.append(("lineTo", (p1,)))

    def _curveToOne(self, p1, p2, p3):
        self.value.append(("curveTo", (p1, p2, p3)))

    def _closePath(self):
        self.value.append(("closePath", ()))


class FontShaperFace:
    """Cached HarfBuzz shaper + TrueType outline recorder + PyMuPDF font metric helper."""

    def __init__(self, font_path: str):
        self.font_path = font_path
        font_bytes = Path(font_path).read_bytes()
        self.hb_blob = hb.Blob(font_bytes)
        self.hb_face = hb.Face(self.hb_blob)
        self.hb_font = hb.Font(self.hb_face)
        self.upem = float(self.hb_face.upem or 1000)
        self.tt_font = TTFont(font_path)
        self.glyph_set = self.tt_font.getGlyphSet()
        self.fitz_font = fitz.Font(fontfile=font_path)
        self._glyph_cache: dict[int, list[tuple[str, tuple]]] = {}

    def get_glyph_cmds(self, gid: int) -> list[tuple[str, tuple]]:
        if gid not in self._glyph_cache:
            try:
                gname = self.tt_font.getGlyphName(gid)
                pen = CubicRecordingPen(self.glyph_set)
                self.glyph_set[gname].draw(pen)
                self._glyph_cache[gid] = pen.value
            except Exception:
                self._glyph_cache[gid] = []
        return self._glyph_cache[gid]

    def measure_shaped_width(self, text: str, fontsize: float) -> float:
        if not text:
            return 0.0
        buf = hb.Buffer()
        buf.add_str(unicodedata.normalize("NFC", text))
        buf.guess_segment_properties()
        hb.shape(self.hb_font, buf)
        scale = fontsize / self.upem
        return sum(pos.x_advance for pos in buf.glyph_positions) * scale


_FACE_CACHE: dict[str, FontShaperFace] = {}


def get_shaper_face(font_key: str, bold: bool = False) -> FontShaperFace:
    meta = AVAILABLE_FONTS.get(font_key) or AVAILABLE_FONTS["hind_siliguri"]
    path = meta["bold"] if bold else meta["regular"]
    if not Path(path).exists():
        path = meta["regular"]
    if path not in _FACE_CACHE:
        _FACE_CACHE[path] = FontShaperFace(path)
    return _FACE_CACHE[path]


class PageVectorAccumulator:
    """Accumulates vector shaped glyph paths and invisible NFC Unicode text for a single PDF page."""

    def __init__(self, page: fitz.Page, font_key: str = "hind_siliguri"):
        self.page = page
        self.page_height = float(page.rect.height)
        self.page_width = float(page.rect.width)
        self.font_key = font_key
        self.tw = fitz.TextWriter(page.rect)
        self.pdf_ops: list[str] = []

    def add_invisible_word(self, text: str, bbox: list[float], font_size_hint: float | None = None):
        """Overlay an invisible NFC Unicode word precisely aligned to [x0, y0, x1, y1]."""
        norm = unicodedata.normalize("NFC", text).strip()
        if not norm:
            return
        x0, y0, x1, y1 = bbox
        box_w = max(x1 - x0, 2.0)
        box_h = max(y1 - y0, 4.0)
        face = get_shaper_face(self.font_key, bold=False)

        fs = font_size_hint if font_size_hint and font_size_hint > 3 else box_h * 0.78
        raw_w = face.fitz_font.text_length(norm, fontsize=fs)
        if raw_w > 0:
            fs = fs * (box_w / raw_w)
        fs = max(3.5, min(box_h * 1.15, fs))

        # Baseline sits ~80% down the word bounding box
        baseline_y = min(self.page_height - 1.0, max(fs, y0 + box_h * 0.82))
        x_clamped = max(0.5, min(self.page_width - 2.0, x0))
        try:
            self.tw.append((x_clamped, baseline_y), norm + " ", font=face.fitz_font, fontsize=fs)
        except Exception:
            pass

    def add_visible_shaped_line(
        self,
        text: str,
        bbox: list[float],
        fontsize: float,
        bold: bool = False,
        ink_rgb: list[int] | None = None,
        alignment: str = "left",
        fit_to_box: bool = True,
    ):
        """Render crisp HarfBuzz-shaped Bangla+English vector curves + aligned invisible NFC Unicode text."""
        norm = unicodedata.normalize("NFC", text).strip()
        if not norm:
            return

        x0, y0, x1, y1 = bbox
        box_w = max(x1 - x0, 8.0)
        box_h = max(y1 - y0, 6.0)
        face = get_shaper_face(self.font_key, bold=bold)

        buf = hb.Buffer()
        buf.add_str(norm)
        buf.guess_segment_properties()
        hb.shape(face.hb_font, buf)

        infos = buf.glyph_infos
        positions = buf.glyph_positions
        if not infos:
            return

        fs = max(5.0, min(72.0, fontsize))
        scale = fs / face.upem
        shaped_w = sum(pos.x_advance for pos in positions) * scale

        h_scale = 1.0
        if fit_to_box and shaped_w > 0:
            ratio = box_w / shaped_w
            if shaped_w > box_w * 1.04:
                # Shrink horizontally slightly or reduce scale so text never overflows margin/cell
                if ratio >= 0.72:
                    h_scale = ratio
                else:
                    fs = max(5.0, fs * max(ratio, 0.55))
                    scale = fs / face.upem
                    shaped_w = sum(pos.x_advance for pos in positions) * scale
                    h_scale = min(1.0, box_w / max(shaped_w, 1.0))
            elif 1.0 <= ratio <= 1.22:
                h_scale = 1.0 + (ratio - 1.0) * 0.35

        draw_w = shaped_w * h_scale
        start_x = x0
        if alignment == "center" and draw_w < box_w:
            start_x = x0 + (box_w - draw_w) * 0.5
        elif alignment == "right" and draw_w < box_w:
            start_x = x1 - draw_w

        start_x = max(1.0, min(self.page_width - 4.0, start_x))
        baseline_y = min(self.page_height - 2.0, max(fs * 0.85, y0 + min(box_h * 0.80, fs * 0.92)))

        rgb = ink_rgb or [20, 20, 20]
        r, g, b = [max(0.0, min(1.0, c / 255.0)) for c in rgb[:3]]

        ops = [f"q {r:.3f} {g:.3f} {b:.3f} rg"]
        cx = start_x
        cy = self.page_height - baseline_y

        for info, pos in zip(infos, positions):
            cmds = face.get_glyph_cmds(info.codepoint)
            if cmds:
                gx = cx + pos.x_offset * scale * h_scale
                gy = cy + pos.y_offset * scale
                for op, pts in cmds:
                    if op == "moveTo":
                        px, py = pts[0]
                        ops.append(f"{gx + px * scale * h_scale:.2f} {gy + py * scale:.2f} m")
                    elif op == "lineTo":
                        px, py = pts[0]
                        ops.append(f"{gx + px * scale * h_scale:.2f} {gy + py * scale:.2f} l")
                    elif op == "curveTo":
                        (cx1, cy1), (cx2, cy2), (cx3, cy3) = pts
                        ops.append(
                            f"{gx + cx1 * scale * h_scale:.2f} {gy + cy1 * scale:.2f} "
                            f"{gx + cx2 * scale * h_scale:.2f} {gy + cy2 * scale:.2f} "
                            f"{gx + cx3 * scale * h_scale:.2f} {gy + cy3 * scale:.2f} c"
                        )
                    elif op == "closePath":
                        ops.append("h")
                ops.append("f")
            cx += pos.x_advance * scale * h_scale

        ops.append("Q")
        self.pdf_ops.append(" ".join(ops))

        # Coordinate-locked invisible NFC Unicode text span for copy-paste & Ctrl+F search!
        actual_span = max(cx - start_x, 4.0)
        unshaped_len = face.fitz_font.text_length(norm, fontsize=fs)
        adj_fs = fs * (actual_span / unshaped_len) if unshaped_len > 0 else fs
        adj_fs = max(3.5, min(fs * 1.35, adj_fs))
        try:
            self.tw.append((start_x, baseline_y), norm + " ", font=face.fitz_font, fontsize=adj_fs)
        except Exception:
            pass

    def commit(self):
        """Flush vector glyph curves and invisible Unicode text layer to the PDF page."""
        if self.pdf_ops:
            stream_payload = ("\n".join(self.pdf_ops) + "\n").encode("ascii")
            self.page.clean_contents()
            xrefs = self.page.get_contents()
            if not xrefs:
                sh = self.page.new_shape()
                sh.commit()
                self.page.clean_contents()
                xrefs = self.page.get_contents()
            if xrefs:
                doc = self.page.parent
                existing = doc.xref_stream(xrefs[-1]) or b""
                doc.update_stream(xrefs[-1], existing + b"\n" + stream_payload)

        # Commit invisible Unicode text layer (PDF Tr=3)
        self.tw.write_text(self.page, render_mode=3)
