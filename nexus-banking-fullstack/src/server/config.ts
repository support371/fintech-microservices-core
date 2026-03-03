/**
 * Environment configuration with production safety guards.
 *
 * Mock mode allows local development without real Supabase or provider keys.
 * Setting NEXT_PUBLIC_MOCK_MODE=true in a Vercel production deployment will
 * cause the process to exit immediately.
 */

const isVercelProduction = process.env.VERCEL_ENV === "production";
const isMockMode = process.env.NEXT_PUBLIC_MOCK_MODE === "true";

if (isVercelProduction && isMockMode) {
  console.error(
    "FATAL: NEXT_PUBLIC_MOCK_MODE=true is not allowed in Vercel production. " +
      "Set it to false or remove it entirely."
  );
  process.exit(1);
}

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value && !isMockMode) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value ?? "";
}

export const config = {
  mockMode: isMockMode,
  appName: process.env.NEXT_PUBLIC_APP_NAME ?? "Nexus Financial",

  supabase: {
    url: process.env.NEXT_PUBLIC_SUPABASE_URL ?? "",
    anonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "",
    serviceRoleKey: requireEnv("SUPABASE_SERVICE_ROLE_KEY"),
  },

  webhookSecrets: {
    banking: requireEnv("BANKING_WEBHOOK_SECRET"),
    kyc: requireEnv("KYC_WEBHOOK_SECRET"),
    cards: requireEnv("CARD_WEBHOOK_SECRET"),
  },

  cronSecret: requireEnv("CRON_SECRET"),

  providers: {
    email: requireEnv("EMAIL_PROVIDER_KEY"),
    card: requireEnv("CARD_PROVIDER_KEY"),
    exchange: requireEnv("EXCHANGE_PROVIDER_KEY"),
    kyc: requireEnv("KYC_PROVIDER_KEY"),
    banking: requireEnv("BANKING_PROVIDER_KEY_US"),
  },
} as const;
