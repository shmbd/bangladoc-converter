import {
  ConversionSettings,
  HealthInfo,
  JobStatusResponse,
  LineEditItem,
  PageOCRResult,
  SystemSettingsModel,
  UploadInspectResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "";

export function apiUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return `${API_BASE}${path}`;
}

async function handleJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) msg = String(body.detail);
    } catch {
      // ignore json parse failure
    }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export async function fetchHealth(): Promise<HealthInfo> {
  const res = await fetch(apiUrl("/api/health"), { cache: "no-store" });
  return handleJson<HealthInfo>(res);
}

export async function uploadPdfFile(file: File): Promise<UploadInspectResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(apiUrl("/api/uploads"), {
    method: "POST",
    body: form,
  });
  return handleJson<UploadInspectResponse>(res);
}

export async function loadSamplePdf(): Promise<UploadInspectResponse> {
  const res = await fetch(apiUrl("/api/samples/load"), {
    method: "POST",
  });
  return handleJson<UploadInspectResponse>(res);
}

export async function startConversionJob(
  uploadId: string,
  settings: ConversionSettings
): Promise<JobStatusResponse> {
  const res = await fetch(apiUrl("/api/jobs"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ upload_id: uploadId, settings }),
  });
  return handleJson<JobStatusResponse>(res);
}

export async function fetchJobStatus(jobId: string): Promise<JobStatusResponse> {
  const res = await fetch(apiUrl(`/api/jobs/${jobId}`), { cache: "no-store" });
  return handleJson<JobStatusResponse>(res);
}

export async function fetchJobsHistory(): Promise<JobStatusResponse[]> {
  const res = await fetch(apiUrl("/api/jobs"), { cache: "no-store" });
  return handleJson<JobStatusResponse[]>(res);
}

export async function fetchJobOcrStructure(jobId: string): Promise<PageOCRResult[]> {
  const res = await fetch(apiUrl(`/api/jobs/${jobId}/ocr`), { cache: "no-store" });
  return handleJson<PageOCRResult[]>(res);
}

export async function submitManualEdits(
  jobId: string,
  edits: LineEditItem[]
): Promise<JobStatusResponse> {
  const res = await fetch(apiUrl(`/api/jobs/${jobId}/edits`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ edits }),
  });
  return handleJson<JobStatusResponse>(res);
}

export async function cancelJobRequest(jobId: string): Promise<void> {
  await fetch(apiUrl(`/api/jobs/${jobId}/cancel`), { method: "POST" });
}

export async function deleteJobRequest(jobId: string): Promise<void> {
  await fetch(apiUrl(`/api/jobs/${jobId}`), { method: "DELETE" });
}

export async function fetchSystemSettings(): Promise<SystemSettingsModel> {
  const res = await fetch(apiUrl("/api/settings"), { cache: "no-store" });
  return handleJson<SystemSettingsModel>(res);
}

export async function updateSystemSettings(
  payload: SystemSettingsModel
): Promise<SystemSettingsModel> {
  const res = await fetch(apiUrl("/api/settings"), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleJson<SystemSettingsModel>(res);
}

export async function triggerManualCleanup(): Promise<{ removed_jobs: number }> {
  const res = await fetch(apiUrl("/api/settings/cleanup"), { method: "POST" });
  return handleJson<{ removed_jobs: number }>(res);
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}
