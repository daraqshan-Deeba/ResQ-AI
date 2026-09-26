export interface RiskScore {
  score: number;
  level: string;
  rainfall_intensity_pct: number;
  drainage_capacity_pct: number;
}

export interface WeatherSummary {
  temp_c: number;
  condition: string;
  rain_mm_last_hour: number;
  alert_active: boolean;
  alert_headline?: string | null;
}

export interface TrafficIncident {
  id: string;
  type: "accident" | "construction" | "congestion" | "road_closure" | "community_report";
  title: string;
  description: string;
  lat?: number | null;
  lon?: number | null;
  distance_km?: number | null;
  severity: "low" | "moderate" | "high";
  source: string;
  verified: boolean;
}

export interface TrafficOverview {
  congestion_level: "light" | "moderate" | "heavy" | "unknown";
  incident_count: number;
  incidents: TrafficIncident[];
  radius_km: number;
  lat: number;
  lon: number;
  sources_used: string[];
}

export interface Hospital {
  name: string;
  lat: number;
  lon: number;
  distance_km?: number | null;
  address?: string | null;
  facility_type?: string | null;
  phone?: string | null;
  source?: string | null;
}

export interface Shelter {
  id: string;
  name: string;
  capacity: number;
  occupied: number;
  address?: string | null;
  lat?: number | null;
  lon?: number | null;
  source?: string | null;
}

export interface Report {
  id: string;
  area: string;
  message: string;
  verified: boolean;
  created_at: string;
  lat?: number | null;
  lon?: number | null;
  attachment_url?: string | null;
  attachment_mime?: string | null;
}

export interface UserProfile {
  id: string;
  email: string;
  full_name?: string | null;
  display_name?: string | null;
  avatar_url?: string | null;
  phone?: string | null;
  phone_country_dial?: string | null;
  phone_national?: string | null;
  city?: string | null;
  emergency_contact_name?: string | null;
  emergency_contact_phone?: string | null;
  emergency_contact_country_dial?: string | null;
  emergency_contact_national?: string | null;
  emergency_contact_relation?: string | null;
  registration_complete?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface KnowledgeAsset {
  id: string;
  title: string;
  content_text: string;
  asset_type: string;
  storage_url?: string | null;
  mime_type?: string | null;
  area?: string | null;
  similarity?: number | null;
  created_at?: string;
}

export interface SosResponse {
  event_id?: string | null;
  status: "recorded" | "degraded";
  notification_status: string;
  maps_link: string;
  message: string;
  emergency_contact_phone?: string | null;
  sms_status?: "sent" | "failed" | "skipped";
}

export interface CommunityInsight {
  id: string;
  area: string;
  message: string;
  verified: boolean;
  source: "community_report" | "knowledge_asset";
  attachment_url?: string | null;
  similarity?: number | null;
  created_at?: string | null;
}

export interface AssessmentResult {
  emergency_level: string;
  whats_happening?: string;
  triage?: { category: string; explanation?: string };
  action_plan?: {
    explanation?: string;
    immediate_actions?: string[];
    safety_warnings?: string[];
    when_to_seek_help?: string[];
    questions_to_ask_user?: string[];
    emergency_contacts?: string[];
  };
  weather?: {
    level?: string | null;
    score?: number | null;
    condition?: string | null;
    temp_c?: number | null;
    status?: string;
  };
  confidence?: {
    confidence_level?: string;
    overall_confidence?: number;
    limiting_factor?: string;
    triage_state?: string;
    weather_state?: string;
    guidance_state?: string;
  };
  hospitals?: Hospital[];
  immediate_first_aid?: string[];
  what_not_to_do?: string[];
  call_these_services?: string[];
  things_to_carry?: string[];
  service_status?: Record<string, string>;
  source_labels?: Record<string, string>;
  community_insights?: CommunityInsight[];
  understood_as?: string | null;
  retrieved_examples?: Array<{ example?: string; category?: string; score?: number }>;
  citations?: Array<{ source?: string; label?: string }>;
}
