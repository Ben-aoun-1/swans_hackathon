import axios from "axios";
import type { ExtractionResult, PipelineResult, SetupResult, ClioStatus } from "./types";

// In production (behind Nginx), all requests go through /api.
// In development, heavy uploads go direct to FastAPI to bypass Next.js proxy limits.
const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

const backendDirect = axios.create({
  baseURL: `${BACKEND_URL}/api`,
  withCredentials: true,
});

export async function uploadAndExtract(file: File): Promise<ExtractionResult> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await backendDirect.post<ExtractionResult>(
    "/extract",
    formData,
    {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 180_000,
    }
  );

  return response.data;
}

export async function approveAndPush(
  data: ExtractionResult,
  pdfBase64?: string | null,
  uploadTimestamp?: number | null,
): Promise<PipelineResult> {
  const payload: Record<string, unknown> = { extraction: data };
  if (pdfBase64) {
    payload.pdf_base64 = pdfBase64;
  }
  if (uploadTimestamp) {
    payload.upload_timestamp = uploadTimestamp;
  }
  const response = await backendDirect.post<PipelineResult>("/approve", payload, {
    timeout: 300_000,
  });
  return response.data;
}

// ── Clio Setup ──────────────────────────────────────────────────────────

export async function getClioStatus(): Promise<ClioStatus> {
  const response = await backendDirect.get<ClioStatus>("/clio/status");
  return response.data;
}

export async function getClioAuthUrl(): Promise<string> {
  const response = await backendDirect.get<{ auth_url: string }>("/clio/auth");
  return response.data.auth_url;
}

export async function checkClioSetup(): Promise<SetupResult> {
  const response = await backendDirect.get<SetupResult>("/clio/setup/check");
  return response.data;
}

export async function runClioSetup(): Promise<SetupResult> {
  const response = await backendDirect.post<SetupResult>("/clio/setup/run");
  return response.data;
}

export async function disconnectClio(): Promise<void> {
  await backendDirect.post("/clio/disconnect");
}
