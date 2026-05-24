import { NextResponse } from "next/server";
import * as dbArticles from "@/db/index"; 
import { SummarizationService } from "@/lib/services/SummarizationService";

/**
 * HTTP POST handler for triggering article summarization.
 */
export async function POST(request: Request) {
  // --- 1. SAFETY CHECK & PREP ---
  try {
    const body = await request.json(); // Parse JSON body safely
  } catch (e) {
    return NextResponse.json({ error: "Invalid JSON payload." }, { status: 400 });
  }

  // --- 2. SINGLE ARTICLE SUMMARIZATION FLOW ---
  if (typeof body?.articleId === 'number' && body.articleId > 0) {
    console.log(`[API] Starting single article summarization for ID: ${body.articleId}`);
    const articleId = body.articleId;
    
    // A. Find the Article via the API Gateway
    const article = dbArticles.Articles.findById(articleId);

    if (!article) {
      return NextResponse.json({ error: "Article not found" }, { status: 404 });
    }

    // B. Check if already summarized (Cache Hit)
    if (article.summary) {
      console.log(`[API] Article ID ${articleId} has existing summary. Returning cached data.`);
      return NextResponse.json({ summary: article.summary }, { status: 200 });
    }

    // C. Check for content existence
    const textToSummarize = article.content && article.content.length > 10 ? article.content : null;

    if (!textToSummarize) {
      return NextResponse.json({ error: "Article has no sufficient content to summarize." }, { status: 400 });
    }

    // D. Execute single run summarization
    try {
        // API now uses the model provided in the request body if available, otherwise defaults.
        const requestedModel = body?.model || "llama3.2"; // Get user-selected model or default
        console.log(`[API] Running single article summarization with model: ${requestedModel}`);

        const summary = await SummarizationService.summarizeSingleArticle(article.title, textToSummarize, requestedModel); 
        await dbArticles.Articles.updateSummary(articleId, summary, "llama3.2"); // Note: DB update needs to reflect the used model in a real app flow

        return NextResponse.json({ message: "Single article successfully summarized.", summary });
    } catch (e) {
        console.error(`[API] Failed to summarize single article ${articleId}:`, e);
        return NextResponse.json({ error: "Internal processing failed during single run." }, { status: 500 });
    }

  // --- 3. BATCH/RESUMMARIZATION FLOW (The Button's main function) ---
  } else { // If no single ID was provided, it is the queue trigger.
    console.log("[API] Triggering batch resummarization sequence.");

    // A. Fetch all candidates
    const articles = dbArticles.Articles.getUnsummarizedBatch(50, null); 

    if (!articles || articles.length === 0) {
      return NextResponse.json({ message: "No unsummarized articles found for the queue." }, { status: 200 });
    }
    
    // B. Execute batch processing logic against service layer
    try {
        const results = await SummarizationService.processBatch(articles);

        // C. Return comprehensive report to frontend
        return NextResponse.json({ 
          message: "Batch processing finished.",
          summarized: results.summarizedCount, 
          errors: results.failedArticles.map(f => `ID ${f.id}: ${f.reason}`) 
        }, { status: 200 });

    } catch (e) {
        // Handle the specific service limit failure here! This is critical for the UI experience.
        if (e instanceof SessionLimitExceededError) {
             return NextResponse.json({ 
                message: "External LLM limits are reached.", 
                errors: ["Quota exceeded, manual intervention required."]}, 
                { status: 403 } // HTTP 403 Forbidden/Rate Limit indicator for usage limit
            );
        }
        console.error("[API] Batch processing failed critically:", e);
        return NextResponse.json({ error: "A critical server failure occurred during batch execution." }, { status: 500 });
    }

  }


  // Final fallback if logic paths were missed
  return NextResponse.json({ error: "Invalid request payload structure." }, { status: 400 });
}
