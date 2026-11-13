/**
 * Environment configuration with production safety guards.
 *
 * Mock mode allows local development without real Supabase or provider keys.
 * Setting NEXT_PUBLIC_MOCK_MODE=true in a Vercel production deployment will
 * cause the process to exit immediately.
 *
 * Config values are lazy — only resolved when accessed at request time,
 * not during the Next.js build phase.
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

function env(name: string): string {
  const value = process.env[name];
  if (!value && !isMockMode) {
    throw new Error(`Missing required environment variable: ${name}`);
  }
  return value ?? "";
}

export const config = {
  mockMode: isMockMode,
  appName: process.env.NEXT_PUBLIC_APP_NAME ?? "Nexus Financial",

  get supabase() {
    return {
      url: process.env.NEXT_PUBLIC_SUPABASE_URL ?? "",
      anonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "",
      serviceRoleKey: env("SUPABASE_SERVICE_ROLE_KEY"),
    };
  },

  get webhookSecrets() {
    return {
      banking: env("BANKING_WEBHOOK_SECRET"),
      kyc: env("KYC_WEBHOOK_SECRET"),
      cards: env("CARD_WEBHOOK_SECRET"),
    };
  },

  get cronSecret() {
    return env("CRON_SECRET");
  },

  get providers() {
    return {
      email: env("EMAIL_PROVIDER_KEY"),
      card: env("CARD_PROVIDER_KEY"),
      exchange: env("EXCHANGE_PROVIDER_KEY"),
      kyc: env("KYC_PROVIDER_KEY"),
      banking: env("BANKING_PROVIDER_KEY_US"),
    };
  },
};
