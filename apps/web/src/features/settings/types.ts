export interface AccountSettings {
  chatnexo_base_url: string;
  chatnexo_api_key: string;
  chatnexo_account_id: number;
  chatnexo_inbox_id: number;
  hubla_webhook_secret: string;
  meta_api_key: string;
  meta_waba_id: string;
  meta_app_id: string;
  alert_whatsapp_target?: string | null;
  idle_ping_minutes: number;
  idle_close_minutes: number;
  intent_confidence_threshold: number;
  message_buffer_wait_seconds: number;
  refund_deadline_days: number;
  welcome_d1_delay_hours: number;
  ai_memory_messages: number;
  // Message Buffer
  message_buffer_enabled: boolean;
  message_buffer_outgoing_url?: string | null;
  message_buffer_api_key?: string | null;
  message_buffer_tenant_id?: string | null;
}

export type AccountSettingsPatch = Partial<AccountSettings>;

// ── Platform / Core config (global, não pertence ao tenant) ──

export interface PlatformSmtpConfig {
  host: string;
  port: number;
  use_tls: boolean;
  username: string;
  from_name: string;
  from_email: string;
  has_password: boolean;
}

export interface PlatformConfig {
  openai_api_key: string; // mascarado quando configurado
  openai_configured: boolean;
  smtp: PlatformSmtpConfig;
}

export interface PlatformSmtpInput {
  host: string;
  port: number;
  use_tls: boolean;
  username: string;
  password?: string | null;
  from_name: string;
  from_email: string;
}

export interface PlatformConfigInput {
  openai_api_key?: string | null;
  smtp?: PlatformSmtpInput;
}
