"use client";

import { useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useForm, useFieldArray } from "react-hook-form";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Send,
  User,
  Car,
  Shield,
  FileText,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useExtraction } from "@/lib/ExtractionContext";
import { approveAndPush } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { StatusTimeline } from "@/components/StatusTimeline";
import type { ExtractionResult } from "@/lib/types";

const ROLE_STYLES = {
  plaintiff: { color: "bg-blue-100 text-blue-800 border-blue-300", label: "PLAINTIFF" },
  defendant: { color: "bg-red-100 text-red-800 border-red-300", label: "DEFENDANT" },
  witness: { color: "bg-gray-100 text-gray-700 border-gray-300", label: "WITNESS" },
  other: { color: "bg-slate-100 text-slate-700 border-slate-300", label: "OTHER" },
} as const;

function isFieldFlagged(fieldName: string, confidenceNotes: string | null): boolean {
  if (!confidenceNotes) return false;
  const lower = confidenceNotes.toLowerCase();
  const keywords = fieldName.toLowerCase().split("_");
  return keywords.some((kw) => kw.length > 2 && lower.includes(kw));
}

function FlaggedInput({
  label,
  fieldName,
  register,
  registerPath,
  confidenceNotes,
  type = "text",
  placeholder,
}: {
  label: string;
  fieldName: string;
  register: ReturnType<typeof useForm<ExtractionResult>>["register"];
  registerPath: Parameters<typeof register>[0];
  confidenceNotes: string | null;
  type?: string;
  placeholder?: string;
}) {
  const flagged = isFieldFlagged(fieldName, confidenceNotes);
  return (
    <div>
      <Label className="text-xs font-medium text-gray-600">{label}</Label>
      <Input
        {...register(registerPath)}
        type={type}
        placeholder={placeholder}
        className={`mt-1 ${flagged ? "border-l-4 border-l-amber-400 bg-amber-50/50" : ""}`}
      />
    </div>
  );
}

export default function ReviewPage() {
  const router = useRouter();
  const { toast } = useToast();
  const { extraction, pdfBlobUrl, pipelineStatus, setPipelineStatus } =
    useExtraction();

  const { register, handleSubmit, control, watch } = useForm<ExtractionResult>({
    defaultValues: extraction || undefined,
  });

  const { fields: partyFields } = useFieldArray({
    control,
    name: "parties",
  });

  const confidenceNotes = watch("confidence_notes");

  // Count flagged concerns from confidence notes
  const flagCount = useMemo(() => {
    if (!confidenceNotes) return 0;
    // Count numbered items like "1)" or "- " patterns
    const matches = confidenceNotes.match(/\d+\)|^- /gm);
    return matches ? matches.length : 1;
  }, [confidenceNotes]);

  useEffect(() => {
    if (!extraction) {
      router.push("/");
    }
  }, [extraction, router]);

  if (!extraction) return null;

  const onSubmit = async (data: ExtractionResult) => {
    try {
      setPipelineStatus("pushing_to_clio");
      await approveAndPush(data);
      setPipelineStatus("complete");
      toast({ title: "Success", description: "Data pushed to Clio successfully." });
    } catch {
      setPipelineStatus("error");
      toast({
        variant: "destructive",
        title: "Push Failed",
        description: "Could not push data to Clio. Check the backend logs.",
      });
    }
  };

  return (
    <div className="h-[calc(100vh-73px)] flex flex-col">
      {/* Confidence notes banner */}
      {confidenceNotes && (
        <div className="bg-amber-50 border-b border-amber-200 px-6 py-3 flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-amber-800">
              AI flagged {flagCount} uncertaint{flagCount === 1 ? "y" : "ies"} — review highlighted fields
            </p>
            <p className="text-xs text-amber-700 mt-1 whitespace-pre-wrap">
              {confidenceNotes}
            </p>
          </div>
        </div>
      )}

      {/* Main two-panel layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left panel — PDF viewer */}
        <div className="w-[45%] border-r bg-gray-100 flex flex-col">
          <div className="px-4 py-2 bg-white border-b flex items-center gap-2">
            <FileText className="h-4 w-4 text-gray-500" />
            <span className="text-sm font-medium text-gray-700">
              Original Report
            </span>
          </div>
          {pdfBlobUrl ? (
            <object
              data={pdfBlobUrl}
              type="application/pdf"
              className="flex-1 w-full"
            >
              <div className="flex items-center justify-center h-full text-gray-500 text-sm p-8 text-center">
                <p>
                  PDF preview not supported in this browser.
                  <br />
                  <a
                    href={pdfBlobUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 underline"
                  >
                    Open PDF in new tab
                  </a>
                </p>
              </div>
            </object>
          ) : (
            <div className="flex-1 flex items-center justify-center text-gray-400">
              No PDF loaded
            </div>
          )}
        </div>

        {/* Right panel — Editable form */}
        <div className="w-[55%] flex flex-col">
          <ScrollArea className="flex-1">
            <form
              id="review-form"
              onSubmit={handleSubmit(onSubmit)}
              className="p-6 space-y-6"
            >
              {/* Section 1: Incident Details */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <FileText className="h-4 w-4" />
                    Incident Details
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-3 gap-4">
                    <FlaggedInput
                      label="Report Number"
                      fieldName="report_number"
                      register={register}
                      registerPath="report_number"
                      confidenceNotes={confidenceNotes}
                    />
                    <FlaggedInput
                      label="Accident Date"
                      fieldName="accident_date"
                      register={register}
                      registerPath="accident_date"
                      confidenceNotes={confidenceNotes}
                      type="date"
                    />
                    <FlaggedInput
                      label="Accident Time"
                      fieldName="accident_time"
                      register={register}
                      registerPath="accident_time"
                      confidenceNotes={confidenceNotes}
                      type="time"
                    />
                  </div>

                  <FlaggedInput
                    label="Accident Location"
                    fieldName="accident_location"
                    register={register}
                    registerPath="accident_location"
                    confidenceNotes={confidenceNotes}
                    placeholder="Full address or intersection"
                  />

                  <div>
                    <Label className="text-xs font-medium text-gray-600">
                      Accident Description
                    </Label>
                    <Textarea
                      {...register("accident_description")}
                      rows={3}
                      className={`mt-1 ${isFieldFlagged("accident_description", confidenceNotes) ? "border-l-4 border-l-amber-400 bg-amber-50/50" : ""}`}
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <FlaggedInput
                      label="Weather Conditions"
                      fieldName="weather"
                      register={register}
                      registerPath="weather_conditions"
                      confidenceNotes={confidenceNotes}
                    />
                    <div>
                      <Label className="text-xs font-medium text-gray-600">
                        Number of Vehicles
                      </Label>
                      <Input
                        {...register("number_of_vehicles", {
                          valueAsNumber: true,
                        })}
                        type="number"
                        className="mt-1"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <FlaggedInput
                      label="Reporting Officer"
                      fieldName="officer"
                      register={register}
                      registerPath="reporting_officer_name"
                      confidenceNotes={confidenceNotes}
                    />
                    <FlaggedInput
                      label="Badge Number"
                      fieldName="badge"
                      register={register}
                      registerPath="reporting_officer_badge"
                      confidenceNotes={confidenceNotes}
                    />
                  </div>
                </CardContent>
              </Card>

              {/* Section 2: Parties */}
              <div className="space-y-4">
                <h3 className="text-base font-semibold flex items-center gap-2">
                  <User className="h-4 w-4" />
                  Parties ({partyFields.length})
                </h3>

                {partyFields.map((field, idx) => {
                  const role = extraction.parties[idx]?.role || "other";
                  const style = ROLE_STYLES[role];

                  return (
                    <Card key={field.id} className="overflow-hidden">
                      <CardHeader className="pb-3 bg-gray-50/50">
                        <div className="flex items-center justify-between">
                          <CardTitle className="text-sm font-medium">
                            {extraction.parties[idx]?.full_name || `Party ${idx + 1}`}
                          </CardTitle>
                          <Badge
                            variant="outline"
                            className={`text-[10px] font-bold ${style.color}`}
                          >
                            {style.label}
                          </Badge>
                        </div>
                      </CardHeader>
                      <CardContent className="pt-4 space-y-4">
                        {/* Identity */}
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <Label className="text-xs font-medium text-gray-600">
                              Full Name
                            </Label>
                            <Input
                              {...register(`parties.${idx}.full_name`)}
                              className="mt-1"
                            />
                          </div>
                          <div>
                            <Label className="text-xs font-medium text-gray-600">
                              Date of Birth
                            </Label>
                            <Input
                              {...register(`parties.${idx}.date_of_birth`)}
                              type="date"
                              className={`mt-1 ${isFieldFlagged("dob", confidenceNotes) ? "border-l-4 border-l-amber-400 bg-amber-50/50" : ""}`}
                            />
                          </div>
                        </div>

                        <div>
                          <Label className="text-xs font-medium text-gray-600">
                            Address
                          </Label>
                          <Input
                            {...register(`parties.${idx}.address`)}
                            className="mt-1"
                          />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <Label className="text-xs font-medium text-gray-600">
                              Phone
                            </Label>
                            <Input
                              {...register(`parties.${idx}.phone`)}
                              className="mt-1"
                            />
                          </div>
                          <div>
                            <Label className="text-xs font-medium text-gray-600">
                              Driver License
                            </Label>
                            <Input
                              {...register(`parties.${idx}.driver_license`)}
                              className="mt-1"
                            />
                          </div>
                        </div>

                        <Separator />

                        {/* Vehicle info */}
                        <div>
                          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1">
                            <Car className="h-3 w-3" /> Vehicle
                          </p>
                          <div className="grid grid-cols-4 gap-3">
                            <div>
                              <Label className="text-xs text-gray-600">Year</Label>
                              <Input
                                {...register(`parties.${idx}.vehicle_year`)}
                                className="mt-1"
                              />
                            </div>
                            <div>
                              <Label className="text-xs text-gray-600">Make</Label>
                              <Input
                                {...register(`parties.${idx}.vehicle_make`)}
                                className="mt-1"
                              />
                            </div>
                            <div>
                              <Label className="text-xs text-gray-600">Model</Label>
                              <Input
                                {...register(`parties.${idx}.vehicle_model`)}
                                className="mt-1"
                              />
                            </div>
                            <div>
                              <Label className="text-xs text-gray-600">Color</Label>
                              <Input
                                {...register(`parties.${idx}.vehicle_color`)}
                                className="mt-1"
                              />
                            </div>
                          </div>
                        </div>

                        <Separator />

                        {/* Insurance */}
                        <div>
                          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1">
                            <Shield className="h-3 w-3" /> Insurance
                          </p>
                          <div className="grid grid-cols-2 gap-4">
                            <div>
                              <Label className="text-xs text-gray-600">
                                Company
                              </Label>
                              <Input
                                {...register(
                                  `parties.${idx}.insurance_company`
                                )}
                                className="mt-1"
                              />
                            </div>
                            <div>
                              <Label className="text-xs text-gray-600">
                                Policy Number
                              </Label>
                              <Input
                                {...register(
                                  `parties.${idx}.insurance_policy_number`
                                )}
                                className="mt-1"
                              />
                            </div>
                          </div>
                        </div>

                        {/* Injuries */}
                        <div>
                          <Label className="text-xs font-medium text-gray-600">
                            Injuries
                          </Label>
                          <Textarea
                            {...register(`parties.${idx}.injuries`)}
                            rows={2}
                            className="mt-1"
                          />
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </form>
          </ScrollArea>

          {/* Sticky bottom bar */}
          <div className="border-t bg-white px-6 py-3 flex items-center justify-between shadow-[0_-2px_10px_rgba(0,0,0,0.05)]">
            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                size="sm"
                onClick={() => router.push("/")}
              >
                <ArrowLeft className="h-4 w-4 mr-1" />
                Re-extract
              </Button>
              <StatusTimeline status={pipelineStatus} />
            </div>

            <Button
              type="submit"
              form="review-form"
              size="lg"
              className="bg-[#1a1a2e] hover:bg-[#2a2a4e] text-white gap-2"
            >
              {pipelineStatus === "pushing_to_clio" ? (
                <>
                  <span className="animate-spin">
                    <Send className="h-4 w-4" />
                  </span>
                  Pushing to Clio...
                </>
              ) : pipelineStatus === "complete" ? (
                <>
                  <CheckCircle2 className="h-4 w-4" />
                  Done
                </>
              ) : (
                <>
                  <Send className="h-4 w-4" />
                  Approve &amp; Push to Clio
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
