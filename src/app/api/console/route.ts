import { NextResponse } from 'next/server';
import { getSummarizationQueue, getSummarizationQueueCount } from '@/lib/db/queries';
import { getLogs } from '@/lib/logger/console';
import { enforceRateLimit } from "@/lib/server/rate-limit";
import { internalServerError } from "@/lib/server/api-response";

// GET /api/console
// Returns summarization queue and recent logs
export async function GET(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "console-get",
    limit: 120,
    windowMs: 10 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const queue = getSummarizationQueue(20);
    const queueCount = getSummarizationQueueCount();
    const logs = getLogs();

    return NextResponse.json({
      queue,
      queueCount,
      logs,
    });
  } catch (error) {
    return internalServerError("Console GET error", error);
  }
}
