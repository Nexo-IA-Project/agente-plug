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

export interface LeadDetail extends Lead {
  events: LeadEvent[];
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
