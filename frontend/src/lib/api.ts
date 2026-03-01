import axios from "axios";
import type { ExtractionResult, PipelineResult } from "./types";

// Light JSON requests go through Next.js rewrite proxy
const api = axios.create({
  baseURL: "/api",
  timeout: 300_000,
});

// Heavy uploads go direct to FastAPI (Next.js proxy can't handle large multipart)
const backendDirect = axios.create({
  baseURL: "http://localhost:8000/api",
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
): Promise<PipelineResult> {
  const payload: Record<string, unknown> = { extraction: data };
  if (pdfBase64) {
    payload.pdf_base64 = pdfBase64;
  }
  const response = await backendDirect.post<PipelineResult>("/approve", payload, {
    timeout: 300_000,
  });
  return response.data;
}
