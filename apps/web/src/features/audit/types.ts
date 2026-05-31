export interface AuditEventItem {
  id: string;
  user_name: string | null;
  user_email: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  ip_address: string | null;
  geo_city: string | null;
  geo_country: string | null;
  geo_region: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface AuditEventListResponse {
  items: AuditEventItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface AuditFilters {
  user_id?: string;
  action?: string;
  resource_type?: string;
  exclude_auth?: boolean;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}
