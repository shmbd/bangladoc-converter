"use client";

import React from "react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Download,
  FileSearch,
  Loader2,
  XCircle,
} from "lucide-react";
import { TRANSLATIONS } from "@/lib/i18n";
import { JobStatusResponse, UILang } from "@/lib/types";

interface ProcessingViewProps {
  lang: UILang;
  job: JobStatusResponse | null;
  onCancel: () => void;
  onGoPreview: () => void;
  onGoDownload: () => void;
  onGoHome: () => void;
}

const PIPELINE_STEPS = [
  { threshold: 2, en: "PDF Layer & Encoding Analysis", bn: "পিডিএফ লেয়ার ও এনকোডিং বিশ্লেষণ" },
  { threshold: 15, en: "OpenCV Deskew & Bangla+English LSTM OCR", bn: "ইমেজ প্রিপ্রসেসিং ও বাংলা+ইংরেজি ওসিআর" },
  { threshold: 60, en: "Table Grid, Image & Typography Detection", bn: "সারণি, ছবি ও ফন্ট কাঠামো শনাক্তকরণ" },
  { threshold: 76, en: "HarfBuzz Vector PDF & EPUB 3 Synthesis", bn: "ভেক্টর পিডিএফ ও ইপাব ৩ পুনর্গঠন" },
  { threshold: 90, en: "Unicode Integrity & Visual QA Verification", bn: "ইউনিকোড অখণ্ডতা ও মান যাচাই" },
];

export default function ProcessingView({
  lang,
  job,
  onCancel,
  onGoPreview,
  onGoDownload,
  onGoHome,
}: ProcessingViewProps) {
  const t = TRANSLATIONS[lang];

  if (!job) {
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

  const isRunning = job.status === "queued" || job.status === "processing";
  const isDone = job.status === "completed";
  const isFailed = job.status === "failed" || job.status === "cancelled";

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="rounded-2xl bg-white border border-slate-200 p-8 shadow-sm space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <span className="text-xs font-bold uppercase tracking-wider text-emerald-700">
              Job #{job.job_id}
            </span>
            <h2 className="text-xl font-bold text-slate-900 font-bangla">{t.procHeading}</h2>
            <p className="text-sm text-slate-500 font-bangla">{job.filename}</p>
          </div>
          {isRunning && <Loader2 className="w-8 h-8 text-emerald-600 animate-spin shrink-0" />}
          {isDone && <CheckCircle2 className="w-8 h-8 text-emerald-600 shrink-0" />}
          {isFailed && <AlertTriangle className="w-8 h-8 text-red-600 shrink-0" />}
        </div>

        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs font-semibold">
            <span className="text-slate-700 font-bangla">
              {lang === "bn" && job.stage_bn ? job.stage_bn : job.stage}
            </span>
            <span className="text-emerald-700 font-mono">{Math.round(job.progress_pct)}%</span>
          </div>
          <div className="w-full h-3.5 rounded-full bg-slate-100 overflow-hidden border border-slate-200">
            <div
              className={`h-full transition-all duration-500 rounded-full ${
                isFailed
                  ? "bg-red-500"
                  : isDone
                  ? "bg-emerald-600"
                  : "bg-gradient-to-r from-emerald-600 to-teal-500"
              }`}
              style={{ width: `${Math.max(3, Math.min(100, job.progress_pct))}%` }}
            />
          </div>
          {job.total_pages > 0 && (
            <p className="text-xs text-slate-500 text-right">
              Page {job.current_page} of {job.total_pages}
            </p>
          )}
        </div>

        {/* Pipeline Stepper */}
        <div className="space-y-3 pt-2 border-t border-slate-100">
          {PIPELINE_STEPS.map((step, idx) => {
            const done = isDone || job.progress_pct >= (PIPELINE_STEPS[idx + 1]?.threshold ?? 100);
            const active = !done && job.progress_pct >= step.threshold && isRunning;
            return (
              <div
                key={idx}
                className={`flex items-center gap-3 p-3 rounded-xl border text-sm ${
                  done
                    ? "bg-emerald-50/60 border-emerald-200 text-emerald-950"
                    : active
                    ? "bg-amber-50/60 border-amber-200 text-slate-900 font-semibold"
                    : "bg-slate-50 border-slate-100 text-slate-400"
                }`}
              >
                {done ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                ) : active ? (
                  <Loader2 className="w-4 h-4 text-amber-600 animate-spin shrink-0" />
                ) : (
                  <div className="w-4 h-4 rounded-full border border-slate-300 shrink-0" />
                )}
                <span className="font-bangla">{lang === "bn" ? step.bn : step.en}</span>
              </div>
            );
          })}
        </div>

        {/* Error Box */}
        {job.error_message && (
          <div className="rounded-xl bg-red-50 border border-red-200 p-4 text-sm text-red-800">
            <strong>Error:</strong> {job.error_message}
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center justify-end gap-3 pt-2">
          {isRunning && (
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2.5 rounded-xl border border-red-200 text-red-700 hover:bg-red-50 text-xs font-semibold flex items-center gap-1.5 cursor-pointer"
            >
              <XCircle className="w-4 h-4" />
              <span>{t.procCancel}</span>
            </button>
          )}
          {isDone && (
            <>
              <button
                type="button"
                onClick={onGoDownload}
                className="px-5 py-2.5 rounded-xl border border-slate-300 hover:bg-slate-100 text-slate-800 text-sm font-semibold flex items-center gap-2 cursor-pointer font-bangla"
              >
                <Download className="w-4 h-4" />
                <span>{t.navDownload}</span>
              </button>
              <button
                type="button"
                onClick={onGoPreview}
                className="px-5 py-2.5 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-sm font-semibold flex items-center gap-2 shadow-sm cursor-pointer font-bangla"
              >
                <FileSearch className="w-4 h-4" />
                <span>{t.procViewResults}</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
