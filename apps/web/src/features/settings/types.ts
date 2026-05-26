export interface AccountSettings {
  chatnexo_base_url: string;
  chatnexo_api_key: string;
  hubla_webhook_secret: string;
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
  ai_memory_messages: number;
}

export type AccountSettingsPatch = Partial<AccountSettings>;
