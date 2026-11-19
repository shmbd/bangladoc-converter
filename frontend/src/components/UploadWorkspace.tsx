"use client";

import React, { useRef, useState } from "react";
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  FileText,
  FileUp,
  Info,
  Layers,
  Loader2,
  Sparkles,
  Wand2,
} from "lucide-react";
import { apiUrl, formatBytes } from "@/lib/api";
import { TRANSLATIONS } from "@/lib/i18n";
import { ConversionSettings, UILang, UploadInspectResponse } from "@/lib/types";

interface UploadWorkspaceProps {
  lang: UILang;
  uploadInfo: UploadInspectResponse | null;
  settings: ConversionSettings;
  isUploading: boolean;
  errorMsg: string | null;
  onSelectFile: (file: File) => void;
  onLoadSample: () => void;
  onResetUpload: () => void;
  onChangeSettings: (next: ConversionSettings) => void;
  onStartConversion: () => void;
}

function serializePageNumbers(pages: number[], total: number): string {
  if (pages.length === 0 || pages.length === total) return "";
  const sorted = [...pages].sort((a, b) => a - b);
  const parts: string[] = [];
  let start = sorted[0];
  let prev = sorted[0];
  for (let i = 1; i < sorted.length; i++) {
    if (sorted[i] === prev + 1) {
      prev = sorted[i];
    } else {
      parts.push(start === prev ? `${start}` : `${start}-${prev}`);
      start = sorted[i];
      prev = sorted[i];
    }
  }
  parts.push(start === prev ? `${start}` : `${start}-${prev}`);
  return parts.join(", ");
}

export default function UploadWorkspace({
  lang,
  uploadInfo,
  settings,
  isUploading,
  errorMsg,
  onSelectFile,
  onLoadSample,
  onResetUpload,
  onChangeSettings,
  onStartConversion,
}: UploadWorkspaceProps) {
  const t = TRANSLATIONS[lang];
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [selectedPageSet, setSelectedPageSet] = useState<Set<number>>(new Set());

  // Sync selected set when uploadInfo changes
  React.useEffect(() => {
    if (uploadInfo) {
      const all = new Set<number>();
      for (let i = 1; i <= uploadInfo.page_count; i++) all.add(i);
      setSelectedPageSet(all);
    }
  }, [uploadInfo]);

  const togglePageSelection = (pageNum: number) => {
    if (!uploadInfo) return;
    const next = new Set(selectedPageSet);
    if (next.has(pageNum)) {
      if (next.size <= 1) return; // Keep at least 1 page selected
      next.delete(pageNum);
    } else {
      next.add(pageNum);
    }
    setSelectedPageSet(next);
    onChangeSettings({
      ...settings,
      page_range: serializePageNumbers(Array.from(next), uploadInfo.page_count),
    });
  };

  const selectAllPages = () => {
    if (!uploadInfo) return;
    const all = new Set<number>();
    for (let i = 1; i <= uploadInfo.page_count; i++) all.add(i);
    setSelectedPageSet(all);
    onChangeSettings({ ...settings, page_range: "" });
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const f = e.dataTransfer.files?.[0];
    if (f) onSelectFile(f);
  };

  return (
    <div className="space-y-8">
      {/* Hero Banner */}
      {!uploadInfo && (
        <div className="rounded-2xl bg-gradient-to-br from-emerald-950 via-emerald-900 to-slate-900 text-white p-8 md:p-10 shadow-lg border border-emerald-800/50">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-emerald-500/20 border border-emerald-400/30 text-emerald-200 text-xs font-medium mb-4">
            <Sparkles className="w-3.5 h-3.5" />
            <span>{t.heroBadge}</span>
          </div>
          <h1 className="text-2xl md:text-4xl font-bold tracking-tight max-w-3xl leading-tight font-bangla">
            {t.heroHeading}
          </h1>
          <p className="mt-3 text-emerald-100/85 max-w-3xl text-sm md:text-base leading-relaxed font-bangla">
            {t.heroDesc}
          </p>
        </div>
      )}

      {/* Error Notification */}
      {errorMsg && (
        <div className="rounded-xl bg-red-50 border border-red-200 p-4 flex items-start gap-3 text-red-800">
          <AlertCircle className="w-5 h-5 text-red-600 shrink-0 mt-0.5" />
          <div className="text-sm font-medium">{errorMsg}</div>
        </div>
      )}

      {/* Drag & Drop Upload Box */}
      {!uploadInfo ? (
        <div
          onDragEnter={(e) => {
            e.preventDefault();
            setDragActive(true);
          }}
          onDragOver={(e) => {
            e.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={(e) => {
            e.preventDefault();
            setDragActive(false);
          }}
          onDrop={handleDrop}
          className={`relative rounded-2xl border-2 border-dashed transition-all p-10 md:p-14 text-center bg-white shadow-sm ${
            dragActive
              ? "border-emerald-600 bg-emerald-50/60 scale-[1.005]"
              : "border-slate-300 hover:border-emerald-500"
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,application/pdf"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onSelectFile(f);
            }}
          />

          {isUploading ? (
            <div className="flex flex-col items-center py-6 space-y-4">
              <Loader2 className="w-12 h-12 text-emerald-600 animate-spin" />
              <p className="text-base font-semibold text-slate-800 font-bangla">{t.uploadingText}</p>
            </div>
          ) : (
            <div className="flex flex-col items-center space-y-4">
              <div className="w-16 h-16 rounded-2xl bg-emerald-100 text-emerald-700 flex items-center justify-center shadow-inner">
                <FileUp className="w-8 h-8" />
              </div>
              <div className="space-y-1.5">
                <h2 className="text-lg md:text-xl font-semibold text-slate-900 font-bangla">
                  {t.dropTitle}
                </h2>
                <p className="text-xs md:text-sm text-slate-500 max-w-xl mx-auto font-bangla">
                  {t.dropSub}
                </p>
              </div>

              <div className="flex flex-wrap items-center justify-center gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="px-6 py-3 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white font-semibold text-sm shadow-sm transition cursor-pointer"
                >
                  {t.selectFileBtn}
                </button>
                <button
                  type="button"
                  onClick={onLoadSample}
                  className="px-5 py-3 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 font-medium text-sm border border-slate-200 flex items-center gap-2 transition cursor-pointer font-bangla"
                >
                  <BookOpen className="w-4 h-4 text-emerald-700" />
                  <span>{t.trySampleBtn}</span>
                </button>
              </div>
            </div>
          )}
        </div>
      ) : (
        /* Uploaded PDF Inspection + Conversion Settings Grid */
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-7">
          {/* Left 7 cols: File Info + Page Thumbnails Preview */}
          <div className="lg:col-span-7 space-y-6">
            <div className="rounded-2xl bg-white border border-slate-200 p-5 shadow-sm flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-4 min-w-0">
                <div className="w-12 h-12 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0">
                  <FileText className="w-6 h-6" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs uppercase tracking-wider font-semibold text-emerald-700">
                    {t.fileSummary}
                  </p>
                  <h3 className="text-base font-bold text-slate-900 truncate font-bangla">
                    {uploadInfo.filename}
                  </h3>
                  <div className="flex items-center gap-3 text-xs text-slate-500 mt-0.5">
                    <span>
                      {t.sizeLabel}: <strong>{formatBytes(uploadInfo.file_size_bytes)}</strong>
                    </span>
                    <span>•</span>
                    <span>
                      {t.pagesLabel}: <strong>{uploadInfo.page_count}</strong>
                    </span>
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={onResetUpload}
                className="px-3.5 py-2 rounded-lg text-xs font-medium border border-slate-200 hover:bg-slate-100 text-slate-700 transition cursor-pointer"
              >
                {t.changeFileBtn}
              </button>
            </div>

            {/* Pre-conversion Page Thumbnail Selector */}
            <div className="rounded-2xl bg-white border border-slate-200 p-5 shadow-sm space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2 font-bangla">
                  <Layers className="w-4 h-4 text-emerald-700" />
                  <span>{t.pagePreviewTitle}</span>
                </h3>
                <button
                  type="button"
                  onClick={selectAllPages}
                  className="text-xs font-semibold text-emerald-700 hover:text-emerald-800 cursor-pointer"
                >
                  {t.selectAllPages} ({selectedPageSet.size}/{uploadInfo.page_count})
                </button>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 max-h-[520px] overflow-y-auto pr-1">
                {uploadInfo.pages.map((p) => {
                  const isSelected = selectedPageSet.has(p.page_number);
                  const badgeMap = {
                    scanned_image: {
                      text: t.scannedBadge,
                      cls: "bg-amber-100 text-amber-800 border-amber-200",
                    },
                    digital_text: {
                      text: t.digitalBadge,
                      cls: "bg-emerald-100 text-emerald-800 border-emerald-200",
                    },
                    hybrid: {
                      text: t.hybridBadge,
                      cls: "bg-blue-100 text-blue-800 border-blue-200",
                    },
                    legacy_ansi_suspect: {
                      text: t.legacyBadge,
                      cls: "bg-purple-100 text-purple-800 border-purple-200",
                    },
                  }[p.mode_detected];

                  return (
                    <div
                      key={p.page_number}
                      onClick={() => togglePageSelection(p.page_number)}
                      className={`group cursor-pointer rounded-xl border p-2.5 transition relative ${
                        isSelected
                          ? "border-emerald-600 bg-emerald-50/30 ring-2 ring-emerald-600/20"
                          : "border-slate-200 bg-slate-50 opacity-60 hover:opacity-90"
                      }`}
                    >
                      <div className="aspect-[1/1.38] bg-white rounded-lg overflow-hidden border border-slate-200 mb-2 relative flex items-center justify-center">
                        <img
                          src={apiUrl(p.thumbnail_url)}
                          alt={`Page ${p.page_number}`}
                          className="w-full h-full object-contain"
                          loading="lazy"
                        />
                        {isSelected && (
                          <span className="absolute top-2 right-2 bg-emerald-600 text-white rounded-full p-0.5 shadow">
                            <CheckCircle2 className="w-4 h-4" />
                          </span>
                        )}
                      </div>
                      <div className="flex items-center justify-between gap-1">
                        <span className="text-xs font-bold text-slate-700">#{p.page_number}</span>
                        <span
                          className={`text-[10px] font-medium px-1.5 py-0.5 rounded border truncate ${badgeMap.cls}`}
                        >
                          {badgeMap.text}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1 font-bangla">
                  {t.pageRangeLabel}
                </label>
                <input
                  type="text"
                  value={settings.page_range}
                  placeholder="e.g. 1-3, 5 or ১-৩, ৫"
                  onChange={(e) =>
                    onChangeSettings({ ...settings, page_range: e.target.value })
                  }
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600"
                />
              </div>
            </div>

            {/* Technical Distinction Callout */}
            <div className="rounded-2xl bg-slate-900 text-slate-100 p-5 space-y-2 border border-slate-800">
              <div className="flex items-center gap-2 text-emerald-400 text-xs font-bold uppercase tracking-wider">
                <Info className="w-4 h-4" />
                <span>{t.modeExplainerTitle}</span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed font-bangla">
                {t.modeExplainerDesc}
              </p>
            </div>
          </div>

          {/* Right 5 cols: Conversion Configuration */}
          <div className="lg:col-span-5">
            <div className="rounded-2xl bg-white border border-slate-200 p-6 shadow-sm space-y-5 sticky top-20">
              <h3 className="text-base font-bold text-slate-900 border-b border-slate-100 pb-3 font-bangla">
                {t.settingsTitle}
              </h3>

              {/* OCR Language */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5 font-bangla">
                  {t.ocrLangLabel}
                </label>
                <select
                  value={settings.ocr_language}
                  onChange={(e) =>
                    onChangeSettings({
                      ...settings,
                      ocr_language: e.target.value as ConversionSettings["ocr_language"],
                    })
                  }
                  className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600 font-bangla"
                >
                  <option value="auto">{t.langAuto}</option>
                  <option value="ben">{t.langBen}</option>
                  <option value="eng">{t.langEng}</option>
                </select>
              </div>

              {/* Output Format */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5 font-bangla">
                  {t.outputFormatLabel}
                </label>
                <select
                  value={settings.output_format}
                  onChange={(e) =>
                    onChangeSettings({
                      ...settings,
                      output_format: e.target.value as ConversionSettings["output_format"],
                    })
                  }
                  className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600 font-bangla"
                >
                  <option value="all">{t.fmtAll}</option>
                  <option value="searchable_pdf">{t.fmtSearchable}</option>
                  <option value="editable_pdf">{t.fmtEditable}</option>
                  <option value="layout_pdf">{t.fmtLayout}</option>
                  <option value="epub">{t.fmtEpub}</option>
                </select>
              </div>

              {/* EPUB Layout */}
              {(settings.output_format === "all" || settings.output_format === "epub") && (
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5 font-bangla">
                    {t.epubLayoutLabel}
                  </label>
                  <select
                    value={settings.epub_layout}
                    onChange={(e) =>
                      onChangeSettings({
                        ...settings,
                        epub_layout: e.target.value as ConversionSettings["epub_layout"],
                      })
                    }
                    className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600 font-bangla"
                  >
                    <option value="reflowable">{t.epubReflowable}</option>
                    <option value="fixed">{t.epubFixed}</option>
                  </select>
                </div>
              )}

              {/* OCR Accuracy */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5 font-bangla">
                  {t.accuracyLabel}
                </label>
                <select
                  value={settings.ocr_accuracy}
                  onChange={(e) =>
                    onChangeSettings({
                      ...settings,
                      ocr_accuracy: e.target.value as ConversionSettings["ocr_accuracy"],
                    })
                  }
                  className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600 font-bangla"
                >
                  <option value="high">{t.accHigh}</option>
                  <option value="standard">{t.accStd}</option>
                </select>
              </div>

              {/* Bangla Font Selector */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5 font-bangla">
                  {t.fontLabel}
                </label>
                <select
                  value={settings.bangla_font}
                  onChange={(e) =>
                    onChangeSettings({
                      ...settings,
                      bangla_font: e.target.value as ConversionSettings["bangla_font"],
                    })
                  }
                  className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600"
                >
                  <option value="hind_siliguri">Hind Siliguri (SIL OFL — Modern Sans)</option>
                  <option value="noto_sans_bengali">Noto Sans Bengali (SIL OFL — Clean Print)</option>
                  <option value="noto_serif_bengali">Noto Serif Bengali (SIL OFL — Book Serif)</option>
                  <option value="kalpurush">Kalpurush (Classic Bengali Typography)</option>
                </select>
              </div>

              {/* Metadata Inputs */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1 font-bangla">
                    {t.docTitleLabel}
                  </label>
                  <input
                    type="text"
                    value={settings.doc_title}
                    placeholder={uploadInfo.title || uploadInfo.filename.replace(/\.pdf$/i, "")}
                    onChange={(e) =>
                      onChangeSettings({ ...settings, doc_title: e.target.value })
                    }
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-xs font-bangla"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1 font-bangla">
                    {t.docAuthorLabel}
                  </label>
                  <input
                    type="text"
                    value={settings.doc_author}
                    placeholder={uploadInfo.author || "Optional"}
                    onChange={(e) =>
                      onChangeSettings({ ...settings, doc_author: e.target.value })
                    }
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-xs font-bangla"
                  />
                </div>
              </div>

              {/* Preservation Toggles */}
              <div className="space-y-2.5 pt-1 border-t border-slate-100">
                {(
                  [
                    ["preserve_layout", t.preserveLayoutToggle],
                    ["preserve_images", t.preserveImagesToggle],
                    ["preserve_tables", t.preserveTablesToggle],
                    ["embed_fonts", t.embedFontsToggle],
                  ] as const
                ).map(([key, label]) => (
                  <label
                    key={key}
                    className="flex items-center justify-between gap-3 py-1 cursor-pointer select-none"
                  >
                    <span className="text-xs font-medium text-slate-700 font-bangla">{label}</span>
                    <input
                      type="checkbox"
                      checked={settings[key]}
                      onChange={(e) =>
                        onChangeSettings({ ...settings, [key]: e.target.checked })
                      }
                      className="w-4 h-4 accent-emerald-700 rounded cursor-pointer"
                    />
                  </label>
                ))}
              </div>

              <button
                type="button"
                onClick={onStartConversion}
                className="w-full py-3.5 px-5 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white font-bold text-sm shadow-md flex items-center justify-center gap-2 transition cursor-pointer font-bangla"
              >
                <Wand2 className="w-4 h-4" />
                <span>{t.startConvertBtn}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
