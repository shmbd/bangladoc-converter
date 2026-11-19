"use client";

import React from "react";
import {
  CheckCircle2,
  Clock,
  Download,
  Eye,
  FileText,
  Loader2,
  Trash2,
  XCircle,
} from "lucide-react";
import { TRANSLATIONS } from "@/lib/i18n";
import { JobStatusResponse, UILang } from "@/lib/types";

interface HistoryPanelProps {
  lang: UILang;
  jobs: JobStatusResponse[];
  activeJobId: string | null;
  onSelectJobForPreview: (job: JobStatusResponse) => void;
  onSelectJobForDownload: (job: JobStatusResponse) => void;
  onDeleteJob: (jobId: string) => void;
}

export default function HistoryPanel({
  lang,
  jobs,
  activeJobId,
  onSelectJobForPreview,
  onSelectJobForDownload,
  onDeleteJob,
}: HistoryPanelProps) {
  const t = TRANSLATIONS[lang];

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-slate-900 font-bangla">{t.histHeading}</h2>
        <span className="text-xs text-slate-500">{jobs.length} record(s)</span>
      </div>

      {jobs.length === 0 ? (
        <div className="rounded-2xl bg-white border border-slate-200 p-12 text-center text-slate-500 text-sm font-bangla">
          {t.histEmpty}
        </div>
      ) : (
        <div className="space-y-3">
          {jobs.map((j) => {
            const isActive = j.job_id === activeJobId;
            return (
              <div
                key={j.job_id}
                className={`rounded-2xl bg-white border p-5 shadow-xs flex flex-wrap items-center justify-between gap-4 transition ${
                  isActive ? "border-emerald-600 ring-2 ring-emerald-600/15" : "border-slate-200"
                }`}
              >
                <div className="flex items-start gap-3.5 min-w-0">
                  <div className="w-10 h-10 rounded-xl bg-slate-100 text-slate-700 flex items-center justify-center shrink-0">
                    <FileText className="w-5 h-5" />
                  </div>
                  <div className="min-w-0 space-y-1">
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-bold text-slate-900 truncate font-bangla">
                        {j.filename}
                      </h3>
                      {j.status === "completed" && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-100 text-emerald-800">
                          <CheckCircle2 className="w-3 h-3" /> Completed
                        </span>
                      )}
                      {(j.status === "processing" || j.status === "queued") && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-100 text-amber-800">
                          <Loader2 className="w-3 h-3 animate-spin" /> {Math.round(j.progress_pct)}%
                        </span>
                      )}
                      {(j.status === "failed" || j.status === "cancelled") && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-red-100 text-red-800">
                          <XCircle className="w-3 h-3" /> {j.status}
                        </span>
                      )}
                    </div>
                    <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
                      <span className="inline-flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5" />
                        {new Date(j.created_at).toLocaleString()}
                      </span>
                      <span>•</span>
                      <span>{j.total_pages} page(s)</span>
                      {j.qa_report && (
                        <>
                          <span>•</span>
                          <span className="text-emerald-700 font-semibold">
                            OCR {j.qa_report.mean_ocr_confidence}% | {j.qa_report.juktakkhor_count} Juktakkhors
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {j.status === "completed" && (
                    <>
                      <button
                        type="button"
                        onClick={() => onSelectJobForPreview(j)}
                        className="px-3.5 py-2 rounded-xl border border-slate-200 hover:bg-slate-100 text-xs font-semibold text-slate-800 flex items-center gap-1.5 cursor-pointer font-bangla"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        <span>{t.navPreview}</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => onSelectJobForDownload(j)}
                        className="px-3.5 py-2 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-semibold flex items-center gap-1.5 cursor-pointer font-bangla"
                      >
                        <Download className="w-3.5 h-3.5" />
                        <span>{t.navDownload}</span>
                      </button>
                    </>
                  )}
                  <button
                    type="button"
                    onClick={() => onDeleteJob(j.job_id)}
                    title="Delete job & purge files immediately"
                    className="p-2 rounded-xl border border-slate-200 hover:bg-red-50 hover:border-red-200 text-slate-500 hover:text-red-600 transition cursor-pointer"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
