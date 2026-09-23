import type { NextRequest } from "next/server";
import { runKeepalive } from "@/lib/keepalive";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function unauthorized() {
  return Response.json({ error: "unauthorized" }, { status: 401 });
}

export async function GET(request: NextRequest) {
  const cronSecret = process.env.CRON_SECRET?.trim();
  if (!cronSecret) {
    return Response.json(
      { error: "CRON_SECRET is not configured on Vercel" },
      { status: 503 },
    );
  }

  const authHeader = request.headers.get("authorization");
  if (authHeader !== `Bearer ${cronSecret}`) {
    return unauthorized();
  }

  const schedule = request.headers.get("x-vercel-cron-schedule");
  const report = await runKeepalive(schedule);

  const statusCode = report.status === "ok" ? 200 : report.status === "degraded" ? 207 : 500;
  return Response.json(report, { status: statusCode });
}
