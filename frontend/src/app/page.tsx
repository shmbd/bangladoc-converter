"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  BookText,
  Clock,
  Download,
  Eye,
  FileUp,
  Globe,
  Loader2,
  Settings,
  ShieldCheck,
} from "lucide-react";
import DownloadHub from "@/components/DownloadHub";
import HistoryPanel from "@/components/HistoryPanel";
import PreviewCompareStudio from "@/components/PreviewCompareStudio";
import ProcessingView from "@/components/ProcessingView";
import SettingsPanel from "@/components/SettingsPanel";
import UploadWorkspace from "@/components/UploadWorkspace";
import {
  cancelJobRequest,
  deleteJobRequest,
  fetchJobsHistory,
  fetchJobStatus,
  fetchSystemSettings,
  loadSamplePdf,
  startConversionJob,
  uploadPdfFile,
} from "@/lib/api";
import { TRANSLATIONS } from "@/lib/i18n";
import {
  AppView,
  ConversionSettings,
  JobStatusResponse,
  SystemSettingsModel,
  UILang,
  UploadInspectResponse,
} from "@/lib/types";

const DEFAULT_CONVERSION_SETTINGS: ConversionSettings = {
  ocr_language: "auto",
  output_format: "all",
  epub_layout: "reflowable",
  ocr_accuracy: "high",
  preserve_layout: true,
  preserve_images: true,
  preserve_tables: true,
  embed_fonts: true,
  bangla_font: "hind_siliguri",
  page_range: "",
  doc_title: "",
  doc_author: "",
};

export default function BanglaDocApp() {
  const [lang, setLang] = useState<UILang>("en");
  const [view, setView] = useState<AppView>("home");
  const [uploadInfo, setUploadInfo] = useState<UploadInspectResponse | null>(null);
  const [settings, setSettings] = useState<ConversionSettings>(DEFAULT_CONVERSION_SETTINGS);
  const [isUploading, setIsUploading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [activeJob, setActiveJob] = useState<JobStatusResponse | null>(null);
  const [history, setHistory] = useState<JobStatusResponse[]>([]);

  const t = TRANSLATIONS[lang];

  const refreshHistory = useCallback(async () => {
    try {
      const list = await fetchJobsHistory();
      setHistory(list);
    } catch {
      // ignore offline during boot
    }
  }, []);

  useEffect(() => {
    refreshHistory();
    fetchSystemSettings()
      .then((sysCfg) => {
        setSettings((prev) => ({
          ...prev,
          ocr_language: sysCfg.default_ocr_language,
          ocr_accuracy: sysCfg.default_ocr_accuracy,
          bangla_font: sysCfg.default_bangla_font,
          epub_layout: sysCfg.default_epub_layout,
        }));
      })
      .catch(() => {});
  }, [refreshHistory]);

  // Poll active conversion job while running
  useEffect(() => {
    if (!activeJob) return;
    if (activeJob.status !== "queued" && activeJob.status !== "processing") return;

    const timer = setInterval(async () => {
      try {
        const updated = await fetchJobStatus(activeJob.job_id);
        setActiveJob(updated);
        if (updated.status === "completed" || updated.status === "failed" || updated.status === "cancelled") {
          refreshHistory();
        }
      } catch {
        // retry next tick
      }
    }, 1200);

    return () => clearInterval(timer);
  }, [activeJob, refreshHistory]);

  const handleSelectFile = async (file: File) => {
    setErrorMsg(null);
    setIsUploading(true);
    try {
      const res = await uploadPdfFile(file);
      setUploadInfo(res);
      setSettings((prev) => ({
        ...prev,
        page_range: "",
        doc_title: res.title || file.name.replace(/\.pdf$/i, ""),
        doc_author: res.author || "",
      }));
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to upload PDF.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleLoadSample = async () => {
    setErrorMsg(null);
    setIsUploading(true);
    try {
      const res = await loadSamplePdf();
      setUploadInfo(res);
      setSettings((prev) => ({
        ...prev,
        page_range: "",
        doc_title: res.title || "জাতীয় ডিজিটাল বাংলা আর্কাইভ প্রতিবেদন",
        doc_author: res.author || "BanglaDoc Sample Archive",
      }));
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to load sample PDF.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleStartConversion = async () => {
    if (!uploadInfo) return;
    setErrorMsg(null);
    try {
      const job = await startConversionJob(uploadInfo.upload_id, settings);
      setActiveJob(job);
      setView("processing");
      refreshHistory();
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Failed to start conversion.");
    }
  };

  const handleCancelJob = async () => {
    if (!activeJob) return;
    await cancelJobRequest(activeJob.job_id);
    const updated = await fetchJobStatus(activeJob.job_id);
    setActiveJob(updated);
    refreshHistory();
  };

  const handleDeleteJob = async (jobId: string) => {
    await deleteJobRequest(jobId);
    if (activeJob?.job_id === jobId) {
      setActiveJob(null);
    }
    refreshHistory();
  };

  const handleSystemDefaultsChanged = (sysCfg: SystemSettingsModel) => {
    setSettings((prev) => ({
      ...prev,
      ocr_language: sysCfg.default_ocr_language,
      ocr_accuracy: sysCfg.default_ocr_accuracy,
      bangla_font: sysCfg.default_bangla_font,
      epub_layout: sysCfg.default_epub_layout,
    }));
  };

  const isJobRunning =
    activeJob?.status === "queued" || activeJob?.status === "processing";

  const navItems: { id: AppView; label: string; icon: React.ComponentType<{ className?: string }>; badge?: string }[] = [
    { id: "home", label: t.navHome, icon: FileUp },
    {
      id: "processing",
      label: t.navProcessing,
      icon: isJobRunning ? Loader2 : BookText,
      badge: isJobRunning ? `${Math.round(activeJob?.progress_pct || 0)}%` : undefined,
    },
    { id: "preview", label: t.navPreview, icon: Eye },
    { id: "download", label: t.navDownload, icon: Download },
    {
      id: "history",
      label: t.navHistory,
      icon: Clock,
      badge: history.length > 0 ? String(history.length) : undefined,
    },
    { id: "settings", label: t.navSettings, icon: Settings },
  ];

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-30 bg-white/95 backdrop-blur border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
          {/* Brand */}
          <button
            type="button"
            onClick={() => setView("home")}
            className="flex items-center gap-3 text-left cursor-pointer shrink-0"
          >
            <div className="w-9 h-9 rounded-xl bg-emerald-700 text-white font-bold flex items-center justify-center text-lg shadow-xs font-bangla">
              বাং
            </div>
            <div>
              <div className="text-sm md:text-base font-bold text-slate-900 leading-none font-bangla">
                {t.brandTitle}
              </div>
              <div className="text-[11px] text-slate-500 hidden sm:block mt-0.5 font-bangla">
                {t.brandSubtitle}
              </div>
            </div>
          </button>

          {/* Navigation Links */}
          <nav className="flex items-center gap-0.5 overflow-x-auto no-scrollbar py-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const active = view === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setView(item.id)}
                  className={`px-2.5 py-1.5 rounded-xl text-xs font-semibold flex items-center gap-1.5 whitespace-nowrap transition-colors cursor-pointer font-bangla ${
                    active
                      ? "bg-emerald-700 text-white shadow-xs"
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                  }`}
                >
                  <Icon
                    className={`w-3.5 h-3.5 shrink-0 ${
                      item.id === "processing" && isJobRunning ? "animate-spin" : ""
                    }`}
                  />
                  <span>{item.label}</span>
                  {item.badge && (
                    <span
                      className={`px-1.5 py-0.2 rounded-full text-[10px] font-bold ${
                        active
                          ? "bg-white/20 text-white"
                          : "bg-emerald-100 text-emerald-800"
                      }`}
                    >
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>

          {/* Bilingual Toggle (EN / বাংলা) */}
          <button
            type="button"
            onClick={() => setLang((l) => (l === "en" ? "bn" : "en"))}
            className="px-3 py-1.5 rounded-xl border border-slate-200 hover:bg-slate-100 text-xs font-bold text-slate-800 flex items-center gap-1.5 shrink-0 cursor-pointer font-bangla"
            title="Switch Interface Language"
          >
            <Globe className="w-3.5 h-3.5 text-emerald-700" />
            <span>{lang === "en" ? "বাংলা" : "English"}</span>
          </button>
        </div>
      </header>

      {/* Main Content Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-7">
        {view === "home" && (
          <UploadWorkspace
            lang={lang}
            uploadInfo={uploadInfo}
            settings={settings}
            isUploading={isUploading}
            errorMsg={errorMsg}
            onSelectFile={handleSelectFile}
            onLoadSample={handleLoadSample}
            onResetUpload={() => {
              setUploadInfo(null);
              setErrorMsg(null);
            }}
            onChangeSettings={setSettings}
            onStartConversion={handleStartConversion}
          />
        )}

        {view === "processing" && (
          <ProcessingView
            lang={lang}
            job={activeJob}
            onCancel={handleCancelJob}
            onGoPreview={() => setView("preview")}
            onGoDownload={() => setView("download")}
            onGoHome={() => setView("home")}
          />
        )}

        {view === "preview" && (
          <PreviewCompareStudio
            lang={lang}
            job={activeJob}
            onJobUpdated={(updated) => {
              setActiveJob(updated);
              refreshHistory();
            }}
            onGoDownload={() => setView("download")}
            onGoHome={() => setView("home")}
          />
        )}

        {view === "download" && (
          <DownloadHub
            lang={lang}
            job={activeJob}
            onGoPreview={() => setView("preview")}
            onGoHome={() => setView("home")}
          />
        )}

        {view === "history" && (
          <HistoryPanel
            lang={lang}
            jobs={history}
            activeJobId={activeJob?.job_id || null}
            onSelectJobForPreview={(j) => {
              setActiveJob(j);
              setView("preview");
            }}
            onSelectJobForDownload={(j) => {
              setActiveJob(j);
              setView("download");
            }}
            onDeleteJob={handleDeleteJob}
          />
        )}

        {view === "settings" && (
          <SettingsPanel
            lang={lang}
            onDefaultsChanged={handleSystemDefaultsChanged}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 py-4 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500">
          <div className="flex items-center gap-2 font-bangla">
            <ShieldCheck className="w-4 h-4 text-emerald-700" />
            <span>
              BanglaDoc Converter • Unicode NFC Bangla & English OCR • Zero AI Training • Local Privacy
            </span>
          </div>
          <div>
            Powered by Tesseract 5.5 LSTM + HarfBuzz Vector Shaper + PyMuPDF + EbookLib
          </div>
        </div>
      </footer>
    </div>
  );
}
