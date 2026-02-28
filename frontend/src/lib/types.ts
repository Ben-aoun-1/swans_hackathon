export interface FieldExtraction<T = string> {
  value: T | null;
  confidence: "high" | "medium" | "low";
  source: "explicit" | "inferred" | "not_found";
  note: string | null;
}

export interface OccupantInfo {
  full_name: string | null;
  vehicle_number: number | null;
  role: "driver" | "passenger" | "pedestrian" | "other";
  injuries: string | null;
}

export interface PartyInfo {
  // Fields with confidence tracking
  role: FieldExtraction<"plaintiff" | "defendant" | "witness" | "other">;
  full_name: FieldExtraction<string>;
  vehicle_color: FieldExtraction<string>;
  insurance_company: FieldExtraction<string>;
  insurance_policy_number: FieldExtraction<string>;
  injuries: FieldExtraction<string>;

  // Plain fields
  address: string | null;
  date_of_birth: string | null;
  phone: string | null;
  driver_license: string | null;
  vehicle_year: string | null;
  vehicle_make: string | null;
  vehicle_model: string | null;
  citation_issued: string | null;

  // Vehicle section mapping
  vehicle_number: number | null;

  // Occupants
  occupants: OccupantInfo[];
}

export interface ExtractionMetadata {
  form_type: string | null;
  total_pages: number;
  fields_extracted: number;
  fields_inferred: number;
  fields_not_found: number;
  low_confidence_fields: string[];
  is_amended: boolean;
  review_date: string | null;
  filing_info: string | null;
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
  extraction_metadata: ExtractionMetadata;
  confidence_notes: string | null; // Computed on backend for backward compat
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
