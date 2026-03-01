"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useForm, useFieldArray } from "react-hook-form";
import {
  AlertTriangle,
  ArrowLeft,
  Send,
  User,
  Car,
  Shield,
  FileText,
  Info,
  Clock,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useExtraction } from "@/lib/ExtractionContext";
import { approveAndPush } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import type { ExtractionResult, FieldExtraction } from "@/lib/types";

const ROLE_BORDERS: Record<string, string> = {
  plaintiff: "border-l-blue-500",
  defendant: "border-l-red-500",
  witness: "border-l-slate-400",
  other: "border-l-slate-300",
};

const ROLE_BADGES: Record<string, string> = {
  plaintiff: "bg-blue-100 text-blue-800",
  defendant: "bg-red-100 text-red-800",
  witness: "bg-slate-100 text-slate-700",
  other: "bg-slate-100 text-slate-600",
};

function fieldStyle(fe: FieldExtraction | undefined): string {
  if (!fe) return "";
  if (fe.confidence === "low") return "border-l-4 border-l-amber-400 bg-amber-50/40";
  if (fe.confidence === "medium") return "border-l-4 border-l-amber-300 bg-amber-50/20";
  if (fe.source === "inferred") return "border-l-4 border-l-blue-300 bg-blue-50/20";
  return "";
}

function FieldNote({ fe }: { fe: FieldExtraction | undefined }) {
  if (!fe || (!fe.note && fe.confidence === "high")) return null;

  const pill =
    fe.confidence === "low"
      ? "bg-red-100 text-red-700"
      : fe.confidence === "medium"
        ? "bg-amber-100 text-amber-700"
        : null;

  return (
    <div className="mt-1 flex items-center gap-1.5 flex-wrap">
      {pill && (
        <span className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded-full ${pill}`}>
          {fe.confidence}
        </span>
      )}
      {fe.source === "inferred" && (
        <span className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700">
          inferred
        </span>
      )}
      {fe.note && (
        <span className="text-[10px] text-slate-500 italic flex items-center gap-1">
          <Info className="h-3 w-3 shrink-0" />
          {fe.note}
        </span>
      )}
    </div>
  );
}

function SectionHeader({ icon: Icon, title }: { icon: React.ElementType; title: string }) {
  return (
    <div className="flex items-center gap-3 mb-4">
      <div className="w-1 h-6 bg-amber-500 rounded-full" />
      <Icon className="h-4 w-4 text-slate-500" />
      <h3 className="font-serif text-lg text-slate-900">{title}</h3>
    </div>
  );
}

export default function ReviewPage() {
  const router = useRouter();
  const { toast } = useToast();
  const {
    extraction,
    pdfBlobUrl,
    pdfBase64,
    pipelineStatus,
    setPipelineStatus,
    setPipelineResult,
    uploadTimestamp,
  } = useExtraction();

  const { register, handleSubmit, control } = useForm<ExtractionResult>({
    defaultValues: extraction || undefined,
  });

  const { fields: partyFields } = useFieldArray({ control, name: "parties" });

  // Review timer
  const [reviewStart] = useState(() => Date.now());
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - reviewStart) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [reviewStart]);

  useEffect(() => {
    if (!extraction) router.push("/");
  }, [extraction, router]);

  if (!extraction) return null;

  const meta = extraction.extraction_metadata;
  const lowCount = meta?.low_confidence_fields?.length ?? 0;
  const inferredCount = meta?.fields_inferred ?? 0;
  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;
  const isPushing =
    pipelineStatus === "pushing_to_clio" ||
    pipelineStatus === "generating_document" ||
    pipelineStatus === "sending_email";

  const onSubmit = async (data: ExtractionResult) => {
    try {
      setPipelineStatus("pushing_to_clio");
      const result = await approveAndPush(data, pdfBase64, uploadTimestamp);
      setPipelineResult(result);
      setPipelineStatus("complete");
      router.push("/status");
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
    <div className="h-[calc(100vh-56px)] flex flex-col">
      {/* Confidence/metadata banner */}
      {(lowCount > 0 || inferredCount > 0) && (
        <div className="bg-amber-50/80 border-b border-amber-200 px-6 py-2.5 flex items-center gap-3">
          <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
          <p className="text-sm text-amber-800">
            {lowCount > 0 && (
              <span className="font-semibold">
                {lowCount} low-confidence field{lowCount !== 1 ? "s" : ""}
              </span>
            )}
            {lowCount > 0 && inferredCount > 0 && <span> &middot; </span>}
            {inferredCount > 0 && (
              <span className="font-semibold text-blue-700">
                {inferredCount} inferred
              </span>
            )}
            <span className="text-amber-700"> - review highlighted fields</span>
          </p>
          {meta?.form_type && (
            <p className="ml-auto text-xs text-slate-500 hidden sm:block">
              {meta.form_type} &middot; {meta.total_pages} page
              {meta.total_pages !== 1 ? "s" : ""}
              {meta.is_amended && (
                <span className="text-red-600 font-bold"> AMENDED</span>
              )}
            </p>
          )}
        </div>
      )}

      {/* Two-panel layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: PDF */}
        <div className="w-[44%] border-r border-slate-200 bg-slate-100 flex flex-col">
          <div className="px-4 py-2.5 bg-slate-800 border-b border-slate-700 flex items-center gap-2">
            <FileText className="h-4 w-4 text-slate-400" />
            <span className="text-sm font-medium text-slate-200">
              Original Report
            </span>
            {meta?.total_pages && (
              <Badge
                variant="outline"
                className="ml-auto text-[10px] bg-slate-700 text-slate-300 border-slate-600"
              >
                {meta.total_pages} pages
              </Badge>
            )}
          </div>
          {pdfBlobUrl ? (
            <object
              data={pdfBlobUrl}
              type="application/pdf"
              className="flex-1 w-full"
            >
              <div className="flex items-center justify-center h-full text-slate-500 text-sm p-8 text-center">
                <p>
                  PDF preview not available.{" "}
                  <a
                    href={pdfBlobUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-amber-600 underline"
                  >
                    Open in new tab
                  </a>
                </p>
              </div>
            </object>
          ) : (
            <div className="flex-1 flex items-center justify-center text-slate-400">
              No PDF loaded
            </div>
          )}
        </div>

        {/* Right: Form */}
        <div className="w-[56%] flex flex-col bg-white">
          <ScrollArea className="flex-1">
            <form
              id="review-form"
              onSubmit={handleSubmit(onSubmit)}
              className="p-6 space-y-8"
            >
              {/* Incident Details */}
              <div>
                <SectionHeader icon={FileText} title="Incident Details" />
                <Card className="border-slate-200 shadow-sm">
                  <CardContent className="pt-5 space-y-4">
                    <div className="grid grid-cols-3 gap-4">
                      <div>
                        <Label className="text-xs font-medium text-slate-500">
                          Report Number
                        </Label>
                        <Input {...register("report_number")} className="mt-1" />
                      </div>
                      <div>
                        <Label className="text-xs font-medium text-slate-500">
                          Accident Date
                        </Label>
                        <Input
                          {...register("accident_date")}
                          type="date"
                          className="mt-1"
                        />
                      </div>
                      <div>
                        <Label className="text-xs font-medium text-slate-500">
                          Accident Time
                        </Label>
                        <Input
                          {...register("accident_time")}
                          type="time"
                          className="mt-1"
                        />
                      </div>
                    </div>

                    <div>
                      <Label className="text-xs font-medium text-slate-500">
                        Location
                      </Label>
                      <Input
                        {...register("accident_location")}
                        placeholder="Full address or intersection"
                        className="mt-1"
                      />
                    </div>

                    <div>
                      <Label className="text-xs font-medium text-slate-500">
                        Description
                      </Label>
                      <Textarea
                        {...register("accident_description")}
                        rows={3}
                        className="mt-1"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label className="text-xs font-medium text-slate-500">
                          Weather
                        </Label>
                        <Input
                          {...register("weather_conditions")}
                          className="mt-1"
                        />
                      </div>
                      <div>
                        <Label className="text-xs font-medium text-slate-500">
                          Vehicles
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
                      <div>
                        <Label className="text-xs font-medium text-slate-500">
                          Reporting Officer
                        </Label>
                        <Input
                          {...register("reporting_officer_name")}
                          className="mt-1"
                        />
                      </div>
                      <div>
                        <Label className="text-xs font-medium text-slate-500">
                          Badge #
                        </Label>
                        <Input
                          {...register("reporting_officer_badge")}
                          className="mt-1"
                        />
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Parties */}
              <div>
                <SectionHeader icon={User} title={`Parties (${partyFields.length})`} />

                <div className="space-y-4">
                  {partyFields.map((field, idx) => {
                    const party = extraction.parties[idx];
                    if (!party) return null;

                    const roleValue = party.role?.value || "other";
                    const displayName =
                      party.full_name?.value || `Party ${idx + 1}`;

                    return (
                      <Card
                        key={field.id}
                        className={`overflow-hidden border-l-4 border-slate-200 shadow-sm ${
                          ROLE_BORDERS[roleValue] || ROLE_BORDERS.other
                        }`}
                      >
                        {/* Party header */}
                        <div className="px-5 py-3 bg-slate-50/50 border-b border-slate-100 flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-sm text-slate-800">
                              {displayName}
                            </span>
                            {party.vehicle_number && (
                              <span className="text-xs text-slate-400">
                                Vehicle {party.vehicle_number}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            {party.role?.source === "inferred" && (
                              <span className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700">
                                inferred
                              </span>
                            )}
                            <span
                              className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${
                                ROLE_BADGES[roleValue] || ROLE_BADGES.other
                              }`}
                            >
                              {roleValue}
                            </span>
                          </div>
                        </div>

                        <CardContent className="pt-4 space-y-4">
                          <FieldNote fe={party.role} />

                          {/* Identity */}
                          <div className="grid grid-cols-2 gap-4">
                            <div>
                              <Label className="text-xs text-slate-500">
                                Full Name
                              </Label>
                              <Input
                                {...register(
                                  `parties.${idx}.full_name.value`
                                )}
                                className={`mt-1 ${fieldStyle(party.full_name)}`}
                              />
                              <FieldNote fe={party.full_name} />
                            </div>
                            <div>
                              <Label className="text-xs text-slate-500">
                                Date of Birth
                              </Label>
                              <Input
                                {...register(`parties.${idx}.date_of_birth`)}
                                type="date"
                                className="mt-1"
                              />
                            </div>
                          </div>

                          <div>
                            <Label className="text-xs text-slate-500">
                              Address
                            </Label>
                            <Input
                              {...register(`parties.${idx}.address`)}
                              className="mt-1"
                            />
                          </div>

                          <div className="grid grid-cols-2 gap-4">
                            <div>
                              <Label className="text-xs text-slate-500">
                                Phone
                              </Label>
                              <Input
                                {...register(`parties.${idx}.phone`)}
                                className="mt-1"
                              />
                            </div>
                            <div>
                              <Label className="text-xs text-slate-500">
                                Driver License
                              </Label>
                              <Input
                                {...register(`parties.${idx}.driver_license`)}
                                className="mt-1"
                              />
                            </div>
                          </div>

                          <Separator className="bg-slate-100" />

                          {/* Vehicle */}
                          <div>
                            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-1.5">
                              <Car className="h-3 w-3" /> Vehicle
                            </p>
                            <div className="grid grid-cols-4 gap-3">
                              <div>
                                <Label className="text-xs text-slate-500">
                                  Year
                                </Label>
                                <Input
                                  {...register(`parties.${idx}.vehicle_year`)}
                                  className="mt-1"
                                />
                              </div>
                              <div>
                                <Label className="text-xs text-slate-500">
                                  Make
                                </Label>
                                <Input
                                  {...register(`parties.${idx}.vehicle_make`)}
                                  className="mt-1"
                                />
                              </div>
                              <div>
                                <Label className="text-xs text-slate-500">
                                  Model
                                </Label>
                                <Input
                                  {...register(`parties.${idx}.vehicle_model`)}
                                  className="mt-1"
                                />
                              </div>
                              <div>
                                <Label className="text-xs text-slate-500">
                                  Color
                                </Label>
                                <Input
                                  {...register(
                                    `parties.${idx}.vehicle_color.value`
                                  )}
                                  className={`mt-1 ${fieldStyle(party.vehicle_color)}`}
                                />
                                <FieldNote fe={party.vehicle_color} />
                              </div>
                            </div>
                          </div>

                          <Separator className="bg-slate-100" />

                          {/* Insurance */}
                          <div>
                            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2 flex items-center gap-1.5">
                              <Shield className="h-3 w-3" /> Insurance
                            </p>
                            <div className="grid grid-cols-2 gap-4">
                              <div>
                                <Label className="text-xs text-slate-500">
                                  Company
                                </Label>
                                <Input
                                  {...register(
                                    `parties.${idx}.insurance_company.value`
                                  )}
                                  className={`mt-1 ${fieldStyle(party.insurance_company)}`}
                                />
                                <FieldNote fe={party.insurance_company} />
                              </div>
                              <div>
                                <Label className="text-xs text-slate-500">
                                  Policy #
                                </Label>
                                <Input
                                  {...register(
                                    `parties.${idx}.insurance_policy_number.value`
                                  )}
                                  className={`mt-1 ${fieldStyle(party.insurance_policy_number)}`}
                                />
                                <FieldNote
                                  fe={party.insurance_policy_number}
                                />
                              </div>
                            </div>
                          </div>

                          {/* Injuries */}
                          <div>
                            <Label className="text-xs font-medium text-slate-500">
                              Injuries
                            </Label>
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
                              <Separator className="bg-slate-100" />
                              <div>
                                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2">
                                  Occupants ({party.occupants.length})
                                </p>
                                <div className="space-y-2">
                                  {party.occupants.map((occ, occIdx) => (
                                    <div
                                      key={occIdx}
                                      className="flex items-center gap-3 text-sm bg-slate-50 rounded px-3 py-2"
                                    >
                                      <Badge
                                        variant="outline"
                                        className="text-[10px]"
                                      >
                                        {occ.role}
                                      </Badge>
                                      <span className="font-medium">
                                        {occ.full_name || "Unknown"}
                                      </span>
                                      {occ.injuries && (
                                        <span className="text-xs text-slate-500">
                                          - {occ.injuries}
                                        </span>
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
              </div>
            </form>
          </ScrollArea>

          {/* Bottom bar */}
          <div className="border-t border-slate-200 bg-white px-6 py-3 flex items-center justify-between shadow-[0_-2px_12px_rgba(0,0,0,0.04)]">
            <div className="flex items-center gap-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => router.push("/")}
                className="text-slate-500 hover:text-slate-700"
              >
                <ArrowLeft className="h-4 w-4 mr-1" />
                Back
              </Button>
              <div className="flex items-center gap-1.5 text-xs text-slate-400">
                <Clock className="h-3.5 w-3.5" />
                <span>
                  {mins}m {secs.toString().padStart(2, "0")}s
                </span>
              </div>
            </div>

            <Button
              type="submit"
              form="review-form"
              size="lg"
              disabled={isPushing}
              className="bg-amber-600 hover:bg-amber-700 text-white font-semibold shadow-md shadow-amber-600/20 gap-2 px-6"
            >
              {isPushing ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Processing...
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
