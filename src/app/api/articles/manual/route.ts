import { NextResponse } from "next/server";
import { createManualArticle, deleteManualArticle } from "@/lib/db/queries";
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

    return NextResponse.json({ success: true, articleId }, { status: 201 });

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
