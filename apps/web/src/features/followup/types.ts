export interface FollowupFlow {
  id: string;
  account_id: string;
  name: string;
  product_tags: string[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface FollowupStep {
  id: string;
  flow_id: string;
  position: number;
  delay_from_purchase_hours: number;
  meta_template_name: string;
  template_variables: Record<string, string>;
  created_at: string;
}

export interface CreateFlowDto {
  name: string;
  product_tags: string[];
}

export interface UpdateFlowDto {
  name?: string;
  product_tags?: string[];
  is_active?: boolean;
}

export interface CreateStepDto {
  position: number;
  delay_from_purchase_hours: number;
  meta_template_name: string;
  template_variables: Record<string, string>;
}

export interface UpdateStepDto {
  position?: number;
  delay_from_purchase_hours?: number;
  meta_template_name?: string;
  template_variables?: Record<string, string>;
}

export interface ReorderItem {
  id: string;
  position: number;
}
