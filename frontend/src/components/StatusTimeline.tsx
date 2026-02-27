"use client";

import { Check } from "lucide-react";
import type { PipelineStatus } from "@/lib/types";

const STEPS = [
  { key: "uploading", label: "Upload" },
  { key: "extracting", label: "Extract" },
  { key: "reviewing", label: "Review" },
  { key: "pushing_to_clio", label: "Push to Clio" },
  { key: "generating_document", label: "Retainer" },
  { key: "sending_email", label: "Email" },
] as const;

// Maps a pipeline status to the index of the current step
function statusToIndex(status: PipelineStatus): number {
  switch (status) {
    case "idle":
      return -1;
    case "uploading":
      return 0;
    case "extracting":
      return 1;
    case "reviewing":
      return 2;
    case "pushing_to_clio":
      return 3;
    case "generating_document":
      return 4;
    case "sending_email":
      return 5;
    case "complete":
      return 6;
    case "error":
      return -2;
  }
}

export function StatusTimeline({ status }: { status: PipelineStatus }) {
  const currentIdx = statusToIndex(status);

  return (
    <div className="flex items-center gap-1">
      {STEPS.map((step, i) => {
        const isComplete = currentIdx > i;
        const isCurrent = currentIdx === i;
        const isFuture = !isComplete && !isCurrent;

        return (
          <div key={step.key} className="flex items-center">
            {/* Step circle */}
            <div className="flex flex-col items-center gap-1">
              <div
                className={`
                  flex h-7 w-7 items-center justify-center rounded-full border-2 text-xs font-semibold
                  transition-all duration-300
                  ${isComplete ? "border-emerald-500 bg-emerald-500 text-white" : ""}
                  ${isCurrent ? "border-blue-500 bg-blue-50 text-blue-600 animate-pulse" : ""}
                  ${isFuture ? "border-gray-300 bg-white text-gray-400" : ""}
                `}
              >
                {isComplete ? <Check className="h-4 w-4" /> : i + 1}
              </div>
              <span
                className={`text-[10px] font-medium whitespace-nowrap
                  ${isComplete ? "text-emerald-600" : ""}
                  ${isCurrent ? "text-blue-600 font-semibold" : ""}
                  ${isFuture ? "text-gray-400" : ""}
                `}
              >
                {step.label}
              </span>
            </div>

            {/* Connector line */}
            {i < STEPS.length - 1 && (
              <div
                className={`h-0.5 w-6 mx-1 mt-[-16px] transition-colors duration-300
                  ${currentIdx > i ? "bg-emerald-500" : "bg-gray-300"}
                `}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
