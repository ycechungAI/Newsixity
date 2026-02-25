import { NextResponse } from 'next/server';
import { execFile } from 'child_process';
import { promisify } from 'util';
import { enforceRateLimit } from "@/lib/server/rate-limit";
import { internalServerError } from "@/lib/server/api-response";

const execFileAsync = promisify(execFile);

// POST /api/console/stop
// Stops Ollama and Next.js dev servers
export async function POST(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "console-stop",
    limit: 20,
    windowMs: 10 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const [nextResult, ollamaResult] = await Promise.allSettled([
      execFileAsync("pkill", ["-f", "next dev"]),
      execFileAsync("pkill", ["-x", "ollama"]),
    ]);

    const output: string[] = [];
    if (nextResult.status === "fulfilled") {
      output.push(nextResult.value.stdout.trim());
    }
    if (ollamaResult.status === "fulfilled") {
      output.push(ollamaResult.value.stdout.trim());
    }

    return NextResponse.json({
      success: true,
      message: 'Servers stopped successfully',
      output: output.filter(Boolean).join("\n") || 'Servers stopped',
    });
  } catch (error) {
    return internalServerError("Console stop POST error", error);
  }
}
