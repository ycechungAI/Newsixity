import { backgroundSummarize } from "./background";
import { getSummarizationQueueCount } from "@/lib/db/queries";

const globalForSummarizer = globalThis as unknown as {
  __newsixitySummarizerScheduler: NodeJS.Timeout | undefined;
  __newsixitySummarizerStarted: boolean | undefined;
};

/**
 * Check for unsummarized articles and process them
 */
async function checkAndSummarize(): Promise<void> {
  try {
    const queueCount = getSummarizationQueueCount();

    if (queueCount === 0) {
      return; // Nothing to do
    }

    console.log(`[Newsixity] Summarization check: ${queueCount} articles in queue`);

    // Run background summarizer
    await backgroundSummarize();
  } catch (error) {
    console.error("[Newsixity] Summarization scheduler error:", error);
  }
}

/**
 * Start automatic summarization scheduler
 * Checks every 3 minutes for articles that need summarization
 */
export function startSummarizationScheduler(intervalMinutes: number = 3): void {
  if (globalForSummarizer.__newsixitySummarizerStarted) return;
  globalForSummarizer.__newsixitySummarizerStarted = true;

  console.log(
    `[Newsixity] Starting summarization scheduler (interval: ${intervalMinutes}min)`
  );

  // Run initial check after 10 seconds (let the server start up)
  setTimeout(() => {
    checkAndSummarize();
  }, 10000);

  // Set up periodic check
  globalForSummarizer.__newsixitySummarizerScheduler = setInterval(
    () => {
      checkAndSummarize();
    },
    intervalMinutes * 60 * 1000
  );
}

export function stopSummarizationScheduler(): void {
  if (globalForSummarizer.__newsixitySummarizerScheduler) {
    clearInterval(globalForSummarizer.__newsixitySummarizerScheduler);
    globalForSummarizer.__newsixitySummarizerScheduler = undefined;
    globalForSummarizer.__newsixitySummarizerStarted = false;
    console.log("[Newsixity] Summarization scheduler stopped");
  }
}
