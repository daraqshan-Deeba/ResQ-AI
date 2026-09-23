import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const revalidate = 0;

/**
 * Lightweight warm endpoint for uptime monitors / GitHub Actions.
 * No auth, no DB — keeps the Vercel serverless function out of cold start.
 */
export async function GET() {
  return NextResponse.json(
    {
      ok: true,
      service: "resq-frontend",
      warmed_at: new Date().toISOString(),
    },
    {
      status: 200,
      headers: {
        "Cache-Control": "no-store, no-cache, must-revalidate",
      },
    },
  );
}
