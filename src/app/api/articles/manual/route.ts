import { NextResponse } from "next/server";
import { createManualArticle, deleteManualArticle, createArticlesFromSearchResults } from "@/lib/db/queries";
import { isSearchEngineUrl } from "@/lib/utils/search";
import { extractSearchResults } from "@/lib/server/search-extractor";
import { z } from "zod";

const ManualArticleSchema = z.object({
  url: z.string().url("Invalid URL"),
  title: z.string().min(1, "Title required").max(500),
  content: z.string().optional(),
  imageUrl: z.string().url().optional(),
  author: z.string().optional(),
});

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const validated = ManualArticleSchema.parse(body);

    const articleId = createManualArticle(validated);

    if (!articleId) {
      return NextResponse.json(
        { error: "Article with this URL already exists" },
        { status: 409 }
      );
    }

    const response: any = { success: true, articleId };
    const resultArticleIds: number[] = [];

    // If it's a search engine URL, extract and save the results
    if (isSearchEngineUrl(validated.url)) {
      try {
        const searchResults = await extractSearchResults(validated.url);
        if (searchResults.length > 0) {
          const createdIds = createArticlesFromSearchResults(searchResults, validated.url);
          resultArticleIds.push(...createdIds);
        }
      } catch (error) {
        console.error("Failed to extract search results:", error);
        // Don't fail the request, just log the error
      }
    }

    if (resultArticleIds.length > 0) {
      response.resultArticleIds = resultArticleIds;
      response.resultCount = resultArticleIds.length;
    }

    return NextResponse.json(response, { status: 201 });

  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: "Validation failed", details: error.issues },
        { status: 400 }
      );
    }

    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function DELETE(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const id = parseInt(searchParams.get("id") ?? "", 10);

    if (isNaN(id)) {
      return NextResponse.json({ error: "Invalid article ID" }, { status: 400 });
    }

    const deleted = deleteManualArticle(id);

    if (!deleted) {
      return NextResponse.json(
        { error: "Article not found or not a manual link" },
        { status: 404 }
      );
    }

    return NextResponse.json({ success: true });

  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
