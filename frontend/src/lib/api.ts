import axios from "axios";
import type { ExtractionResult } from "./types";

// Light requests go through Next.js rewrite proxy (avoids CORS config)
const api = axios.create({
  baseURL: "/api",
});

// Heavy uploads go direct to FastAPI (avoids Next.js proxy body/timeout limits)
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
      timeout: 180_000, // 3 min — Claude vision can take a while on large PDFs
    }
  );

  return response.data;
}

export async function approveAndPush(
  data: ExtractionResult
): Promise<{ status: string }> {
  const response = await api.post("/approve", data);
  return response.data;
}
