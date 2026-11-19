"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Check,
  ChevronLeft,
  ChevronRight,
  Copy,
  Download,
  Edit3,
  Eye,
  FileText,
  Loader2,
  RefreshCw,
  Save,
  Sparkles,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { apiUrl, fetchJobOcrStructure, submitManualEdits } from "@/lib/api";
import { TRANSLATIONS } from "@/lib/i18n";
import {
  JobStatusResponse,
  LineEditItem,
  PageOCRResult,
  UILang,
} from "@/lib/types";

interface PreviewCompareStudioProps {
  lang: UILang;
  job: JobStatusResponse | null;
  onJobUpdated: (updated: JobStatusResponse) => void;
  onGoDownload: () => void;
  onGoHome: () => void;
}

export default function PreviewCompareStudio({
  lang,
  job,
  onJobUpdated,
  onGoDownload,
  onGoHome,
}: PreviewCompareStudioProps) {
  const t = TRANSLATIONS[lang];
  const [ocrPages, setOcrPages] = useState<PageOCRResult[]>([]);
  const [loadingOcr, setLoadingOcr] = useState(false);
  const [pageIdx, setPageIdx] = useState(1); // 1-indexed output page
  const [zoom, setZoom] = useState(100);
  const [showOverlayBoxes, setShowOverlayBoxes] = useState(true);
  const [rightTab, setRightTab] = useState<"pdf" | "native_pdf" | "ocr" | "diff">("pdf");
  const [pdfVariant, setPdfVariant] = useState<"searchable_pdf" | "layout_pdf" | "editable_pdf">(
    "searchable_pdf"
  );
  const [lowConfOnly, setLowConfOnly] = useState(false);
  const [focusedLineId, setFocusedLineId] = useState<string | null>(null);
  const [draftEdits, setDraftEdits] = useState<Record<string, string>>({});
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [copiedPage, setCopiedPage] = useState(false);
  const [renderRev, setRenderRev] = useState(1);

  useEffect(() => {
    if (!job || job.status !== "completed") return;
    let active = true;
    setLoadingOcr(true);
    fetchJobOcrStructure(job.job_id)
      .then((pages) => {
        if (!active) return;
        setOcrPages(pages);
        setPageIdx(1);
        setDraftEdits({});
      })
      .catch(() => {})
      .finally(() => {
        if (active) setLoadingOcr(false);
      });
    return () => {
      active = false;
    };
  }, [job?.job_id, job?.status]);

  const currentPageOcr: PageOCRResult | undefined = useMemo(
    () => ocrPages.find((p) => p.output_page_index === pageIdx) || ocrPages[0],
    [ocrPages, pageIdx]
  );

  if (!job || job.status !== "completed") {
    return (
      <div className="rounded-2xl bg-white border border-slate-200 p-12 text-center space-y-4">
        <p className="text-slate-600 font-bangla">{t.noJobSelected}</p>
        <button
          type="button"
          onClick={onGoHome}
          className="px-5 py-2.5 rounded-xl bg-emerald-700 text-white text-sm font-semibold cursor-pointer"
        >
          {t.navHome}
        </button>
      </div>
    );
  }

  const totalPages = ocrPages.length || job.total_pages || 1;
  const pendingEditCount = Object.keys(draftEdits).length;

  const handleLineChange = (sourcePageNum: number, lineId: string, val: string) => {
    setDraftEdits((prev) => ({
      ...prev,
      [`${sourcePageNum}::${lineId}`]: val,
    }));
    setSaveSuccess(false);
  };

  const getLineCurrentValue = (sourcePageNum: number, lineId: string, original: string) => {
    const key = `${sourcePageNum}::${lineId}`;
    return key in draftEdits ? draftEdits[key] : original;
  };

  const handleSaveCorrections = async () => {
    const items: LineEditItem[] = Object.entries(draftEdits).map(([composite, newText]) => {
      const [pStr, lineId] = composite.split("::");
      return {
        page_number: Number(pStr),
        line_id: lineId,
        new_text: newText,
      };
    });
    if (items.length === 0) return;

    setIsSaving(true);
    setSaveSuccess(false);
    try {
      const updatedJob = await submitManualEdits(job.job_id, items);
      const refreshedOcr = await fetchJobOcrStructure(job.job_id);
      setOcrPages(refreshedOcr);
      setDraftEdits({});
      setRenderRev((r) => r + 1);
      setSaveSuccess(true);
      onJobUpdated(updatedJob);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to save edits");
    } finally {
      setIsSaving(false);
    }
  };

  const handleCopyCurrentPageText = async () => {
    if (!currentPageOcr) return;
    const parts: string[] = [];
    for (const blk of currentPageOcr.blocks) {
      parts.push(
        blk.lines
          .map((ln) => getLineCurrentValue(currentPageOcr.page_number, ln.id, ln.text))
          .join("\n")
      );
    }
    for (const tbl of currentPageOcr.tables) {
      const rows: string[][] = Array.from({ length: tbl.rows }, () =>
        Array(tbl.cols).fill("")
      );
      for (const c of tbl.cells) {
        if (rows[c.row]) {
          rows[c.row][c.col] = getLineCurrentValue(
            currentPageOcr.page_number,
            `${tbl.id}_r${c.row}_c${c.col}`,
            c.text
          );
        }
      }
      parts.push(rows.map((r) => r.join("\t")).join("\n"));
    }
    await navigator.clipboard.writeText(parts.join("\n\n"));
    setCopiedPage(true);
    setTimeout(() => setCopiedPage(false), 2200);
  };

  const sourceImgUrl = apiUrl(
    `/api/jobs/${job.job_id}/pages/${pageIdx}/render/source?dpi=160&rev=${renderRev}`
  );
  const convertedImgUrl = apiUrl(
    `/api/jobs/${job.job_id}/pages/${pageIdx}/render/${pdfVariant}?dpi=160&rev=${renderRev}`
  );
  const diffImgUrl = apiUrl(
    `/api/jobs/${job.job_id}/pages/${pageIdx}/render/diff?rev=${renderRev}`
  );
  const nativePdfEmbedUrl = apiUrl(
    `/api/jobs/${job.job_id}/preview/${pdfVariant}?rev=${renderRev}#page=${pageIdx}`
  );

  return (
    <div className="space-y-5">
      {/* Top Toolbar */}
      <div className="rounded-2xl bg-white border border-slate-200 p-4 shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div>
            <h2 className="text-base font-bold text-slate-900 font-bangla">{t.prevHeading}</h2>
            <p className="text-xs text-slate-500 font-bangla">
              {job.filename} •{" "}
              {currentPageOcr
                ? `OCR Confidence: ${currentPageOcr.mean_confidence}% | Low-Conf Words: ${currentPageOcr.low_confidence_word_count}`
                : ""}
            </p>
          </div>
        </div>

        {/* Page Navigator & Zoom Controls */}
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="inline-flex items-center rounded-xl border border-slate-200 bg-slate-50 p-1">
            <button
              type="button"
              disabled={pageIdx <= 1}
              onClick={() => setPageIdx((p) => Math.max(1, p - 1))}
              className="p-1.5 rounded-lg hover:bg-white disabled:opacity-40 cursor-pointer"
              title="Previous Page"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-3 text-xs font-bold text-slate-800">
              Page {pageIdx} / {totalPages}
            </span>
            <button
              type="button"
              disabled={pageIdx >= totalPages}
              onClick={() => setPageIdx((p) => Math.min(totalPages, p + 1))}
              className="p-1.5 rounded-lg hover:bg-white disabled:opacity-40 cursor-pointer"
              title="Next Page"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          <div className="inline-flex items-center rounded-xl border border-slate-200 bg-slate-50 p-1">
            <button
              type="button"
              onClick={() => setZoom((z) => Math.max(60, z - 15))}
              className="p-1.5 rounded-lg hover:bg-white cursor-pointer"
              title="Zoom Out"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <span className="px-2.5 text-xs font-mono font-semibold text-slate-700">{zoom}%</span>
            <button
              type="button"
              onClick={() => setZoom((z) => Math.min(200, z + 15))}
              className="p-1.5 rounded-lg hover:bg-white cursor-pointer"
              title="Zoom In"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
          </div>

          <button
            type="button"
            onClick={handleCopyCurrentPageText}
            className="px-3 py-2 rounded-xl border border-slate-200 hover:bg-slate-100 text-xs font-semibold text-slate-700 flex items-center gap-1.5 cursor-pointer font-bangla"
          >
            {copiedPage ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copiedPage ? "Copied Unicode!" : "Copy Page Unicode"}</span>
          </button>

          <button
            type="button"
            onClick={onGoDownload}
            className="px-4 py-2 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-semibold flex items-center gap-1.5 shadow-sm cursor-pointer font-bangla"
          >
            <Download className="w-3.5 h-3.5" />
            <span>{t.navDownload}</span>
          </button>
        </div>
      </div>

      {/* Pending Edits Save Bar */}
      {(pendingEditCount > 0 || saveSuccess) && (
        <div
          className={`rounded-xl border p-3.5 flex flex-wrap items-center justify-between gap-3 ${
            saveSuccess
              ? "bg-emerald-50 border-emerald-200 text-emerald-900"
              : "bg-amber-50 border-amber-300 text-amber-950"
          }`}
        >
          <div className="flex items-center gap-2 text-xs font-semibold font-bangla">
            {saveSuccess ? (
              <>
                <Check className="w-4 h-4 text-emerald-600" />
                <span>
                  All manual Bangla/English corrections saved! Searchable PDF, Editable PDF, Layout PDF, EPUB 3 & DOCX have been updated.
                </span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 text-amber-600" />
                <span>
                  {pendingEditCount} line/cell correction(s) staged. Click Save to rebuild all downloadable documents while preserving original layout coordinates.
                </span>
              </>
            )}
          </div>
          {pendingEditCount > 0 && (
            <button
              type="button"
              disabled={isSaving}
              onClick={handleSaveCorrections}
              className="px-4 py-2 rounded-lg bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-bold flex items-center gap-1.5 shadow-sm cursor-pointer disabled:opacity-60 font-bangla"
            >
              {isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
              <span>{isSaving ? t.savingEdits : t.saveEditsBtn}</span>
            </button>
          )}
        </div>
      )}

      {/* Dual Side-by-Side Comparison Panels */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        {/* LEFT PANEL: Original Source PDF + Interactive OCR Region Overlay */}
        <div className="rounded-2xl bg-white border border-slate-200 shadow-sm flex flex-col overflow-hidden">
          <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs font-bold text-slate-800 flex items-center gap-1.5 font-bangla">
              <Eye className="w-4 h-4 text-slate-600" />
              <span>{t.leftOriginal}</span>
            </span>

            <label className="flex items-center gap-2 text-xs text-slate-600 cursor-pointer select-none font-bangla">
              <input
                type="checkbox"
                checked={showOverlayBoxes}
                onChange={(e) => setShowOverlayBoxes(e.target.checked)}
                className="accent-emerald-700 rounded"
              />
              <span>{t.showBoxes}</span>
            </label>
          </div>

          <div className="p-4 bg-slate-100/80 overflow-auto max-h-[760px] flex justify-center">
            <div
              className="relative bg-white shadow-md border border-slate-300 transition-all origin-top"
              style={{ width: `${(595 * zoom) / 100}px` }}
            >
              <img
                src={sourceImgUrl}
                alt={`Original Page ${pageIdx}`}
                className="w-full h-auto block select-none"
              />

              {/* Interactive Bounding Box Overlay */}
              {showOverlayBoxes && currentPageOcr && (
                <div className="absolute inset-0 pointer-events-none">
                  {currentPageOcr.blocks.flatMap((blk) =>
                    blk.lines.map((ln) => {
                      const leftPct = (ln.bbox[0] / currentPageOcr.width_pt) * 100;
                      const topPct = (ln.bbox[1] / currentPageOcr.height_pt) * 100;
                      const widthPct = ((ln.bbox[2] - ln.bbox[0]) / currentPageOcr.width_pt) * 100;
                      const heightPct = ((ln.bbox[3] - ln.bbox[1]) / currentPageOcr.height_pt) * 100;
                      const isLow = ln.confidence < 75;
                      const isFocused = focusedLineId === ln.id;

                      return (
                        <button
                          key={ln.id}
                          type="button"
                          title={`Confidence: ${ln.confidence}% — Click to edit: ${ln.text}`}
                          onClick={() => {
                            setFocusedLineId(ln.id);
                            setRightTab("ocr");
                          }}
                          style={{
                            left: `${leftPct}%`,
                            top: `${topPct}%`,
                            width: `${widthPct}%`,
                            height: `${heightPct}%`,
                          }}
                          className={`absolute pointer-events-auto cursor-pointer rounded-[2px] transition ${
                            isFocused
                              ? "border-2 border-blue-600 bg-blue-500/20 z-10"
                              : isLow
                              ? "border border-amber-500 bg-amber-400/20 hover:bg-amber-400/35"
                              : "border border-emerald-500/45 hover:border-emerald-600 hover:bg-emerald-500/15"
                          }`}
                        />
                      );
                    })
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* RIGHT PANEL: Converted Selectable PDF / Native PDF / Interactive OCR Editor / Visual Diff */}
        <div className="rounded-2xl bg-white border border-slate-200 shadow-sm flex flex-col overflow-hidden">
          <div className="px-4 py-2.5 bg-slate-50 border-b border-slate-200 flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-1">
              <button
                type="button"
                onClick={() => setRightTab("pdf")}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer font-bangla ${
                  rightTab === "pdf"
                    ? "bg-emerald-700 text-white shadow-xs"
                    : "text-slate-600 hover:bg-slate-200/70"
                }`}
              >
                {t.tabPdfView}
              </button>
              <button
                type="button"
                onClick={() => setRightTab("native_pdf")}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer ${
                  rightTab === "native_pdf"
                    ? "bg-emerald-700 text-white shadow-xs"
                    : "text-slate-600 hover:bg-slate-200/70"
                }`}
              >
                Native PDF Reader
              </button>
              <button
                type="button"
                onClick={() => setRightTab("ocr")}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer flex items-center gap-1 font-bangla ${
                  rightTab === "ocr"
                    ? "bg-emerald-700 text-white shadow-xs"
                    : "text-slate-600 hover:bg-slate-200/70"
                }`}
              >
                <Edit3 className="w-3.5 h-3.5" />
                <span>{t.tabOcrEdit}</span>
              </button>
              <button
                type="button"
                onClick={() => setRightTab("diff")}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer font-bangla ${
                  rightTab === "diff"
                    ? "bg-emerald-700 text-white shadow-xs"
                    : "text-slate-600 hover:bg-slate-200/70"
                }`}
              >
                {t.tabVisualDiff}
              </button>
            </div>

            {(rightTab === "pdf" || rightTab === "native_pdf") && (
              <select
                value={pdfVariant}
                onChange={(e) =>
                  setPdfVariant(
                    e.target.value as "searchable_pdf" | "layout_pdf" | "editable_pdf"
                  )
                }
                className="rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-semibold text-slate-700"
              >
                <option value="searchable_pdf">Searchable PDF (Original Visual)</option>
                <option value="layout_pdf">Layout-Preserved Hybrid PDF</option>
                <option value="editable_pdf">Editable Vector PDF</option>
              </select>
            )}
          </div>

          {/* Right Tab Content */}
          {rightTab === "pdf" && (
            <div className="p-4 bg-slate-100/80 overflow-auto max-h-[760px] flex justify-center">
              <div
                className="relative bg-white shadow-md border border-slate-300"
                style={{ width: `${(595 * zoom) / 100}px` }}
              >
                <img
                  src={convertedImgUrl}
                  alt={`Converted Page ${pageIdx}`}
                  className="w-full h-auto block select-none"
                />
                {/* Live Selectable & Copyable Unicode Text Layer right over the converted page! */}
                {currentPageOcr && (
                  <div className="absolute inset-0">
                    {currentPageOcr.blocks.flatMap((blk) =>
                      blk.lines.map((ln) => {
                        const leftPct = (ln.bbox[0] / currentPageOcr.width_pt) * 100;
                        const topPct = (ln.bbox[1] / currentPageOcr.height_pt) * 100;
                        const widthPct =
                          ((ln.bbox[2] - ln.bbox[0]) / currentPageOcr.width_pt) * 100;
                        const heightPct =
                          ((ln.bbox[3] - ln.bbox[1]) / currentPageOcr.height_pt) * 100;
                        const txt = getLineCurrentValue(
                          currentPageOcr.page_number,
                          ln.id,
                          ln.text
                        );
                        return (
                          <span
                            key={ln.id}
                            style={{
                              left: `${leftPct}%`,
                              top: `${topPct}%`,
                              width: `${widthPct}%`,
                              height: `${heightPct}%`,
                              fontSize: `${Math.max(9, (ln.font_size_pt * zoom) / 108)}px`,
                              lineHeight: 1.05,
                            }}
                            className="absolute text-transparent selection:bg-emerald-500/35 selection:text-emerald-950 cursor-text whitespace-nowrap overflow-hidden font-bangla"
                          >
                            {txt}
                          </span>
                        );
                      })
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {rightTab === "native_pdf" && (
            <div className="bg-slate-200 h-[740px]">
              <iframe
                key={`${pdfVariant}-${pageIdx}-${renderRev}`}
                src={nativePdfEmbedUrl}
                title="Converted Native PDF Viewer"
                className="w-full h-full border-0"
              />
            </div>
          )}

          {rightTab === "diff" && (
            <div className="p-4 bg-slate-100/80 overflow-auto max-h-[760px] space-y-3">
              <div className="rounded-xl bg-white border border-slate-200 p-3 text-xs text-slate-600 flex items-center justify-between">
                <span>
                  Blue = Identical to Original Scan • Red/Yellow = Reconstructed Typography Difference
                </span>
                {currentPageOcr && (
                  <strong className="text-emerald-700">
                    Similarity: {currentPageOcr.layout_similarity_score}%
                  </strong>
                )}
              </div>
              <div className="flex justify-center">
                <img
                  src={diffImgUrl}
                  alt="Layout Similarity Diff"
                  style={{ width: `${(520 * zoom) / 100}px` }}
                  className="rounded-lg shadow border border-slate-300"
                />
              </div>
            </div>
          )}

          {rightTab === "ocr" && (
            <div className="p-4 overflow-y-auto max-h-[760px] space-y-4">
              {loadingOcr ? (
                <div className="py-16 flex justify-center">
                  <Loader2 className="w-7 h-7 text-emerald-600 animate-spin" />
                </div>
              ) : !currentPageOcr ? (
                <p className="text-sm text-slate-500 text-center py-10">No OCR blocks available.</p>
              ) : (
                <>
                  <div className="flex items-center justify-between gap-2 pb-2 border-b border-slate-100">
                    <span className="text-xs font-semibold text-slate-600">
                      Click any line or table cell to refine Bangla/English Unicode text:
                    </span>
                    <label className="flex items-center gap-1.5 text-xs font-semibold text-amber-800 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={lowConfOnly}
                        onChange={(e) => setLowConfOnly(e.target.checked)}
                        className="accent-amber-600"
                      />
                      <span>{t.lowConfFilter}</span>
                    </label>
                  </div>

                  {/* Blocks & Lines */}
                  <div className="space-y-3">
                    {currentPageOcr.blocks.map((blk) => {
                      const visibleLines = lowConfOnly
                        ? blk.lines.filter((l) => l.confidence < 75)
                        : blk.lines;
                      if (visibleLines.length === 0) return null;

                      return (
                        <div
                          key={blk.id}
                          className="rounded-xl border border-slate-200 bg-slate-50/60 p-3 space-y-2"
                        >
                          <div className="flex items-center justify-between text-[11px]">
                            <span className="uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-slate-200 text-slate-700">
                              {blk.role}
                            </span>
                            <span className="text-slate-400 font-mono">
                              align: {blk.alignment}
                            </span>
                          </div>

                          {visibleLines.map((ln) => {
                            const val = getLineCurrentValue(
                              currentPageOcr.page_number,
                              ln.id,
                              ln.text
                            );
                            const isEdited =
                              `${currentPageOcr.page_number}::${ln.id}` in draftEdits;
                            const isLow = ln.confidence < 75;
                            const isFocused = focusedLineId === ln.id;

                            return (
                              <div
                                key={ln.id}
                                className={`rounded-lg p-2 border transition ${
                                  isFocused
                                    ? "border-blue-500 bg-blue-50/40 ring-2 ring-blue-500/20"
                                    : isEdited
                                    ? "border-emerald-500 bg-emerald-50/40"
                                    : isLow
                                    ? "border-amber-300 bg-amber-50/50"
                                    : "border-slate-200 bg-white"
                                }`}
                              >
                                <div className="flex items-center justify-between text-[11px] mb-1">
                                  <span className="text-slate-400 font-mono">
                                    {ln.font_size_pt}pt
                                  </span>
                                  <span
                                    className={`px-1.5 py-0.5 rounded font-semibold ${
                                      isEdited
                                        ? "bg-emerald-100 text-emerald-800"
                                        : isLow
                                        ? "bg-amber-100 text-amber-800"
                                        : "bg-slate-100 text-slate-600"
                                    }`}
                                  >
                                    {isEdited
                                      ? "Edited (100%)"
                                      : `OCR ${ln.confidence}%`}
                                  </span>
                                </div>
                                <input
                                  type="text"
                                  value={val}
                                  onFocus={() => setFocusedLineId(ln.id)}
                                  onChange={(e) =>
                                    handleLineChange(
                                      currentPageOcr.page_number,
                                      ln.id,
                                      e.target.value
                                    )
                                  }
                                  className="w-full text-sm text-slate-900 bg-transparent focus:outline-none font-bangla"
                                />
                              </div>
                            );
                          })}
                        </div>
                      );
                    })}
                  </div>

                  {/* Detected Tables Editor */}
                  {currentPageOcr.tables.map((tbl) => (
                    <div
                      key={tbl.id}
                      className="rounded-xl border border-emerald-200 bg-emerald-50/20 p-3 space-y-2"
                    >
                      <div className="flex items-center justify-between text-xs font-bold text-emerald-900">
                        <span>
                          Reconstructed Table ({tbl.rows} × {tbl.cols})
                        </span>
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full border-collapse text-xs bg-white">
                          <tbody>
                            {Array.from({ length: tbl.rows }).map((_, rIdx) => (
                              <tr key={rIdx}>
                                {Array.from({ length: tbl.cols }).map((__, cIdx) => {
                                  const cell = tbl.cells.find(
                                    (c) => c.row === rIdx && c.col === cIdx
                                  );
                                  const cellId = `${tbl.id}_r${rIdx}_c${cIdx}`;
                                  const val = getLineCurrentValue(
                                    currentPageOcr.page_number,
                                    cellId,
                                    cell?.text || ""
                                  );
                                  return (
                                    <td
                                      key={cIdx}
                                      className="border border-slate-300 p-1.5"
                                    >
                                      <input
                                        type="text"
                                        value={val}
                                        onChange={(e) =>
                                          handleLineChange(
                                            currentPageOcr.page_number,
                                            cellId,
                                            e.target.value
                                          )
                                        }
                                        className={`w-full bg-transparent focus:outline-none font-bangla ${
                                          rIdx === 0 ? "font-bold" : ""
                                        }`}
                                      />
                                    </td>
                                  );
                                })}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ))}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
