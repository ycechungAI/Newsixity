import { startScheduler } from "@/lib/rss/scheduler";
import { startBackupScheduler } from "@/lib/backup/scheduler";
import { startSummarizationScheduler } from "@/lib/ollama/scheduler";
import { installConsoleInterceptor } from "@/lib/logger/console";

const globalForBackgroundServices = globalThis as unknown as {
  __newsixityBackgroundServicesStarted: boolean | undefined;
};

function isBuildPhase(): boolean {
  return process.env.NEXT_PHASE === "phase-production-build";
}

function isDisabledByConfig(): boolean {
  return process.env.NEWSIXITY_DISABLE_BACKGROUND_SERVICES === "1";
}

/**
 * Start long-running server background services once per process.
 * Skips Next.js production build phase to avoid side effects during static generation.
 */
export function ensureBackgroundServicesStarted(): void {
  if (typeof window !== "undefined") return;
  if (isBuildPhase()) return;
  if (isDisabledByConfig()) return;
  if (globalForBackgroundServices.__newsixityBackgroundServicesStarted) return;

  globalForBackgroundServices.__newsixityBackgroundServicesStarted = true;

  installConsoleInterceptor();
  startScheduler();
  startBackupScheduler();
  startSummarizationScheduler();
}
