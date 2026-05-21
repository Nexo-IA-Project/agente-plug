export interface AccountSettings {
  chatnexo_base_url: string;
  chatnexo_api_key: string;
  hubla_webhook_secret: string;
  cademi_api_url: string;
  cademi_api_key: string;
  cademi_max_retries: number;
  cademi_retry_base_seconds: number;
  openai_api_key: string;
  meta_api_key: string;
  meta_waba_id: string;
  meta_app_id: string;
  idle_ping_minutes: number;
  idle_close_minutes: number;
  intent_confidence_threshold: number;
  message_buffer_wait_seconds: number;
  refund_deadline_days: number;
  welcome_d1_delay_hours: number;
  loja_express_d1_delay_hours: number;
  loja_express_d3_delay_hours: number;
  loja_express_d5_delay_hours: number;
  loja_express_d7_delay_hours: number;
}

export type AccountSettingsPatch = Partial<AccountSettings>;
