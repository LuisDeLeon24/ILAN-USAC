export type Role = "admin" | "operator";

export type Me = {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  organization_id: string;
  organization_name: string;
};

export type Site = {
  id: string;
  name: string;
  address: string | null;
  camera_count: number;
  created_at: string;
};

export type Camera = {
  id: string;
  site_id: string;
  name: string;
  source_type: "rtsp" | "file";
  rtsp_url_masked: string | null;
  file_path: string | null;
  fps: number;
  enabled: boolean;
  loop: boolean;
  min_confidence: number;
  min_box_area: number;
  zone_count: number;
  created_at: string;
};

export type Zone = {
  id: string;
  camera_id: string;
  name: string;
  polygon: number[][];
  schedule: {
    timezone: string;
    windows: { days: string[]; start: string; end: string }[];
  };
  rule_type: "intrusion" | "after_hours" | "loitering" | "occupancy";
  rule_params: { seconds?: number; max_people?: number };
  created_at: string;
};

export type EventStatus = "new" | "in_review" | "resolved" | "false_positive";

export type EventItem = {
  id: string;
  event_type: string;
  severity: "low" | "medium" | "high" | "critical";
  status: EventStatus;
  camera_id: string | null;
  camera_name: string | null;
  sensor_id: string | null;
  sensor_name: string | null;
  occurred_at: string;
  reviewed_at: string | null;
  has_snapshot: boolean;
};

export type Exclusion = {
  id: string;
  camera_id: string;
  polygon: number[][];
  created_at: string;
};

export type DayCount = {
  date: string;
  count: number;
};

export type Metrics = {
  month_start: string;
  events_per_day: DayCount[];
  average_response_seconds: number | null;
  analyzed_minutes: number;
  rate_per_minute: number;
  currency: string;
  estimated_cost: number;
  previous_month_start: string | null;
  previous_analyzed_minutes: number | null;
  previous_estimated_cost: number | null;
};

export type UserAccount = {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  created_at: string;
};

export type SensorType = "door" | "motion" | "smoke" | "panic";

export type SensorItem = {
  id: string;
  site_id: string;
  name: string;
  sensor_type: SensorType;
  external_id: string;
  created_at: string;
};

export type AlertChannel = "whatsapp" | "telegram";

export type AlertContact = {
  id: string;
  name: string;
  channel: AlertChannel;
  phone: string | null;
  chat_id: string | null;
  enabled: boolean;
  created_at: string;
};

export type TelegramChat = {
  chat_id: string;
  label: string;
  username: string | null;
};

export type AgentMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

export type AgentConfirmation = {
  id: string;
  prompt: string;
};

export type AgentThread = {
  messages: AgentMessage[];
  confirmation: AgentConfirmation | null;
};

export type AlertLogItem = {
  id: string;
  event_id: string | null;
  event_type: string | null;
  contact_name: string | null;
  provider: string;
  status: "sent" | "failed" | "suppressed";
  detail: string | null;
  is_test: boolean;
  created_at: string;
};
