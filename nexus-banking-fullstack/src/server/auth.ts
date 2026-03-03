import { NextRequest } from "next/server";
import { config } from "./config";
import { mockStore } from "./supabase";

export interface AuthUser {
  id: string;
  email: string;
  fullName: string;
  kycTier: number;
  kycStatus: string;
  isAdmin: boolean;
}

const ADMIN_AUTH_IDS = new Set(["mock-user-1"]);

/**
 * Extract the authenticated user from a request.
 * In mock mode, returns the seeded demo user.
 * In production, validates the Supabase JWT from the Authorization header.
 */
export async function requireUser(req: NextRequest): Promise<AuthUser> {
  if (config.mockMode) {
    const user = mockStore.getUserByAuthId("mock-user-1");
    if (!user) throw new Error("Mock user not found");
    return {
      id: user.id,
      email: user.email,
      fullName: user.full_name,
      kycTier: user.kyc_tier,
      kycStatus: user.kyc_status,
      isAdmin: ADMIN_AUTH_IDS.has(user.auth_id),
    };
  }

  const authHeader = req.headers.get("authorization");
  if (!authHeader?.startsWith("Bearer ")) {
    throw new AuthError("Missing or invalid Authorization header");
  }

  const token = authHeader.slice(7);
  const { createClient } = await import("@supabase/supabase-js");
  const supabase = createClient(config.supabase.url, config.supabase.anonKey, {
    global: { headers: { Authorization: `Bearer ${token}` } },
  });

  const { data: { user: authUser }, error } = await supabase.auth.getUser();
  if (error || !authUser) {
    throw new AuthError("Invalid or expired token");
  }

  const { getServerSupabase } = await import("./supabase");
  const server = getServerSupabase();
  const { data: profile, error: profileError } = await server
    .from("users")
    .select("*")
    .eq("auth_id", authUser.id)
    .single();

  if (profileError || !profile) {
    throw new AuthError("User profile not found");
  }

  return {
    id: profile.id,
    email: profile.email,
    fullName: profile.full_name,
    kycTier: profile.kyc_tier,
    kycStatus: profile.kyc_status,
    isAdmin: ADMIN_AUTH_IDS.has(authUser.id),
  };
}

/**
 * Require admin-level access. Throws if the user is not an admin.
 */
export async function requireAdmin(req: NextRequest): Promise<AuthUser> {
  const user = await requireUser(req);
  if (!user.isAdmin) {
    throw new AuthError("Admin access required");
  }
  return user;
}

export class AuthError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AuthError";
  }
}
