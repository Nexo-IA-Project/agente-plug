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

export interface OnboardingStep {
  id: string;
  flow_id: string;
  position: number;
  delay_from_previous_minutes: number;
  meta_template_name: string | null;
  template_variables: Record<string, StepVariableBinding>;
  message_text: string | null;
}

export interface ProductSummary {
  id: string;
  name: string;
  hubla_id: string;
}

export interface OnboardingFlow {
  id: string;
  name: string;
  is_active: boolean;
  trigger_event_type: string;
  product: ProductSummary;
  steps_count: number;
  created_at: string;
  updated_at: string;
}

export interface CreateFlowInput {
  name: string;
  product_id: string;
  is_active?: boolean;
  trigger_event_type?: string;
}

export interface UpdateFlowInput {
  name?: string;
  product_id?: string;
  is_active?: boolean;
  trigger_event_type?: string;
}

export interface CreateStepInput {
  delay_from_previous_minutes: number;
  meta_template_name?: string;
  template_variables?: Record<string, StepVariableBinding>;
  message_text?: string;
}

export interface UpdateStepInput {
  delay_from_previous_minutes?: number;
  meta_template_name?: string | null;
  template_variables?: Record<string, StepVariableBinding>;
  message_text?: string | null;
}

export interface ReorderItem {
  id: string;
  position: number;
}
