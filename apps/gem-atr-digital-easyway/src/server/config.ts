export type AppConfig = {
  env: string;
  mockMode: boolean;
  cronSecret: string;
  bankingWebhookSecret: string;
};

let cached: AppConfig | null = null;

export function getConfig(): AppConfig {
  if (cached) return cached;

  const env = process.env.VERCEL_ENV || process.env.NODE_ENV || 'development';
  const mockMode = process.env.NEXT_PUBLIC_MOCK_MODE === 'true';

  if (process.env.VERCEL_ENV === 'production' && mockMode) {
    throw new Error('Unsafe configuration: NEXT_PUBLIC_MOCK_MODE must be false in production.');
  }

  cached = {
    env,
    mockMode,
    cronSecret: process.env.CRON_SECRET || '',
    bankingWebhookSecret: process.env.BANKING_WEBHOOK_SECRET || '',
  };

  return cached;
}
