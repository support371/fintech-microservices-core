/**
 * config.ts — Centralised runtime configuration with strict production guards.
 * APP_MODE: 'mock' | 'staging' | 'production'
 */

export type AppMode = 'mock' | 'staging' | 'production';

export type AppConfig = {
  env: string;
  appMode: AppMode;
  mockMode: boolean;                  // true only in 'mock' mode
  cronSecret: string;
  bankingWebhookSecret: string;
  complianceServiceUrl: string;
  auditServiceUrl: string;
  cardProviderApiKey: string;
  converterServiceSecret: string;
  databaseUrl: string;
  sentryDsn: string;
  logLevel: 'debug' | 'info' | 'warn' | 'error';
};

let cached: AppConfig | null = null;

function required(key: string): string {
  const v = process.env[key];
  if (!v || v.trim() === '') {
    throw new Error(`[config] Required env var missing: ${key}`);
  }
  return v.trim();
}

function optional(key: string, fallback = ''): string {
  return (process.env[key] || fallback).trim();
}

export function getConfig(): AppConfig {
  if (cached) return cached;

  const rawMode = optional('APP_MODE', 'mock').toLowerCase();
  const appMode: AppMode =
    rawMode === 'production' ? 'production'
    : rawMode === 'staging' ? 'staging'
    : 'mock';

  const mockMode = appMode === 'mock';

  // ── Production guards ──────────────────────────────────────────────────────
  if (appMode === 'production') {
    if (process.env.NEXT_PUBLIC_MOCK_MODE === 'true') {
      throw new Error('[config] NEXT_PUBLIC_MOCK_MODE must be false in production');
    }

    // Hard-require secrets in production
    required('BANKING_WEBHOOK_SECRET');
    required('CRON_SECRET');
    required('CARD_PROVIDER_API_KEY');
    required('CONVERTER_SERVICE_SECRET');
  }

  const env = optional('VERCEL_ENV', optional('NODE_ENV', 'development'));

  cached = {
    env,
    appMode,
    mockMode,
    cronSecret: optional('CRON_SECRET'),
    bankingWebhookSecret: optional('BANKING_WEBHOOK_SECRET'),
    complianceServiceUrl: optional('COMPLIANCE_SERVICE_URL', 'http://compliance-service:8001'),
    auditServiceUrl: optional('AUDIT_SERVICE_URL', 'http://audit-service:8002'),
    cardProviderApiKey: optional('CARD_PROVIDER_API_KEY'),
    converterServiceSecret: optional('CONVERTER_SERVICE_SECRET'),
    databaseUrl: optional('DATABASE_URL', './gem-atr.db'),
    sentryDsn: optional('SENTRY_DSN'),
    logLevel: (optional('LOG_LEVEL', 'info') as AppConfig['logLevel']) || 'info',
  };

  return cached;
}

/** Reset cached config — used in tests */
export function _resetConfigCache(): void {
  cached = null;
}

export function isMockMode(): boolean {
  return getConfig().mockMode;
}

export function isProduction(): boolean {
  return getConfig().appMode === 'production';
}
