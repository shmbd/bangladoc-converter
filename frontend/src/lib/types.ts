export type UILang = "en" | "bn";

export type AppView =
  | "home"
  | "processing"
  | "preview"
  | "download"
  | "history"
  | "settings";

export interface PageInspectionInfo {
  page_number: number;
  width_pt: number;
  height_pt: number;
  has_reliable_text: boolean;
  has_legacy_encoding_suspect: boolean;
  image_count: number;
  char_count: number;
  mode_detected: "digital_text" | "scanned_image" | "hybrid" | "legacy_ansi_suspect";
  thumbnail_url: string;
}

export interface UploadInspectResponse {
  upload_id: string;
  filename: string;
  file_size_bytes: number;
  page_count: number;
  title: string;
  author: string;
  is_encrypted: boolean;
  pages: PageInspectionInfo[];
}

export interface ConversionSettings {
  ocr_language: "auto" | "ben" | "eng";
  output_format: "all" | "searchable_pdf" | "editable_pdf" | "layout_pdf" | "epub";
  epub_layout: "reflowable" | "fixed";
  ocr_accuracy: "standard" | "high";
  preserve_layout: boolean;
  preserve_images: boolean;
  preserve_tables: boolean;
  embed_fonts: boolean;
  bangla_font: "hind_siliguri" | "noto_sans_bengali" | "noto_serif_bengali" | "kalpurush";
  page_range: string;
  doc_title: string;
  doc_author: string;
}

export interface OCRWordItem {
  id: string;
  text: string;
  bbox: [number, number, number, number];
  confidence: number;
  language: "bn" | "en" | "num" | "punct" | "mixed";
}

export interface OCRLineItem {
  id: string;
  text: string;
  bbox: [number, number, number, number];
  font_size_pt: number;
  confidence: number;
  is_bold: boolean;
  alignment: "left" | "center" | "right" | "justify";
  ink_rgb: [number, number, number];
  bg_rgb: [number, number, number];
  words: OCRWordItem[];
}

export interface OCRTableCell {
  row: number;
  col: number;
  bbox: [number, number, number, number];
  text: string;
  confidence: number;
}

export interface OCRTableItem {
  id: string;
  bbox: [number, number, number, number];
  rows: number;
  cols: number;
  cells: OCRTableCell[];
}

export interface OCRFigureItem {
  id: string;
  bbox: [number, number, number, number];
  image_rel_path: string;
  width_px: number;
  height_px: number;
}

export interface OCRBlockItem {
  id: string;
  role: "heading" | "paragraph" | "list_item" | "page_number" | "caption" | "table_text";
  bbox: [number, number, number, number];
  alignment: "left" | "center" | "right" | "justify";
  confidence: number;
  lines: OCRLineItem[];
}

export interface PageOCRResult {
  page_number: number;
  output_page_index: number;
  width_pt: number;
  height_pt: number;
  extraction_method: "native_unicode" | "tesseract_ocr";
  deskew_angle_deg: number;
  mean_confidence: number;
  low_confidence_word_count: number;
  layout_similarity_score: number;
  blocks: OCRBlockItem[];
  tables: OCRTableItem[];
  figures: OCRFigureItem[];
}

export interface PageQASummary {
  page_number: number;
  output_page_index: number;
  mean_confidence: number;
  low_confidence_words: number;
  layout_similarity_pct: number;
  editable_similarity_pct: number;
  significant_diff_flagged: boolean;
  bangla_chars: number;
  english_chars: number;
  juktakkhor_count: number;
}

export interface QAReport {
  overall_passed: boolean;
  mean_ocr_confidence: number;
  unicode_integrity_passed: boolean;
  character_order_valid: boolean;
  selectable_text_verified: boolean;
  page_count_consistent: boolean;
  source_selected_pages: number;
  converted_page_count: number;
  total_words: number;
  low_confidence_words: number;
  bangla_char_count: number;
  english_char_count: number;
  bangla_numeral_count: number;
  juktakkhor_count: number;
  kar_fola_count: number;
  headings_detected: number;
  paragraphs_detected: number;
  tables_preserved: number;
  images_preserved: number;
  searchable_layout_similarity_pct: number;
  layout_preserved_similarity_pct: number;
  editable_layout_similarity_pct: number;
  flagged_pages: number[];
  per_page: PageQASummary[];
  warnings: string[];
}

export interface JobStatusResponse {
  job_id: string;
  upload_id: string;
  filename: string;
  status: "queued" | "processing" | "completed" | "failed" | "cancelled";
  stage: string;
  stage_bn: string;
  progress_pct: number;
  current_page: number;
  total_pages: number;
  created_at: string;
  completed_at: string | null;
  expires_at: string | null;
  error_message: string | null;
  settings: ConversionSettings;
  available_downloads: Record<string, string>;
  qa_report: QAReport | null;
}

export interface LineEditItem {
  page_number: number;
  line_id: string;
  new_text: string;
}

export interface SystemSettingsModel {
  retention_hours: number;
  default_ocr_language: "auto" | "ben" | "eng";
  default_ocr_accuracy: "standard" | "high";
  default_bangla_font: "hind_siliguri" | "noto_sans_bengali" | "noto_serif_bengali" | "kalpurush";
  default_epub_layout: "reflowable" | "fixed";
  auto_cleanup_enabled: boolean;
}

export interface HealthInfo {
  status: string;
  tesseract_available: boolean;
  tesseract_version: string;
  bangla_best_model: boolean;
  bangla_fast_model: boolean;
  fonts: { id: string; label: string; license: string }[];
  privacy: {
    ai_training: boolean;
    public_exposure: boolean;
    retention_hours: number;
  };
}
