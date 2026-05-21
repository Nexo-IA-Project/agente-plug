export type StepVariableSource =
  | "customer_name"
  | "product_name"
  | "contact_phone"
  | "contact_email"
  | "static";

export interface StepVariableBinding {
  source: StepVariableSource;
  value?: string;
}

export interface FollowupStep {
  id: string;
  flow_id: string;
  position: number;
  delay_from_purchase_hours: number;
  meta_template_name: string | null;
  template_variables: Record<string, StepVariableBinding>;
  message_text: string | null;
}

export interface CourseSummary {
  id: string;
  name: string;
  hubla_id: string;
}

export interface FollowupFlow {
  id: string;
  name: string;
  is_active: boolean;
  course: CourseSummary;
  steps_count: number;
  created_at: string;
  updated_at: string;
}

export interface CreateFlowInput {
  name: string;
  course_id: string;
  is_active?: boolean;
}

export interface UpdateFlowInput {
  name?: string;
  course_id?: string;
  is_active?: boolean;
}

export interface CreateStepInput {
  delay_from_purchase_hours: number;
  meta_template_name?: string;
  template_variables?: Record<string, StepVariableBinding>;
  message_text?: string;
}

export interface UpdateStepInput {
  delay_from_purchase_hours?: number;
  meta_template_name?: string | null;
  template_variables?: Record<string, StepVariableBinding>;
  message_text?: string | null;
}

export interface ReorderItem {
  id: string;
  position: number;
}
