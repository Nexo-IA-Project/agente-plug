export interface UnmappedProduct {
  hubla_product_id: string;
  product_name: string | null;
  affected_leads: number;
  first_seen: string | null;
  last_seen: string | null;
}

export interface ResolveUnmappedInput {
  hubla_product_id: string;
  product_id: string;
}

export interface ResolveUnmappedResponse {
  affected_leads: number;
}

export type ReprocessScheduleMode = "from_now" | "original";

export interface ReprocessUnmappedInput {
  hubla_product_id: string;
  schedule_mode: ReprocessScheduleMode;
}

export interface ReprocessUnmappedResponse {
  enqueued: number;
}
