import { NextResponse } from "next/server";
import { getAllArticleResearch, deleteArticleResearch } from "@/lib/db/queries";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const articleIdStr = searchParams.get("articleId");

    if (!articleIdStr) {
      return NextResponse.json(
        { error: "articleId is required" },
        { status: 400 }
      );
    }

    const articleId = parseInt(articleIdStr, 10);
    if (isNaN(articleId)) {
      return NextResponse.json(
        { error: "Invalid articleId" },
        { status: 400 }
      );
    }

    // Get all research for this article
    const history = getAllArticleResearch(articleId);

    return NextResponse.json({
      history: history.map((item) => ({
        id: item.id,
        question: item.question,
        answer: item.answer,
        sources: item.sources,
        createdAt: item.createdAt,
      })),
    });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    console.error("[Newsixity] Research history error:", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function DELETE(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const researchIdStr = searchParams.get("id");

    if (!researchIdStr) {
      return NextResponse.json(
        { error: "Research ID is required" },
        { status: 400 }
      );
    }

    const researchId = parseInt(researchIdStr, 10);
    if (isNaN(researchId)) {
      return NextResponse.json(
        { error: "Invalid research ID" },
        { status: 400 }
      );
    }

    // Delete the research item
    deleteArticleResearch(researchId);

    return NextResponse.json({
      success: true,
      message: "Research deleted successfully",
    });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    console.error("[Newsixity] Delete research error:", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
