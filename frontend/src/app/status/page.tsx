"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  CheckCircle2,
  XCircle,
  Loader2,
  Zap,
  ExternalLink,
  FileUp,
  Settings,
  Database,
  FileText,
  Mail,
  Flag,
  AlertTriangle,
  ArrowRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useExtraction } from "@/lib/ExtractionContext";
import type { PipelineStepResult } from "@/lib/types";

const STEP_GROUPS = [
  {
    label: "Setup",
    icon: Settings,
    steps: ["authenticate", "map_custom_fields", "conflict_check"],
  },
  {
    label: "Clio Records",
    icon: Database,
    steps: [
      "find_or_create_contact",
      "find_or_create_matter",
      "duplicate_check",
      "update_custom_fields",
      "update_stage",
    ],
  },
  {
    label: "Documents",
    icon: FileText,
    steps: ["generate_retainer", "upload_police_report", "upload_retainer_to_clio"],
  },
  {
    label: "Communications",
    icon: Mail,
    steps: [
      "ai_email_personalization",
      "send_email",
      "create_tasks",
      "log_activity",
      "log_communication",
    ],
  },
  {
    label: "Finalize",
    icon: Flag,
    steps: ["priority_scoring", "audit_trail_note", "stage_retainer_sent"],
  },
];

const STEP_LABELS: Record<string, string> = {
  authenticate: "Authenticate with Clio",
  map_custom_fields: "Map Custom Fields",
  conflict_check: "Conflict of Interest Check",
  find_or_create_contact: "Find or Create Contact",
  find_or_create_matter: "Find or Create Matter",
  duplicate_check: "Duplicate Report Check",
  update_custom_fields: "Update Custom Fields",
  update_stage: "Advance Matter Stage",
  generate_retainer: "Generate Retainer Agreement",
  upload_police_report: "Upload Police Report",
  upload_retainer_to_clio: "Upload Retainer to Clio",
  ai_email_personalization: "AI Email Personalization",
  send_email: "Send Client Email",
  create_tasks: "Create Task List",
  log_activity: "Log Intake Activity",
  log_communication: "Log Communication",
  priority_scoring: "Case Priority Scoring",
  audit_trail_note: "Create Audit Trail",
  stage_retainer_sent: "Final Stage Update",
};

function StepIcon({ status }: { status: string }) {
  switch (status) {
    case "success":
      return <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />;
    case "error":
      return <XCircle className="h-4 w-4 text-red-500 shrink-0" />;
    default:
      return <Loader2 className="h-4 w-4 text-amber-500 animate-spin shrink-0" />;
  }
}

function PriorityBadge({ score }: { score: number }) {
  let color: string;
  let label: string;
  if (score >= 8) {
    color = "bg-emerald-100 text-emerald-800 border-emerald-200";
    label = "High Priority";
  } else if (score >= 5) {
    color = "bg-amber-100 text-amber-800 border-amber-200";
    label = "Medium Priority";
  } else {
    color = "bg-red-100 text-red-800 border-red-200";
    label = "Low Priority";
  }
  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border ${color}`}>
      <span className="text-2xl font-bold font-serif">{score}</span>
      <div className="text-left">
        <p className="text-xs font-semibold leading-tight">{label}</p>
        <p className="text-[10px] opacity-70">out of 10</p>
      </div>
    </div>
  );
}

export default function StatusPage() {
  const router = useRouter();
  const { pipelineResult, setPipelineResult, setPipelineStatus, uploadTimestamp } =
    useExtraction();

  const [visibleCount, setVisibleCount] = useState(0);
  const [showSummary, setShowSummary] = useState(false);
  const [displaySpeed, setDisplaySpeed] = useState(0);

  // Filter out skipped steps entirely
  const visibleSteps = pipelineResult?.steps?.filter(
    (s) => s.status !== "skipped"
  ) ?? [];

  const totalSteps = visibleSteps.length;
  const allRevealed = visibleCount >= totalSteps;

  // Progressive step reveal
  useEffect(() => {
    if (!pipelineResult || visibleCount >= totalSteps) return;
    const timer = setTimeout(() => {
      setVisibleCount((prev) => prev + 1);
    }, 220);
    return () => clearTimeout(timer);
  }, [visibleCount, totalSteps, pipelineResult]);

  // Show summary after all steps revealed
  useEffect(() => {
    if (!allRevealed || !pipelineResult) return;
    const timer = setTimeout(() => setShowSummary(true), 600);
    return () => clearTimeout(timer);
  }, [allRevealed, pipelineResult]);

  // Animated speed counter
  useEffect(() => {
    if (!showSummary || !pipelineResult?.speed_to_lead_seconds) return;
    const target = pipelineResult.speed_to_lead_seconds;
    const duration = 1200;
    const start = Date.now();

    const animate = () => {
      const elapsed = Date.now() - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - (1 - progress) * (1 - progress);
      setDisplaySpeed(Math.round(target * eased));
      if (progress < 1) requestAnimationFrame(animate);
    };
    requestAnimationFrame(animate);
  }, [showSummary, pipelineResult?.speed_to_lead_seconds]);

  const handleNewReport = useCallback(() => {
    setPipelineResult(null);
    setPipelineStatus("idle");
    router.push("/");
  }, [setPipelineResult, setPipelineStatus, router]);

  // Redirect if no result
  useEffect(() => {
    if (!pipelineResult) router.push("/");
  }, [pipelineResult, router]);

  if (!pipelineResult) return null;

  // Build map only from non-skipped steps
  const stepMap = new Map<string, PipelineStepResult>();
  for (const step of visibleSteps) {
    stepMap.set(step.name, step);
  }

  const passed = visibleSteps.filter((s) => s.status === "success").length;
  const failed = visibleSteps.filter((s) => s.status === "error").length;

  // Build a flat index for determining visibility
  let flatIndex = 0;
  const flatIndexMap = new Map<string, number>();
  for (const group of STEP_GROUPS) {
    for (const stepName of group.steps) {
      if (stepMap.has(stepName)) {
        flatIndexMap.set(stepName, flatIndex++);
      }
    }
  }

  // Format speed display
  const speedSeconds = pipelineResult.speed_to_lead_seconds ?? 0;
  const speedMins = Math.floor(displaySpeed / 60);
  const speedSecs = displaySpeed % 60;
  const speedDisplay =
    speedMins > 0 ? `${speedMins}m ${speedSecs}s` : `${displaySpeed}s`;
  const speedFinalDisplay =
    speedSeconds >= 60
      ? `${Math.floor(speedSeconds / 60)}m ${Math.round(speedSeconds % 60)}s`
      : `${Math.round(speedSeconds)}s`;

  return (
    <div className="min-h-[calc(100vh-56px)] bg-slate-50 py-8 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8 animate-fade-in-up">
          <h1 className="font-serif text-3xl text-slate-900">Pipeline Progress</h1>
          <p className="text-sm text-slate-500 mt-1">
            {allRevealed
              ? `Complete - ${passed} of ${totalSteps} steps passed${failed > 0 ? `, ${failed} failed` : ""}`
              : `Processing step ${visibleCount} of ${totalSteps}...`}
          </p>
        </div>

        {/* Step groups */}
        <div className="space-y-6">
          {STEP_GROUPS.map((group) => {
            const groupSteps = group.steps.filter((s) => stepMap.has(s));
            if (groupSteps.length === 0) return null;

            const firstIdx = flatIndexMap.get(groupSteps[0]) ?? Infinity;
            if (firstIdx >= visibleCount) return null;

            const GroupIcon = group.icon;

            return (
              <div key={group.label} className="animate-fade-in-up">
                <div className="flex items-center gap-2 mb-3">
                  <GroupIcon className="h-4 w-4 text-slate-400" />
                  <h2 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                    {group.label}
                  </h2>
                  <div className="h-px flex-1 bg-slate-200" />
                </div>

                <Card className="border-slate-200 shadow-sm overflow-hidden divide-y divide-slate-100">
                  {groupSteps.map((stepName) => {
                    const step = stepMap.get(stepName);
                    const idx = flatIndexMap.get(stepName) ?? Infinity;
                    if (!step || idx >= visibleCount) return null;

                    return (
                      <div
                        key={stepName}
                        className="px-4 py-3 flex items-start gap-3 animate-fade-in-up"
                      >
                        <div className="mt-0.5">
                          <StepIcon status={step.status} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-slate-800">
                            {STEP_LABELS[stepName] || stepName}
                          </p>
                          {step.detail && (
                            <p className="text-xs text-slate-400 mt-0.5 truncate">
                              {step.detail}
                            </p>
                          )}
                        </div>
                        {step.status === "error" && (
                          <span className="text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded bg-red-100 text-red-600">
                            error
                          </span>
                        )}
                      </div>
                    );
                  })}
                </Card>
              </div>
            );
          })}
        </div>

        {/* Loading indicator while revealing */}
        {!allRevealed && (
          <div className="flex items-center justify-center gap-2 mt-6 text-sm text-slate-400">
            <Loader2 className="h-4 w-4 animate-spin" />
            Processing...
          </div>
        )}

        {/* Summary card */}
        {showSummary && (
          <div className="mt-8 animate-fade-in-up">
            {/* Conflict warning */}
            {pipelineResult.conflict_warning && (
              <div className="mb-4 flex items-start gap-3 px-4 py-3 rounded-lg bg-amber-50 border border-amber-200">
                <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-semibold text-amber-800">
                    Conflict Notice
                  </p>
                  <p className="text-sm text-amber-700">
                    {pipelineResult.conflict_warning}
                  </p>
                </div>
              </div>
            )}

            <Card className="border-slate-200 shadow-lg overflow-hidden">
              <div className="px-6 py-5 bg-slate-900 text-white">
                <div className="flex items-center justify-between">
                  {/* Speed to lead */}
                  <div className="flex items-center gap-3">
                    <div className="h-12 w-12 rounded-xl bg-amber-500/20 flex items-center justify-center">
                      <Zap className="h-6 w-6 text-amber-400" />
                    </div>
                    <div>
                      <p className="text-3xl font-bold font-serif tracking-tight">
                        {allRevealed ? speedFinalDisplay : speedDisplay}
                      </p>
                      <p className="text-xs text-slate-400">
                        {uploadTimestamp ? "Total time from upload" : "Speed to Lead"}
                      </p>
                    </div>
                  </div>

                  {/* Priority */}
                  {pipelineResult.priority_score != null && (
                    <PriorityBadge score={pipelineResult.priority_score} />
                  )}
                </div>

                {/* Stats row */}
                <div className="mt-4 flex items-center gap-4 text-xs text-slate-400">
                  <span className="flex items-center gap-1">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                    {passed} passed
                  </span>
                  {failed > 0 && (
                    <span className="flex items-center gap-1">
                      <XCircle className="h-3.5 w-3.5 text-red-400" />
                      {failed} failed
                    </span>
                  )}
                </div>
              </div>

              {/* Actions */}
              <div className="px-6 py-4 bg-white flex items-center justify-between">
                {pipelineResult.matter_url ? (
                  <a
                    href={pipelineResult.matter_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 text-sm font-medium text-amber-700 hover:text-amber-800 transition-colors"
                  >
                    View in Clio
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                ) : (
                  <span />
                )}

                <Button
                  onClick={handleNewReport}
                  className="bg-amber-600 hover:bg-amber-700 text-white font-semibold shadow-sm gap-2"
                >
                  <FileUp className="h-4 w-4" />
                  Process Another Report
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </div>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
