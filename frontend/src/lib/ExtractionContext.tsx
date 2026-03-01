"use client";

import {
  createContext,
  useContext,
  useState,
  type ReactNode,
} from "react";
import type { ExtractionResult, PipelineResult, PipelineStatus } from "./types";

interface ExtractionContextValue {
  extraction: ExtractionResult | null;
  setExtraction: (data: ExtractionResult | null) => void;
  pdfBlobUrl: string | null;
  setPdfBlobUrl: (url: string | null) => void;
  pdfBase64: string | null;
  setPdfBase64: (b64: string | null) => void;
  pipelineStatus: PipelineStatus;
  setPipelineStatus: (status: PipelineStatus) => void;
  pipelineResult: PipelineResult | null;
  setPipelineResult: (result: PipelineResult | null) => void;
}

const ExtractionContext = createContext<ExtractionContextValue | null>(null);

export function ExtractionProvider({ children }: { children: ReactNode }) {
  const [extraction, setExtraction] = useState<ExtractionResult | null>(null);
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null);
  const [pdfBase64, setPdfBase64] = useState<string | null>(null);
  const [pipelineStatus, setPipelineStatus] =
    useState<PipelineStatus>("idle");
  const [pipelineResult, setPipelineResult] =
    useState<PipelineResult | null>(null);

  return (
    <ExtractionContext.Provider
      value={{
        extraction,
        setExtraction,
        pdfBlobUrl,
        setPdfBlobUrl,
        pdfBase64,
        setPdfBase64,
        pipelineStatus,
        setPipelineStatus,
        pipelineResult,
        setPipelineResult,
      }}
    >
      {children}
    </ExtractionContext.Provider>
  );
}

export function useExtraction() {
  const ctx = useContext(ExtractionContext);
  if (!ctx) {
    throw new Error("useExtraction must be used within ExtractionProvider");
  }
  return ctx;
}
