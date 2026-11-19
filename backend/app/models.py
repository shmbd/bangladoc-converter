from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class PageInspectionInfo(BaseModel):
    page_number: int  # 1-indexed
    width_pt: float
    height_pt: float
    has_reliable_text: bool
    has_legacy_encoding_suspect: bool = False
    image_count: int = 0
    char_count: int = 0
    mode_detected: Literal["digital_text", "scanned_image", "hybrid", "legacy_ansi_suspect"]
    thumbnail_url: str


class UploadInspectResponse(BaseModel):
    upload_id: str
    filename: str
    file_size_bytes: int
    page_count: int
    title: str = ""
    author: str = ""
    is_encrypted: bool = False
    pages: list[PageInspectionInfo]


class ConversionSettings(BaseModel):
    ocr_language: Literal["auto", "ben", "eng"] = "auto"
    output_format: Literal["all", "searchable_pdf", "editable_pdf", "layout_pdf", "epub"] = "all"
    epub_layout: Literal["reflowable", "fixed"] = "reflowable"
    ocr_accuracy: Literal["standard", "high"] = "high"
    preserve_layout: bool = True
    preserve_images: bool = True
    preserve_tables: bool = True
    embed_fonts: bool = True
    bangla_font: Literal["hind_siliguri", "noto_sans_bengali", "noto_serif_bengali", "kalpurush"] = "hind_siliguri"
    page_range: str = ""  # empty means all pages, e.g. "1-3, 5"
    doc_title: str = ""
    doc_author: str = ""


class StartConversionRequest(BaseModel):
    upload_id: str
    settings: ConversionSettings = Field(default_factory=ConversionSettings)


class OCRWordItem(BaseModel):
    id: str
    text: str
    bbox: list[float]  # [x0, y0, x1, y1] in PDF points (top-left origin)
    confidence: float
    language: Literal["bn", "en", "num", "punct", "mixed"] = "bn"


class OCRLineItem(BaseModel):
    id: str
    text: str
    bbox: list[float]  # [x0, y0, x1, y1] in PDF points
    font_size_pt: float
    confidence: float
    is_bold: bool = False
    alignment: Literal["left", "center", "right", "justify"] = "left"
    ink_rgb: list[int] = Field(default_factory=lambda: [20, 20, 20])
    bg_rgb: list[int] = Field(default_factory=lambda: [255, 255, 255])
    words: list[OCRWordItem] = Field(default_factory=list)


class OCRTableCell(BaseModel):
    row: int
    col: int
    bbox: list[float]
    text: str
    confidence: float = 90.0


class OCRTableItem(BaseModel):
    id: str
    bbox: list[float]
    rows: int
    cols: int
    cells: list[OCRTableCell] = Field(default_factory=list)


class OCRFigureItem(BaseModel):
    id: str
    bbox: list[float]
    image_rel_path: str
    width_px: int
    height_px: int


class OCRBlockItem(BaseModel):
    id: str
    role: Literal["heading", "paragraph", "list_item", "page_number", "caption", "table_text"] = "paragraph"
    bbox: list[float]
    alignment: Literal["left", "center", "right", "justify"] = "left"
    confidence: float
    lines: list[OCRLineItem] = Field(default_factory=list)


class PageOCRResult(BaseModel):
    page_number: int  # 1-indexed source page number
    output_page_index: int  # 1-indexed within selected pages
    width_pt: float
    height_pt: float
    extraction_method: Literal["native_unicode", "tesseract_ocr"]
    deskew_angle_deg: float = 0.0
    mean_confidence: float = 0.0
    low_confidence_word_count: int = 0
    layout_similarity_score: float = 100.0
    blocks: list[OCRBlockItem] = Field(default_factory=list)
    tables: list[OCRTableItem] = Field(default_factory=list)
    figures: list[OCRFigureItem] = Field(default_factory=list)


class PageQASummary(BaseModel):
    page_number: int
    output_page_index: int
    mean_confidence: float
    low_confidence_words: int
    layout_similarity_pct: float
    editable_similarity_pct: float
    significant_diff_flagged: bool = False
    bangla_chars: int = 0
    english_chars: int = 0
    juktakkhor_count: int = 0


class QAReport(BaseModel):
    overall_passed: bool = True
    mean_ocr_confidence: float = 0.0
    unicode_integrity_passed: bool = True
    character_order_valid: bool = True
    selectable_text_verified: bool = True
    page_count_consistent: bool = True
    source_selected_pages: int = 0
    converted_page_count: int = 0
    total_words: int = 0
    low_confidence_words: int = 0
    bangla_char_count: int = 0
    english_char_count: int = 0
    bangla_numeral_count: int = 0
    juktakkhor_count: int = 0
    kar_fola_count: int = 0
    headings_detected: int = 0
    paragraphs_detected: int = 0
    tables_preserved: int = 0
    images_preserved: int = 0
    searchable_layout_similarity_pct: float = 100.0
    layout_preserved_similarity_pct: float = 95.0
    editable_layout_similarity_pct: float = 90.0
    flagged_pages: list[int] = Field(default_factory=list)
    per_page: list[PageQASummary] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class JobStatusResponse(BaseModel):
    job_id: str
    upload_id: str
    filename: str
    status: Literal["queued", "processing", "completed", "failed", "cancelled"]
    stage: str
    stage_bn: str = ""
    progress_pct: float = 0.0
    current_page: int = 0
    total_pages: int = 0
    created_at: str
    completed_at: str | None = None
    expires_at: str | None = None
    error_message: str | None = None
    settings: ConversionSettings
    available_downloads: dict[str, str] = Field(default_factory=dict)
    qa_report: QAReport | None = None


class LineEditItem(BaseModel):
    page_number: int
    line_id: str
    new_text: str


class ManualCorrectionRequest(BaseModel):
    edits: list[LineEditItem]


class SystemSettingsModel(BaseModel):
    retention_hours: int = 24
    default_ocr_language: Literal["auto", "ben", "eng"] = "auto"
    default_ocr_accuracy: Literal["standard", "high"] = "high"
    default_bangla_font: Literal["hind_siliguri", "noto_sans_bengali", "noto_serif_bengali", "kalpurush"] = "hind_siliguri"
    default_epub_layout: Literal["reflowable", "fixed"] = "reflowable"
    auto_cleanup_enabled: bool = True
