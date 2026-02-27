"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { FileUp, Loader2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useExtraction } from "@/lib/ExtractionContext";
import { uploadAndExtract } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

export default function UploadPage() {
  const router = useRouter();
  const { toast } = useToast();
  const { setExtraction, setPdfBlobUrl, setPipelineStatus } = useExtraction();

  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
      setPipelineStatus("extracting");

      // Store the PDF blob URL for the viewer
      const blobUrl = URL.createObjectURL(file);
      setPdfBlobUrl(blobUrl);

      try {
        const result = await uploadAndExtract(file);
        setExtraction(result);
        setPipelineStatus("reviewing");
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
    [router, setExtraction, setPdfBlobUrl, setPipelineStatus, toast]
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

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  return (
    <div className="max-w-2xl mx-auto px-6 py-16">
      <div className="text-center mb-10">
        <h2 className="text-3xl font-bold text-gray-900 mb-2">
          Police Report Extraction
        </h2>
        <p className="text-gray-500 text-lg">
          Upload a police report PDF and AI will extract all case data
          automatically.
        </p>
      </div>

      <Card
        className={`
          relative border-2 border-dashed rounded-xl p-16
          transition-all duration-200 cursor-pointer
          ${isDragging ? "border-blue-500 bg-blue-50" : "border-gray-300 bg-white hover:border-gray-400 hover:bg-gray-50"}
          ${isLoading ? "pointer-events-none opacity-80" : ""}
        `}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => !isLoading && fileInputRef.current?.click()}
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
          {isLoading ? (
            <>
              <Loader2 className="h-16 w-16 text-blue-500 animate-spin" />
              <div className="text-center">
                <p className="text-lg font-semibold text-gray-700">
                  Extracting data with AI...
                </p>
                <p className="text-sm text-gray-500 mt-1">
                  Claude is analyzing every page of the report. This may take
                  30-60 seconds.
                </p>
              </div>
            </>
          ) : (
            <>
              <div
                className={`
                  h-20 w-20 rounded-full flex items-center justify-center
                  ${isDragging ? "bg-blue-100" : "bg-gray-100"}
                `}
              >
                <FileUp
                  className={`h-10 w-10 ${isDragging ? "text-blue-500" : "text-gray-400"}`}
                />
              </div>
              <div className="text-center">
                <p className="text-lg font-semibold text-gray-700">
                  {isDragging
                    ? "Drop your PDF here"
                    : "Drop a police report PDF here"}
                </p>
                <p className="text-sm text-gray-500 mt-1">or click to browse files</p>
              </div>
              <Button variant="outline" size="sm" className="mt-2">
                Browse Files
              </Button>
            </>
          )}
        </div>
      </Card>

      {error && (
        <div className="mt-4 flex items-start gap-2 rounded-lg bg-red-50 border border-red-200 p-4">
          <AlertCircle className="h-5 w-5 text-red-500 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-medium text-red-800">Error</p>
            <p className="text-sm text-red-600">{error}</p>
          </div>
        </div>
      )}

      <div className="mt-12 text-center text-xs text-gray-400">
        Supported: PDF files up to 50 MB. Multi-page reports are handled
        automatically.
      </div>
    </div>
  );
}
