export interface Lead {
  id: string;
  hubla_subscription_id: string;
  payer_phone: string;
  payer_name: string;
  payer_email: string;
  payer_document: string | null;
  hubla_product_id: string;
  product_name: string;
  offer_name: string | null;
  amount_total_cents: number | null;
  payment_method: string | null;
  subscription_status: string;
  utm_source: string | null;
  utm_campaign: string | null;
  first_seen_at: string;
  activated_at: string | null;
  last_event_at: string;
  last_event_type: string;
}

export interface LeadEvent {
  id: string;
  event_type: string;
  received_at: string;
  payer_phone: string;
  product_name: string;
}

export type FollowupStepStatus = "sent" | "pending" | "failed" | "cancelled";

export interface FollowupStepDetail {
  id: string;
  position: number;
  template_name: string | null;
  message_text: string | null;
  status: FollowupStepStatus;
  delay_from_previous_minutes: number;
  scheduled_for: string | null;   // ISO datetime, quando vai disparar
  sent_at: string | null;          // ISO datetime, quando foi enviado
  failure_reason: string | null;
  rendered_preview: string | null; // primeiros ~80 chars do conteúdo renderizado
}

export interface FollowupEnrollmentDetail {
  id: string;
  flow_id: string;
  flow_name: string;
  product_name: string;
  trigger_event_type: string;       // ex: subscription.activated
  enrolled_at: string;               // ISO datetime
  steps: FollowupStepDetail[];
}

export interface LeadDetail extends Lead {
  events: LeadEvent[];
  enrollments: FollowupEnrollmentDetail[];
  chatnexo_conversation_url: string | null;
}

export interface LeadListResponse {
  items: Lead[];
  total: number;
  page: number;
  page_size: number;
}

export interface LeadFilters {
  product_id?: string;
  status?: string;
  utm_source?: string;
  date_from?: string; // ISO datetime string
  date_to?: string;   // ISO datetime string
  page?: number;
  page_size?: number;
}
