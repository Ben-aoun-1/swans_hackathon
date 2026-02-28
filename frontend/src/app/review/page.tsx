"use client";

import { useEffect } from "react";
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
  Info,
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
import type { ExtractionResult, FieldExtraction } from "@/lib/types";

const ROLE_STYLES = {
  plaintiff: { color: "bg-blue-100 text-blue-800 border-blue-300", label: "PLAINTIFF" },
  defendant: { color: "bg-red-100 text-red-800 border-red-300", label: "DEFENDANT" },
  witness: { color: "bg-gray-100 text-gray-700 border-gray-300", label: "WITNESS" },
  other: { color: "bg-slate-100 text-slate-700 border-slate-300", label: "OTHER" },
} as const;

/** Returns CSS classes for a FieldExtraction's confidence/source status */
function fieldStyle(fe: FieldExtraction | undefined): string {
  if (!fe) return "";
  if (fe.confidence === "low") return "border-l-4 border-l-amber-400 bg-amber-50/50";
  if (fe.confidence === "medium") return "border-l-4 border-l-amber-300 bg-amber-50/30";
  if (fe.source === "inferred") return "border-l-4 border-l-blue-400 bg-blue-50/30";
  return "";
}

/** Tooltip-style note display for inferred/low-confidence fields */
function FieldNote({ fe }: { fe: FieldExtraction | undefined }) {
  if (!fe?.note) return null;
  const isInferred = fe.source === "inferred";
  return (
    <div className={`mt-1 flex items-start gap-1 text-[10px] ${isInferred ? "text-blue-600" : "text-amber-600"}`}>
      <Info className="h-3 w-3 mt-0.5 shrink-0" />
      <span>{fe.note}</span>
    </div>
  );
}

export default function ReviewPage() {
  const router = useRouter();
  const { toast } = useToast();
  const { extraction, pdfBlobUrl, pipelineStatus, setPipelineStatus } =
    useExtraction();

  const { register, handleSubmit, control } = useForm<ExtractionResult>({
    defaultValues: extraction || undefined,
  });

  const { fields: partyFields } = useFieldArray({
    control,
    name: "parties",
  });

  useEffect(() => {
    if (!extraction) {
      router.push("/");
    }
  }, [extraction, router]);

  if (!extraction) return null;

  const meta = extraction.extraction_metadata;
  const lowCount = meta?.low_confidence_fields?.length ?? 0;
  const inferredCount = meta?.fields_inferred ?? 0;

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
      {/* Confidence/metadata banner */}
      {(lowCount > 0 || inferredCount > 0) && (
        <div className="bg-amber-50 border-b border-amber-200 px-6 py-3 flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-amber-800">
              {lowCount > 0 && (
                <span>{lowCount} low-confidence field{lowCount !== 1 ? "s" : ""}</span>
              )}
              {lowCount > 0 && inferredCount > 0 && <span> &middot; </span>}
              {inferredCount > 0 && (
                <span className="text-blue-700">{inferredCount} inferred field{inferredCount !== 1 ? "s" : ""}</span>
              )}
              <span className="font-normal text-amber-700"> — review highlighted fields below</span>
            </p>
            {meta?.low_confidence_fields && meta.low_confidence_fields.length > 0 && (
              <p className="text-xs text-amber-600 mt-1">
                <span className="font-medium">Low confidence:</span>{" "}
                {meta.low_confidence_fields.join(", ")}
              </p>
            )}
            {meta?.form_type && (
              <p className="text-xs text-gray-500 mt-1">
                Form: {meta.form_type} &middot; {meta.total_pages} page{meta.total_pages !== 1 ? "s" : ""}
                {meta.is_amended && <span className="text-red-600 font-semibold"> &middot; AMENDED</span>}
              </p>
            )}
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
                    <div>
                      <Label className="text-xs font-medium text-gray-600">Report Number</Label>
                      <Input {...register("report_number")} className="mt-1" />
                    </div>
                    <div>
                      <Label className="text-xs font-medium text-gray-600">Accident Date</Label>
                      <Input {...register("accident_date")} type="date" className="mt-1" />
                    </div>
                    <div>
                      <Label className="text-xs font-medium text-gray-600">Accident Time</Label>
                      <Input {...register("accident_time")} type="time" className="mt-1" />
                    </div>
                  </div>

                  <div>
                    <Label className="text-xs font-medium text-gray-600">Accident Location</Label>
                    <Input
                      {...register("accident_location")}
                      placeholder="Full address or intersection"
                      className="mt-1"
                    />
                  </div>

                  <div>
                    <Label className="text-xs font-medium text-gray-600">Accident Description</Label>
                    <Textarea {...register("accident_description")} rows={3} className="mt-1" />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label className="text-xs font-medium text-gray-600">Weather Conditions</Label>
                      <Input {...register("weather_conditions")} className="mt-1" />
                    </div>
                    <div>
                      <Label className="text-xs font-medium text-gray-600">Number of Vehicles</Label>
                      <Input {...register("number_of_vehicles", { valueAsNumber: true })} type="number" className="mt-1" />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label className="text-xs font-medium text-gray-600">Reporting Officer</Label>
                      <Input {...register("reporting_officer_name")} className="mt-1" />
                    </div>
                    <div>
                      <Label className="text-xs font-medium text-gray-600">Badge Number</Label>
                      <Input {...register("reporting_officer_badge")} className="mt-1" />
                    </div>
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
                  const party = extraction.parties[idx];
                  if (!party) return null;

                  const roleValue = party.role?.value || "other";
                  const style = ROLE_STYLES[roleValue];
                  const displayName = party.full_name?.value || `Party ${idx + 1}`;

                  return (
                    <Card key={field.id} className="overflow-hidden">
                      <CardHeader className="pb-3 bg-gray-50/50">
                        <div className="flex items-center justify-between">
                          <CardTitle className="text-sm font-medium">
                            {displayName}
                            {party.vehicle_number && (
                              <span className="ml-2 text-xs text-gray-400 font-normal">
                                Vehicle {party.vehicle_number}
                              </span>
                            )}
                          </CardTitle>
                          <div className="flex items-center gap-2">
                            {party.role?.source === "inferred" && (
                              <Badge variant="outline" className="text-[10px] bg-blue-50 text-blue-600 border-blue-200">
                                INFERRED
                              </Badge>
                            )}
                            <Badge
                              variant="outline"
                              className={`text-[10px] font-bold ${style.color}`}
                            >
                              {style.label}
                            </Badge>
                          </div>
                        </div>
                        <FieldNote fe={party.role} />
                      </CardHeader>
                      <CardContent className="pt-4 space-y-4">
                        {/* Identity */}
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <Label className="text-xs font-medium text-gray-600">Full Name</Label>
                            <Input
                              {...register(`parties.${idx}.full_name.value`)}
                              className={`mt-1 ${fieldStyle(party.full_name)}`}
                            />
                            <FieldNote fe={party.full_name} />
                          </div>
                          <div>
                            <Label className="text-xs font-medium text-gray-600">Date of Birth</Label>
                            <Input
                              {...register(`parties.${idx}.date_of_birth`)}
                              type="date"
                              className="mt-1"
                            />
                          </div>
                        </div>

                        <div>
                          <Label className="text-xs font-medium text-gray-600">Address</Label>
                          <Input {...register(`parties.${idx}.address`)} className="mt-1" />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <Label className="text-xs font-medium text-gray-600">Phone</Label>
                            <Input {...register(`parties.${idx}.phone`)} className="mt-1" />
                          </div>
                          <div>
                            <Label className="text-xs font-medium text-gray-600">Driver License</Label>
                            <Input {...register(`parties.${idx}.driver_license`)} className="mt-1" />
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
                              <Input {...register(`parties.${idx}.vehicle_year`)} className="mt-1" />
                            </div>
                            <div>
                              <Label className="text-xs text-gray-600">Make</Label>
                              <Input {...register(`parties.${idx}.vehicle_make`)} className="mt-1" />
                            </div>
                            <div>
                              <Label className="text-xs text-gray-600">Model</Label>
                              <Input {...register(`parties.${idx}.vehicle_model`)} className="mt-1" />
                            </div>
                            <div>
                              <Label className="text-xs text-gray-600">Color</Label>
                              <Input
                                {...register(`parties.${idx}.vehicle_color.value`)}
                                className={`mt-1 ${fieldStyle(party.vehicle_color)}`}
                              />
                              <FieldNote fe={party.vehicle_color} />
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
                              <Label className="text-xs text-gray-600">Company</Label>
                              <Input
                                {...register(`parties.${idx}.insurance_company.value`)}
                                className={`mt-1 ${fieldStyle(party.insurance_company)}`}
                              />
                              <FieldNote fe={party.insurance_company} />
                            </div>
                            <div>
                              <Label className="text-xs text-gray-600">Policy Number</Label>
                              <Input
                                {...register(`parties.${idx}.insurance_policy_number.value`)}
                                className={`mt-1 ${fieldStyle(party.insurance_policy_number)}`}
                              />
                              <FieldNote fe={party.insurance_policy_number} />
                            </div>
                          </div>
                        </div>

                        {/* Injuries */}
                        <div>
                          <Label className="text-xs font-medium text-gray-600">Injuries</Label>
                          <Textarea
                            {...register(`parties.${idx}.injuries.value`)}
                            rows={2}
                            className={`mt-1 ${fieldStyle(party.injuries)}`}
                          />
                          <FieldNote fe={party.injuries} />
                        </div>

                        {/* Occupants */}
                        {party.occupants && party.occupants.length > 0 && (
                          <>
                            <Separator />
                            <div>
                              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                                Occupants ({party.occupants.length})
                              </p>
                              <div className="space-y-2">
                                {party.occupants.map((occ, occIdx) => (
                                  <div key={occIdx} className="flex items-center gap-3 text-sm bg-gray-50 rounded px-3 py-2">
                                    <Badge variant="outline" className="text-[10px]">{occ.role}</Badge>
                                    <span className="font-medium">{occ.full_name || "Unknown"}</span>
                                    {occ.injuries && (
                                      <span className="text-xs text-gray-500">— {occ.injuries}</span>
                                    )}
                                  </div>
                                ))}
                              </div>
                            </div>
                          </>
                        )}
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
