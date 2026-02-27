"use client";

import {
  createContext,
  useContext,
  useState,
  type ReactNode,
} from "react";
import type { ExtractionResult, PipelineStatus } from "./types";

interface ExtractionContextValue {
  extraction: ExtractionResult | null;
  setExtraction: (data: ExtractionResult | null) => void;
  pdfBlobUrl: string | null;
  setPdfBlobUrl: (url: string | null) => void;
  pipelineStatus: PipelineStatus;
  setPipelineStatus: (status: PipelineStatus) => void;
}

const ExtractionContext = createContext<ExtractionContextValue | null>(null);

export function ExtractionProvider({ children }: { children: ReactNode }) {
  const [extraction, setExtraction] = useState<ExtractionResult | null>(null);
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null);
  const [pipelineStatus, setPipelineStatus] =
    useState<PipelineStatus>("idle");

  return (
    <ExtractionContext.Provider
      value={{
        extraction,
        setExtraction,
        pdfBlobUrl,
        setPdfBlobUrl,
        pipelineStatus,
        setPipelineStatus,
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
