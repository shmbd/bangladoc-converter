"use client";

import React, { useEffect, useState } from "react";
import {
  CheckCircle2,
  Cpu,
  Lock,
  Save,
  Shield,
  Trash2,
} from "lucide-react";
import {
  fetchHealth,
  fetchSystemSettings,
  triggerManualCleanup,
  updateSystemSettings,
} from "@/lib/api";
import { TRANSLATIONS } from "@/lib/i18n";
import { HealthInfo, SystemSettingsModel, UILang } from "@/lib/types";

interface SettingsPanelProps {
  lang: UILang;
  onDefaultsChanged: (cfg: SystemSettingsModel) => void;
}

export default function SettingsPanel({
  lang,
  onDefaultsChanged,
}: SettingsPanelProps) {
  const t = TRANSLATIONS[lang];
  const [cfg, setCfg] = useState<SystemSettingsModel>({
    retention_hours: 24,
    default_ocr_language: "auto",
    default_ocr_accuracy: "high",
    default_bangla_font: "hind_siliguri",
    default_epub_layout: "reflowable",
    auto_cleanup_enabled: true,
  });
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [savedToast, setSavedToast] = useState(false);
  const [cleanupMsg, setCleanupMsg] = useState<string | null>(null);

  useEffect(() => {
    fetchSystemSettings().then(setCfg).catch(() => {});
    fetchHealth().then(setHealth).catch(() => {});
  }, []);

  const handleSave = async () => {
    const saved = await updateSystemSettings(cfg);
    setCfg(saved);
    onDefaultsChanged(saved);
    setSavedToast(true);
    setTimeout(() => setSavedToast(false), 2500);
  };

  const handlePurgeExpired = async () => {
    const res = await triggerManualCleanup();
    setCleanupMsg(`Purged ${res.removed_jobs} expired job(s).`);
    setTimeout(() => setCleanupMsg(null), 3000);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h2 className="text-xl font-bold text-slate-900 font-bangla">{t.settingsHeading}</h2>

      {/* Privacy & Security Guarantee Card */}
      <div className="rounded-2xl bg-emerald-950 text-emerald-50 p-6 border border-emerald-800 flex items-start gap-4">
        <Lock className="w-6 h-6 text-emerald-400 shrink-0 mt-0.5" />
        <div className="space-y-1.5">
          <h3 className="text-sm font-bold text-white">Document Privacy & Zero-Training Guarantee</h3>
          <p className="text-xs text-emerald-100/85 leading-relaxed font-bangla">
            {t.privacyBanner}
          </p>
        </div>
      </div>

      {/* Default Preferences Form */}
      <div className="rounded-2xl bg-white border border-slate-200 p-6 shadow-sm space-y-5">
        <h3 className="text-sm font-bold text-slate-800 border-b border-slate-100 pb-3">
          Default Conversion & Retention Policy
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Default OCR Language
            </label>
            <select
              value={cfg.default_ocr_language}
              onChange={(e) =>
                setCfg({
                  ...cfg,
                  default_ocr_language: e.target.value as SystemSettingsModel["default_ocr_language"],
                })
              }
              className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm bg-white"
            >
              <option value="auto">Automatic (Bangla + English)</option>
              <option value="ben">Bangla Only (বাংলা)</option>
              <option value="eng">English Only</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Default OCR Accuracy Profile
            </label>
            <select
              value={cfg.default_ocr_accuracy}
              onChange={(e) =>
                setCfg({
                  ...cfg,
                  default_ocr_accuracy: e.target.value as SystemSettingsModel["default_ocr_accuracy"],
                })
              }
              className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm bg-white"
            >
              <option value="high">High Accuracy (300 DPI + Best LSTM)</option>
              <option value="standard">Standard Fast (210 DPI)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Default Unicode Bangla Font
            </label>
            <select
              value={cfg.default_bangla_font}
              onChange={(e) =>
                setCfg({
                  ...cfg,
                  default_bangla_font: e.target.value as SystemSettingsModel["default_bangla_font"],
                })
              }
              className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm bg-white"
            >
              <option value="hind_siliguri">Hind Siliguri (SIL OFL)</option>
              <option value="noto_sans_bengali">Noto Sans Bengali (SIL OFL)</option>
              <option value="noto_serif_bengali">Noto Serif Bengali (SIL OFL)</option>
              <option value="kalpurush">Kalpurush (OmicronLab)</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Temporary File Retention Window (Hours)
            </label>
            <select
              value={cfg.retention_hours}
              onChange={(e) =>
                setCfg({ ...cfg, retention_hours: Number(e.target.value) })
              }
              className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm bg-white"
            >
              <option value={1}>1 Hour (Strict Privacy)</option>
              <option value={6}>6 Hours</option>
              <option value={24}>24 Hours (Recommended)</option>
              <option value={72}>72 Hours</option>
            </select>
          </div>
        </div>

        <label className="flex items-center gap-2.5 text-xs font-semibold text-slate-700 cursor-pointer">
          <input
            type="checkbox"
            checked={cfg.auto_cleanup_enabled}
            onChange={(e) => setCfg({ ...cfg, auto_cleanup_enabled: e.target.checked })}
            className="w-4 h-4 accent-emerald-700 rounded"
          />
          <span>Automatically purge expired uploads and converted files in background</span>
        </label>

        <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-100">
          <button
            type="button"
            onClick={handlePurgeExpired}
            className="px-4 py-2.5 rounded-xl border border-slate-300 hover:bg-slate-100 text-xs font-semibold text-slate-700 flex items-center gap-1.5 cursor-pointer"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Run Expired File Cleanup Now</span>
          </button>

          <div className="flex items-center gap-3">
            {cleanupMsg && <span className="text-xs text-slate-600">{cleanupMsg}</span>}
            {savedToast && (
              <span className="text-xs text-emerald-700 font-semibold flex items-center gap-1">
                <CheckCircle2 className="w-4 h-4" /> Saved!
              </span>
            )}
            <button
              type="button"
              onClick={handleSave}
              className="px-5 py-2.5 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-bold flex items-center gap-1.5 cursor-pointer"
            >
              <Save className="w-3.5 h-3.5" />
              <span>Save Preferences</span>
            </button>
          </div>
        </div>
      </div>

      {/* Engine Diagnostics Card */}
      {health && (
        <div className="rounded-2xl bg-white border border-slate-200 p-6 shadow-sm space-y-4">
          <div className="flex items-center gap-2 text-sm font-bold text-slate-800">
            <Cpu className="w-4 h-4 text-emerald-700" />
            <span>Active OCR & Font Shaping Engine Status</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            <div className="rounded-xl bg-slate-50 border border-slate-200 p-3">
              <div className="text-slate-500">OCR Engine</div>
              <div className="font-bold text-slate-900 mt-0.5">{health.tesseract_version}</div>
            </div>
            <div className="rounded-xl bg-slate-50 border border-slate-200 p-3">
              <div className="text-slate-500">Bangla LSTM Models</div>
              <div className="font-bold text-emerald-700 mt-0.5">
                {health.bangla_best_model ? "tessdata_best + fast Ready" : "Missing"}
              </div>
            </div>
            <div className="rounded-xl bg-slate-50 border border-slate-200 p-3">
              <div className="text-slate-500">OpenType Shaper</div>
              <div className="font-bold text-emerald-700 mt-0.5">
                HarfBuzz Vector + NFC Layer ({health.fonts.length} Fonts)
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
