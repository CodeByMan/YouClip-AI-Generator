import { friendlyHttpError } from "./http-errors.mjs";

export type SourceType = "url" | "upload";
export type PipelineMode = "api" | "local";
export type JobStatus = "queued" | "processing" | "completed" | "failed";

export interface HealthResponse {
  status: string;
  service: string;
  access_mode: "local" | "hosted";
  max_workers: number;
  max_queued_jobs: number;
  max_upload_mb: number;
  max_video_seconds: number;
  retention_seconds: number;
  providers: {
    muapi_configured: boolean;
    openai_configured: boolean;
    gemini_configured: boolean;
    local_llm_provider: string;
  };
}

export interface ShortResult {
  start_time?: number;
  end_time?: number;
  score?: number;
  title?: string;
  hook_sentence?: string;
  virality_reason?: string;
  clip_url?: string | null;
  error?: string;
}

export interface PipelineResult {
  mode: PipelineMode;
  source_video_url: string;
  transcript?: { language?: string; segments?: unknown[] };
  highlights: ShortResult[];
  shorts: ShortResult[];
}

export interface JobResponse {
  id: string;
  status: JobStatus;
  progress: number;
  message: string;
  created_at: string;
  updated_at: string;
  expires_at: string;
  request: {
    source_type: SourceType;
    source: string;
    mode: PipelineMode;
    num_clips: number;
    aspect_ratio: string;
    download_format: string;
    language?: string | null;
  };
  result?: PipelineResult | null;
  error?: string | null;
}

export interface JobPayload {
  source_type: SourceType;
  source: string;
  mode: PipelineMode;
  num_clips: number;
  aspect_ratio: string;
  download_format: "360" | "480" | "720" | "1080";
  language: string | null;
}

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
const ACCESS_KEY_STORAGE = "youclip-ai-access-key";

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

export function storedAccessKey(): string {
  if (typeof window === "undefined") return "";
  return window.sessionStorage.getItem(ACCESS_KEY_STORAGE) || "";
}

export function setAccessKey(value: string): void {
  if (typeof window === "undefined") return;
  const cleaned = value.trim();
  if (cleaned) window.sessionStorage.setItem(ACCESS_KEY_STORAGE, cleaned);
  else window.sessionStorage.removeItem(ACCESS_KEY_STORAGE);
}

function authHeaders(extra?: HeadersInit): Headers {
  const headers = new Headers(extra);
  const key = storedAccessKey();
  if (key) headers.set("X-YouClip-Key", key);
  return headers;
}

async function parseResponse<T>(response: Response): Promise<T> {
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.detail;
    const message = Array.isArray(detail)
      ? detail.map((item: { msg?: string }) => item.msg || "Invalid request").join(". ")
      : detail || `Request failed with status ${response.status}`;
    const friendly = friendlyHttpError(response.status, message);
    throw new ApiError(friendly, response.status);
  }
  return body as T;
}

export function apiBase(): string {
  return API_BASE;
}

export function publicMediaUrl(value?: string | null): string | null {
  if (!value) return null;
  if (/^https?:\/\//i.test(value)) return value;
  return `${API_BASE}${value.startsWith("/") ? value : `/${value}`}`;
}

export async function loadMediaUrl(value: string, signal?: AbortSignal): Promise<{ url: string; revoke: boolean }> {
  if (/^https?:\/\//i.test(value)) return { url: value, revoke: false };
  const response = await fetch(publicMediaUrl(value)!, {
    signal,
    cache: "no-store",
    headers: authHeaders(),
  });
  if (!response.ok) await parseResponse<never>(response);
  return { url: URL.createObjectURL(await response.blob()), revoke: true };
}

export async function downloadMedia(value: string, filename: string): Promise<void> {
  const controller = new AbortController();
  const asset = await loadMediaUrl(value, controller.signal);
  const anchor = document.createElement("a");
  anchor.href = asset.url;
  anchor.download = filename;
  anchor.target = "_blank";
  anchor.rel = "noreferrer";
  anchor.click();
  if (asset.revoke) window.setTimeout(() => URL.revokeObjectURL(asset.url), 1000);
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return parseResponse<HealthResponse>(
    await fetch(`${API_BASE}/api/health`, { signal, cache: "no-store", headers: authHeaders() }),
  );
}

export async function uploadVideo(file: File): Promise<{ upload_id: string; filename: string; size_bytes: number }> {
  const data = new FormData();
  data.append("file", file);
  return parseResponse(
    await fetch(`${API_BASE}/api/uploads`, {
      method: "POST",
      body: data,
      headers: authHeaders(),
    }),
  );
}

export async function createJob(payload: JobPayload): Promise<JobResponse> {
  return parseResponse<JobResponse>(
    await fetch(`${API_BASE}/api/jobs`, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
    }),
  );
}

export async function getJob(jobId: string, signal?: AbortSignal): Promise<JobResponse> {
  return parseResponse<JobResponse>(
    await fetch(`${API_BASE}/api/jobs/${jobId}`, { signal, cache: "no-store", headers: authHeaders() }),
  );
}
