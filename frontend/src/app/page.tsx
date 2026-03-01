"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  FileUp,
  Loader2,
  AlertCircle,
  CheckCircle2,
  Zap,
  Brain,
  Layers,
  FileText,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useExtraction } from "@/lib/ExtractionContext";
import { uploadAndExtract } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

const LOADING_STEPS = [
  "Reading PDF pages",
  "Analyzing report with AI",
  "Structuring extracted data",
];

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function UploadPage() {
  const router = useRouter();
  const { toast } = useToast();
  const { setExtraction, setPdfBlobUrl, setPdfBase64, setPipelineStatus } =
    useExtraction();

  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState("");
  const [fileSize, setFileSize] = useState(0);
  const [progress, setProgress] = useState(0);
  const [loadingStep, setLoadingStep] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Animated progress during extraction
  useEffect(() => {
    if (!isLoading) {
      setProgress(0);
      setLoadingStep(0);
      return;
    }
    const start = Date.now();
    const interval = setInterval(() => {
      const elapsed = (Date.now() - start) / 1000;
      const p = Math.min(92, 92 * (1 - Math.exp(-elapsed / 28)));
      setProgress(p);
      if (elapsed < 3) setLoadingStep(0);
      else if (elapsed < 35) setLoadingStep(1);
      else setLoadingStep(2);
    }, 150);
    return () => clearInterval(interval);
  }, [isLoading]);

  const handleFile = useCallback(
    async (file: File) => {
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        setError("Please upload a PDF file.");
        return;
      }
      if (file.size > 50 * 1024 * 1024) {
        setError("File is too large (max 50 MB).");
        return;
      }

      setError(null);
      setIsLoading(true);
      setFileName(file.name);
      setFileSize(file.size);
      setPipelineStatus("extracting");

      const blobUrl = URL.createObjectURL(file);
      setPdfBlobUrl(blobUrl);

      const arrayBuf = await file.arrayBuffer();
      const bytes = new Uint8Array(arrayBuf);
      let binary = "";
      for (let i = 0; i < bytes.length; i++) {
        binary += String.fromCharCode(bytes[i]);
      }
      setPdfBase64(btoa(binary));

      try {
        const result = await uploadAndExtract(file);
        setProgress(100);
        setExtraction(result);
        setPipelineStatus("reviewing");
        await new Promise((r) => setTimeout(r, 400));
        router.push("/review");
      } catch (err: unknown) {
        setIsLoading(false);
        setPipelineStatus("error");
        const message =
          err instanceof Error ? err.message : "Extraction failed";
        setError(message);
        toast({
          variant: "destructive",
          title: "Extraction Failed",
          description: message,
        });
      }
    },
    [router, setExtraction, setPdfBlobUrl, setPdfBase64, setPipelineStatus, toast]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  return (
    <div className="min-h-[calc(100vh-56px)] flex items-center justify-center px-6">
      <div className="max-w-5xl w-full grid grid-cols-1 lg:grid-cols-[1.2fr_1fr] gap-12 lg:gap-16 items-center py-12">
        {/* Left: Hero */}
        <div className="animate-fade-in-up">
          <div className="flex items-center gap-2 mb-6">
            <div className="h-px flex-1 max-w-[40px] bg-amber-500" />
            <span className="text-xs font-semibold uppercase tracking-widest text-amber-600">
              AI-Powered
            </span>
          </div>

          <h1 className="font-serif text-5xl lg:text-6xl text-slate-900 leading-[1.1] tracking-tight">
            Intake
            <br />
            Automation
          </h1>

          <p className="mt-6 text-lg text-slate-500 leading-relaxed max-w-md">
            Upload a police report PDF. AI extracts every field.
            Your Clio matter is updated in under 3 minutes.
          </p>

          <div className="mt-8 flex flex-wrap gap-3">
            <div className="flex items-center gap-2 px-4 py-2 bg-slate-100 rounded-full text-sm text-slate-600">
              <Zap className="h-3.5 w-3.5 text-amber-500" />
              3 min vs 45 min
            </div>
            <div className="flex items-center gap-2 px-4 py-2 bg-slate-100 rounded-full text-sm text-slate-600">
              <Brain className="h-3.5 w-3.5 text-amber-500" />
              AI Extraction
            </div>
            <div className="flex items-center gap-2 px-4 py-2 bg-slate-100 rounded-full text-sm text-slate-600">
              <Layers className="h-3.5 w-3.5 text-amber-500" />
              20 Steps Automated
            </div>
          </div>
        </div>

        {/* Right: Upload/Loading Card */}
        <div
          className="animate-fade-in-up"
          style={{ animationDelay: "0.15s", opacity: 0 }}
        >
          <div className="bg-white border border-slate-200 rounded-xl shadow-lg shadow-slate-200/60 overflow-hidden">
            {/* Card header */}
            <div className="px-5 py-3 bg-slate-50/80 border-b border-slate-100 flex items-center gap-2">
              <FileText className="h-4 w-4 text-slate-400" />
              <span className="text-sm font-medium text-slate-600">
                {isLoading ? fileName : "Upload Police Report"}
              </span>
              {isLoading && (
                <span className="text-xs text-slate-400 ml-auto">
                  {formatSize(fileSize)}
                </span>
              )}
            </div>

            {isLoading ? (
              /* Loading state */
              <div className="p-8">
                {/* Progress bar */}
                <div className="h-1.5 w-full bg-slate-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-amber-500 rounded-full transition-all duration-300 ease-out"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <p className="text-xs text-slate-400 mt-2 text-right">
                  {Math.round(progress)}%
                </p>

                <div className="mt-6 space-y-4">
                  {LOADING_STEPS.map((step, i) => {
                    const isDone = i < loadingStep;
                    const isActive = i === loadingStep;
                    return (
                      <div
                        key={i}
                        className={`flex items-center gap-3 transition-colors duration-300 ${
                          isDone
                            ? "text-emerald-600"
                            : isActive
                              ? "text-slate-800"
                              : "text-slate-300"
                        }`}
                      >
                        {isDone ? (
                          <CheckCircle2 className="h-5 w-5 shrink-0" />
                        ) : isActive ? (
                          <Loader2 className="h-5 w-5 shrink-0 animate-spin text-amber-500" />
                        ) : (
                          <div className="h-5 w-5 rounded-full border-2 border-current shrink-0" />
                        )}
                        <span className="text-sm font-medium">{step}</span>
                      </div>
                    );
                  })}
                </div>

                <p className="mt-6 text-xs text-slate-400 text-center">
                  Claude Sonnet 4.6 is analyzing every page. This may take 30-60s.
                </p>
              </div>
            ) : (
              /* Upload zone */
              <div
                className={`p-12 cursor-pointer transition-all duration-200 ${
                  isDragging
                    ? "bg-amber-50/60"
                    : "bg-white hover:bg-slate-50/50"
                }`}
                onDrop={handleDrop}
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragging(true);
                }}
                onDragLeave={(e) => {
                  e.preventDefault();
                  setIsDragging(false);
                }}
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleFile(file);
                  }}
                />

                <div className="flex flex-col items-center gap-4">
                  <div
                    className={`h-16 w-16 rounded-2xl flex items-center justify-center transition-colors duration-200 ${
                      isDragging
                        ? "bg-amber-100 text-amber-600"
                        : "bg-slate-100 text-slate-400"
                    }`}
                  >
                    <FileUp className="h-7 w-7" />
                  </div>

                  <div className="text-center">
                    <p className="text-base font-semibold text-slate-700">
                      {isDragging
                        ? "Drop your PDF here"
                        : "Drop a police report here"}
                    </p>
                    <p className="text-sm text-slate-400 mt-1">
                      or click to browse files
                    </p>
                  </div>

                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-1 border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-slate-800"
                  >
                    Browse Files
                  </Button>
                </div>
              </div>
            )}
          </div>

          {/* Error message */}
          {error && (
            <div className="mt-4 flex items-start gap-2 rounded-lg bg-red-50 border border-red-200 p-4 animate-fade-in-up">
              <AlertCircle className="h-5 w-5 text-red-500 mt-0.5 shrink-0" />
              <div>
                <p className="text-sm font-medium text-red-800">Error</p>
                <p className="text-sm text-red-600">{error}</p>
              </div>
            </div>
          )}

          <p className="mt-4 text-center text-xs text-slate-400">
            PDF files up to 50 MB. Multi-page reports handled automatically.
          </p>
        </div>
      </div>
    </div>
  );
}
