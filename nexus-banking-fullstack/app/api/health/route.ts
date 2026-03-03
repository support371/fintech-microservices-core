import { NextResponse } from "next/server";
import { config } from "@/src/server/config";

export const dynamic = "force-dynamic";

export async function GET() {
  const checks: Record<string, string> = {
    status: "healthy",
    app: config.appName,
    mode: config.mockMode ? "mock" : "live",
    timestamp: new Date().toISOString(),
  };

  if (!config.mockMode) {
    try {
      const { getServerSupabase } = await import("@/src/server/supabase");
      const supabase = getServerSupabase();
      const { error } = await supabase.from("app_config").select("key").limit(1);
      checks.database = error ? "unhealthy" : "healthy";
    } catch {
      checks.database = "unhealthy";
    }
  } else {
    checks.database = "mock";
  }

  const isHealthy = checks.database !== "unhealthy";
  return NextResponse.json(checks, { status: isHealthy ? 200 : 503 });
}
