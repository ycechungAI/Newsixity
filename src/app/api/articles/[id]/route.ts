import { NextResponse } from "next/server";
import {
  getArticleById,
  markArticleRead,
  markArticleUnread,
  toggleArticleSaved,
} from "@/lib/db/queries";
import { summarizeArticleById } from "@/lib/ollama/background";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: idParam } = await params;
    const id = parseInt(idParam, 10);

    if (isNaN(id)) {
      return NextResponse.json({ error: "Invalid article ID" }, { status: 400 });
    }

    const article = getArticleById(id);
    if (!article) {
      return NextResponse.json({ error: "Article not found" }, { status: 404 });
    }

    markArticleRead(id);

    return NextResponse.json(article);
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: idParam } = await params;
    const id = parseInt(idParam, 10);

    if (isNaN(id)) {
      return NextResponse.json({ error: "Invalid article ID" }, { status: 400 });
    }

    const body = await request.json();
    const { is_read, is_saved } = body as {
      is_read?: boolean;
      is_saved?: boolean;
    };

    if (is_read === true) {
      markArticleRead(id);
    } else if (is_read === false) {
      markArticleUnread(id);
    }

    if (is_saved !== undefined) {
      toggleArticleSaved(id);

      // When saving, fire-and-forget a background summarization
      // so the summary is ready for the user next time
      const saved = getArticleById(id);
      if (saved?.isSaved && !saved.summary) {
        summarizeArticleById(id).catch(() => {});
      }
    }

    // Return categorySlug so the client can update sidebar counts
    const article = getArticleById(id);
    return NextResponse.json({
      success: true,
      categorySlug: article?.categorySlug ?? null,
    });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
