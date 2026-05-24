import { getUnsummarizedArticles, updateArticleSummary } from "@/lib/db/queries";
import type { Article } from "@/types";
import { summarizeArticle, isOllamaAvailable } from "@/lib/ollama/client";
import { OllamaUnavailableError, OllamaModelNotFoundError } from "@/types";

// Define the specialized error type for when a user hits their session limit on external AI services.
export class SessionLimitExceededError extends Error {
    constructor(message: string) {
        super(message);
        this.name = "SessionLimitExceededError";
    }
}

// Default model used for summarization when none is specified
const DEFAULT_MODEL = "granite4.1:8b";
// Backup model if default is not available
const BACKUP_MODEL = "llama3.2";

/**
 * @module SummarizationService
 * Manages the state transition and processing flow for all articles that require a summary.
 */
export class SummarizationService {
  public static async getCandidates(limit: number = 50, category: string | null = null): Promise<Article[]> {
    console.log("[Service] Fetching uncategorized articles. Limit: " + limit);
    return getUnsummarizedArticles(limit, category ?? undefined);
  }

  /**
   * Summarize a single article with the given model, falling back to backup model if needed.
   * @param title Article title
   * @param content Article content
   * @param model Model name to use for summarization
   * @returns The generated summary
   */
  public static async summarizeArticle(
    title: string,
    content: string,
    model: string = DEFAULT_MODEL
  ): Promise<string> {
    try {
      // Delegate to the Ollama client which already handles availability, truncation, and errors
      return await summarizeArticle(title, content, model);
    } catch (error) {
      // If the model is not found, try the backup model
      if (error instanceof OllamaModelNotFoundError) {
        console.warn(`[SummarizationService] Model "${model}" not found, falling back to "${BACKUP_MODEL}"`);
        return await summarizeArticle(title, content, BACKUP_MODEL);
      }
      // Re-throw any other errors (including OllamaUnavailableError)
      throw error;
    }
  }

  /**
   * Summarize a single article (used by the API route).
   * @param title Article title
   * @param textToSummarize Article content
   * @param model Model name to use (from request or default)
   * @returns The generated summary
   */
  public static async summarizeSingleArticle(
    title: string,
    textToSummarize: string,
    model: string = "llama3.2"
  ): Promise<string> {
    return this.summarizeArticle(title, textToSummarize, model);
  }

  /**
   * Processes a list of candidate articles by calling the summarization model for each.
   * @param candidates Array of articles to process.
   * @returns An object containing success metrics and a list of specific errors encountered.
   */
  public static async processBatch(candidates: Article[]): Promise<{ summarizedCount: number, failedArticles: { id: number, reason: string }[]} > {
    let successfulSummaries = 0;
    const processingErrors: { id: number, reason: string }[] = [];

    for (const article of candidates) {
      try {
        if (!article.content || article.content.length < 10) {
          processingErrors.push({ id: article.id, reason: "Article has no sufficient content." });
          continue;
        }
        
        // --- COMPLEX FLOW CHECK START ---
        // In a real scenario, we would fetch the current user quota/status here.
        const isQuotaExceeded = false; // Assume FALSE for now during service logic creation

        if (isQuotaExceeded) {
            // If quota is exceeded but the system hasn't been properly transitioned to local LLM yet, 
            // we need a specific response that signals re-queueing based on state.
            throw new SessionLimitExceededError("External session limit reached.");
        }

        // --- Attempt External LLM Run ---
        const summary = await SummarizationService.summarizeArticle(article.title, article.content); 
        await updateArticleSummary(article.id, summary, DEFAULT_MODEL);
        successfulSummaries++;

      } catch (e) {
        // Check if the failure is a known state-switchable error
        if (e instanceof SessionLimitExceededError) {
          // This signals that external AI failed due to user limits and requires human intervention/manual local run.
          processingErrors.push({ id: article.id, reason: "EXTERNAL LLM FAILED DUE TO SESSION LIMIT. Please trigger a manual local resummarization." });
        } else if (e instanceof Error) {
          // Generic runtime error from the LLM call or DB write failure
          processingErrors.push({ id: article.id, reason: `Transient failure during summarization: ${e.message}` });
        }
      }
    }

    return { summarizedCount: successfulSummaries, failedArticles: processingErrors };
  }
}
