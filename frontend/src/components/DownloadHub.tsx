"use client";

import React, { useState } from "react";
import {
  AlertTriangle,
  Archive,
  BookOpen,
  Check,
  CheckCircle2,
  Copy,
  Download,
  FileCheck2,
  FileCode2,
  FileSpreadsheet,
  FileText,
  Layers,
  ShieldCheck,
} from "lucide-react";
import { apiUrl } from "@/lib/api";
import { TRANSLATIONS } from "@/lib/i18n";
import { JobStatusResponse, UILang } from "@/lib/types";

interface DownloadHubProps {
  lang: UILang;
  job: JobStatusResponse | null;
  onGoPreview: () => void;
  onGoHome: () => void;
}

export default function DownloadHub({
  lang,
  job,
  onGoPreview,
  onGoHome,
}: DownloadHubProps) {
  const t = TRANSLATIONS[lang];
  const [copiedTxt, setCopiedTxt] = useState(false);

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

  const qa = job.qa_report;

  const handleCopyFullTxt = async () => {
    try {
      const res = await fetch(apiUrl(`/api/jobs/${job.job_id}/download/txt`), {
        cache: "no-store",
      });
      const txt = await res.text();
      await navigator.clipboard.writeText(txt);
      setCopiedTxt(true);
      setTimeout(() => setCopiedTxt(false), 2500);
    } catch {
      alert("Could not copy extracted text.");
    }
  };

  const formatCards = [
    {
      key: "searchable_pdf",
      badge: lang === "bn" ? "সর্বোচ্চ দৃশ্যমান সাদৃশ্য" : "Highest Visual Fidelity",
      title: "Searchable PDF",
      titleBn: "সার্চযোগ্য পিডিএফ (Searchable PDF)",
      desc: "100% untouched original page appearance with coordinate-aligned invisible NFC Unicode Bangla & English text layer for Ctrl+F and Copy-Paste.",
      descBn:
        "মূল স্ক্যান করা পৃষ্ঠার দৃশ্যমান রূপ ১০০% অপরিবর্তিত রেখে নিখুঁত ইউনিকোড বাংলা ও ইংরেজি টেক্সট লেয়ার যুক্ত করা হয়েছে (Ctrl+F ও কপি-পেস্ট সমর্থিত)।",
      icon: FileCheck2,
      accent: "border-emerald-300 bg-emerald-50/40",
      btnCls: "bg-emerald-700 hover:bg-emerald-800 text-white",
    },
    {
      key: "editable_pdf",
      badge: lang === "bn" ? "ভেক্টর বাংলা ফন্ট" : "Vector Typography",
      title: "Editable PDF",
      titleBn: "সম্পাদনাযোগ্য ভেক্টর পিডিএফ (Editable PDF)",
      desc: "Reconstructed digital PDF with HarfBuzz-shaped Bangla vector outlines, embedded fonts, vector table grids, cropped figures & Unicode layer.",
      descBn:
        "হার্ফবাজ (HarfBuzz) ভেক্টর বাংলা অক্ষর, এমবেডেড ফন্ট, ভেক্টর সারণি এবং সংরক্ষিত চিত্রসহ সম্পূর্ণ পুনর্গঠিত ডিজিটাল পিডিএফ।",
      icon: Layers,
      accent: "border-slate-200 bg-white",
      btnCls: "bg-slate-900 hover:bg-slate-800 text-white",
    },
    {
      key: "layout_pdf",
      badge: lang === "bn" ? "হাইব্রিড পুনর্গঠন" : "Hybrid Reconstruction",
      title: "Layout-Preserved PDF",
      titleBn: "লেআউট-সংরক্ষিত হাইব্রিড পিডিএফ",
      desc: "Preserves original borders, stamps, and graphics while surgically replacing scanned text with crisp vector Bangla characters in original ink colors.",
      descBn:
        "মূল বর্ডার, সিলমোহর ও গ্রাফিক্স অক্ষুণ্ণ রেখে স্ক্যান করা লেখার স্থানে মূল কালির রঙে স্পষ্ট ভেক্টর বাংলা অক্ষর প্রতিস্থাপিত পিডিএফ।",
      icon: FileSpreadsheet,
      accent: "border-slate-200 bg-white",
      btnCls: "bg-slate-900 hover:bg-slate-800 text-white",
    },
    {
      key: "epub",
      badge: `EPUB 3 (${job.settings.epub_layout})`,
      title: "EPUB 3 E-Book",
      titleBn: "ইপাব ৩ ই-বুক (EPUB 3)",
      desc: "Structured XHTML5 e-book with clickable Table of Contents, embedded SIL OFL Bangla font, chapters, tables, and preserved illustrations.",
      descBn:
        "ক্লিকযোগ্য সূচিপত্র (TOC), এমবেডেড ইউনিকোড বাংলা ফন্ট, অধ্যায়, সারণি ও চিত্রসহ মানসম্মত ইপাব ৩ ই-বুক।",
      icon: BookOpen,
      accent: "border-teal-200 bg-teal-50/30",
      btnCls: "bg-teal-700 hover:bg-teal-800 text-white",
    },
    {
      key: "docx",
      badge: "MS Word / Google Docs",
      title: "Editable Word (DOCX)",
      titleBn: "মাইক্রোসফট ওয়ার্ড (DOCX)",
      desc: "Structured DOCX with Complex-Script Bangla font tags, headings, editable Word tables, and embedded illustrations.",
      descBn:
        "মাইক্রোসফট ওয়ার্ড ও গুগল ডকসে সরাসরি সম্পাদনাযোগ্য ইউনিকোড বাংলা ফন্ট, শিরোনাম, সারণি ও চিত্রসহ ডকএক্স ফাইল।",
      icon: FileText,
      accent: "border-slate-200 bg-white",
      btnCls: "bg-slate-800 hover:bg-slate-900 text-white",
    },
    {
      key: "txt",
      badge: "UTF-8 NFC Plain Text",
      title: "Extracted Bangla TXT",
      titleBn: "ইউনিকোড বাংলা টেক্সট (TXT)",
      desc: "Clean NFC-normalized Unicode Bangla & English plain text organized page by page, ready for NLP or text editors.",
      descBn:
        "পৃষ্ঠাভিত্তিক সাজানো বিশুদ্ধ ইউনিকোড (UTF-8 NFC) বাংলা ও ইংরেজি প্লেইন টেক্সট ফাইল।",
      icon: FileCode2,
      accent: "border-slate-200 bg-white",
      btnCls: "bg-slate-800 hover:bg-slate-900 text-white",
    },
  ];

  return (
    <div className="space-y-7">
      {/* Header + ZIP Bundle Banner */}
      <div className="rounded-2xl bg-gradient-to-r from-emerald-900 via-emerald-800 to-slate-900 text-white p-6 md:p-8 shadow-md flex flex-wrap items-center justify-between gap-6">
        <div className="space-y-1.5 max-w-2xl">
          <span className="text-xs uppercase tracking-wider font-semibold text-emerald-300">
            {job.filename}
          </span>
          <h2 className="text-2xl font-bold font-bangla">{t.dlHeading}</h2>
          <p className="text-sm text-emerald-100/85 font-bangla">{t.dlZipDesc}</p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={handleCopyFullTxt}
            className="px-4 py-3 rounded-xl bg-white/10 hover:bg-white/20 border border-white/20 text-white text-xs font-semibold flex items-center gap-2 transition cursor-pointer font-bangla"
          >
            {copiedTxt ? <Check className="w-4 h-4 text-emerald-300" /> : <Copy className="w-4 h-4" />}
            <span>{copiedTxt ? t.copiedToast : t.copyAllUnicode}</span>
          </button>

          <a
            href={apiUrl(`/api/jobs/${job.job_id}/download/zip`)}
            className="px-5 py-3 rounded-xl bg-emerald-400 hover:bg-emerald-300 text-slate-950 font-bold text-sm shadow flex items-center gap-2 transition font-bangla"
          >
            <Archive className="w-4 h-4" />
            <span>{t.dlZipTitle}</span>
          </a>
        </div>
      </div>

      {/* Individual Format Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {formatCards.map((card) => {
          const Icon = card.icon;
          return (
            <div
              key={card.key}
              className={`rounded-2xl border p-5 shadow-xs flex flex-col justify-between space-y-4 ${card.accent}`}
            >
              <div className="space-y-2.5">
                <div className="flex items-center justify-between">
                  <div className="w-10 h-10 rounded-xl bg-emerald-700/10 text-emerald-800 flex items-center justify-center">
                    <Icon className="w-5 h-5" />
                  </div>
                  <span className="text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-slate-900/5 text-slate-700 border border-slate-200">
                    {card.badge}
                  </span>
                </div>
                <h3 className="text-base font-bold text-slate-900 font-bangla">
                  {lang === "bn" ? card.titleBn : card.title}
                </h3>
                <p className="text-xs text-slate-600 leading-relaxed font-bangla">
                  {lang === "bn" ? card.descBn : card.desc}
                </p>
              </div>

              <a
                href={apiUrl(`/api/jobs/${job.job_id}/download/${card.key}`)}
                className={`w-full py-2.5 px-4 rounded-xl text-xs font-bold flex items-center justify-center gap-2 transition font-bangla ${card.btnCls}`}
              >
                <Download className="w-3.5 h-3.5" />
                <span>
                  {lang === "bn" ? `${card.titleBn} ডাউনলোড করুন` : `Download ${card.title}`}
                </span>
              </a>
            </div>
          );
        })}
      </div>

      {/* Quality Assurance Evaluation Scorecard */}
      {qa && (
        <div className="rounded-2xl bg-white border border-slate-200 p-6 shadow-sm space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
            <div className="flex items-center gap-2.5">
              <ShieldCheck className="w-6 h-6 text-emerald-600" />
              <h3 className="text-lg font-bold text-slate-900 font-bangla">{t.qaTitle}</h3>
            </div>
            <button
              type="button"
              onClick={onGoPreview}
              className="text-xs font-semibold text-emerald-700 hover:underline cursor-pointer"
            >
              Need manual OCR refinements? Open Side-by-Side Editor →
            </button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-4">
            <div className="rounded-xl bg-slate-50 border border-slate-200 p-3.5">
              <div className="text-[11px] text-slate-500 font-medium">Mean OCR Confidence</div>
              <div className="text-xl font-bold text-emerald-700 mt-0.5">
                {qa.mean_ocr_confidence}%
              </div>
            </div>
            <div className="rounded-xl bg-slate-50 border border-slate-200 p-3.5">
              <div className="text-[11px] text-slate-500 font-medium">Searchable Visual Match</div>
              <div className="text-xl font-bold text-emerald-700 mt-0.5">
                {qa.searchable_layout_similarity_pct}%
              </div>
            </div>
            <div className="rounded-xl bg-slate-50 border border-slate-200 p-3.5">
              <div className="text-[11px] text-slate-500 font-medium">Bangla Characters</div>
              <div className="text-xl font-bold text-slate-900 mt-0.5">
                {qa.bangla_char_count.toLocaleString()}
              </div>
            </div>
            <div className="rounded-xl bg-slate-50 border border-slate-200 p-3.5">
              <div className="text-[11px] text-slate-500 font-medium">Juktakkhors Preserved</div>
              <div className="text-xl font-bold text-slate-900 mt-0.5">
                {qa.juktakkhor_count}
              </div>
            </div>
            <div className="rounded-xl bg-slate-50 border border-slate-200 p-3.5">
              <div className="text-[11px] text-slate-500 font-medium">Bangla Numerals (০-৯)</div>
              <div className="text-xl font-bold text-slate-900 mt-0.5">
                {qa.bangla_numeral_count}
              </div>
            </div>
            <div className="rounded-xl bg-slate-50 border border-slate-200 p-3.5">
              <div className="text-[11px] text-slate-500 font-medium">Tables / Figures</div>
              <div className="text-xl font-bold text-slate-900 mt-0.5">
                {qa.tables_preserved} / {qa.images_preserved}
              </div>
            </div>
          </div>

          {/* Integrity Checklist */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
            {[
              ["Unicode NFC Integrity", qa.unicode_integrity_passed],
              ["Selectable & Copyable Text Layer", qa.selectable_text_verified],
              ["Logical Character Order (Kar/Fola)", qa.character_order_valid],
              [
                `Page Count Consistency (${qa.converted_page_count}/${qa.source_selected_pages})`,
                qa.page_count_consistent,
              ],
            ].map(([label, ok]) => (
              <div
                key={String(label)}
                className={`rounded-xl border p-3 flex items-center gap-2 font-semibold ${
                  ok
                    ? "bg-emerald-50/50 border-emerald-200 text-emerald-900"
                    : "bg-amber-50 border-amber-200 text-amber-900"
                }`}
              >
                {ok ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                ) : (
                  <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                )}
                <span>{String(label)}</span>
              </div>
            ))}
          </div>

          {/* Warnings / Advisories */}
          {qa.warnings.length > 0 && (
            <div className="rounded-xl bg-amber-50 border border-amber-200 p-4 space-y-1.5">
              {qa.warnings.map((w, idx) => (
                <div key={idx} className="flex items-start gap-2 text-xs text-amber-900">
                  <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                  <span>{w}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
