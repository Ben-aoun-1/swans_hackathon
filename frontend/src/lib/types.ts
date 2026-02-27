export interface PartyInfo {
  role: "plaintiff" | "defendant" | "witness" | "other";
  full_name: string | null;
  address: string | null;
  date_of_birth: string | null;
  phone: string | null;
  driver_license: string | null;
  vehicle_year: string | null;
  vehicle_make: string | null;
  vehicle_model: string | null;
  vehicle_color: string | null;
  insurance_company: string | null;
  insurance_policy_number: string | null;
  injuries: string | null;
  citation_issued: string | null;
}

export interface ExtractionResult {
  report_number: string | null;
  accident_date: string | null;
  accident_time: string | null;
  accident_location: string | null;
  accident_description: string | null;
  weather_conditions: string | null;
  road_conditions: string | null;
  number_of_vehicles: number | null;
  reporting_officer_name: string | null;
  reporting_officer_badge: string | null;
  parties: PartyInfo[];
  confidence_notes: string | null;
}

export type PipelineStatus =
  | "idle"
  | "uploading"
  | "extracting"
  | "reviewing"
  | "pushing_to_clio"
  | "generating_document"
  | "sending_email"
  | "complete"
  | "error";
