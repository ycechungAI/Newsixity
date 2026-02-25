import { NextResponse } from "next/server";
import {
  getPreferenceKeywords,
  upsertPreferenceKeyword,
  deletePreferenceKeyword,
  CAPPED_CATEGORIES,
} from "@/lib/db/queries";
import { rebuildPreferences } from "@/lib/ranking/preferences";
import { z } from "zod";
import { badRequest, internalServerError, validationError } from "@/lib/server/api-response";
import { enforceRateLimit } from "@/lib/server/rate-limit";
import { InvalidJsonError, parseJsonBody } from "@/lib/server/request";

const VALID_CATEGORIES = new Set(CAPPED_CATEGORIES);

const PreferenceCreateSchema = z
  .object({
    categorySlug: z.string().trim().min(1),
    keyword: z.string().trim().min(1).max(120),
    weight: z.number().min(0.1).max(5).optional(),
    source: z.string().trim().min(1).max(64).optional(),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (!VALID_CATEGORIES.has(value.categorySlug)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["categorySlug"],
        message: `Invalid category. Must be one of: ${CAPPED_CATEGORIES.join(", ")}`,
      });
    }
  });

const PreferenceDeleteQuerySchema = z.object({
  id: z.coerce.number().int().positive(),
});

const PreferenceRebuildSchema = z
  .object({
    categorySlug: z.string().trim().optional(),
  })
  .strict()
  .superRefine((value, ctx) => {
    if (value.categorySlug && !VALID_CATEGORIES.has(value.categorySlug)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["categorySlug"],
        message: `Invalid category. Must be one of: ${CAPPED_CATEGORIES.join(", ")}`,
      });
    }
  });

export async function GET(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "preferences-get",
    limit: 120,
    windowMs: 10 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const { searchParams } = new URL(request.url);
    const category = searchParams.get("category")?.trim() || undefined;

    if (category && !VALID_CATEGORIES.has(category)) {
      return badRequest(
        `Invalid category. Must be one of: ${CAPPED_CATEGORIES.join(", ")}`
      );
    }

    const keywords = getPreferenceKeywords(category);

    return NextResponse.json({ keywords });
  } catch (e) {
    return internalServerError("Preferences GET error", e);
  }
}

export async function POST(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "preferences-post",
    limit: 60,
    windowMs: 10 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const { categorySlug, keyword, weight, source } =
      await parseJsonBody(request, PreferenceCreateSchema);

    upsertPreferenceKeyword(
      categorySlug,
      keyword,
      weight ?? 1.0,
      source ?? "manual"
    );

    return NextResponse.json({ success: true });
  } catch (e) {
    if (e instanceof z.ZodError) {
      return validationError(e);
    }
    if (e instanceof InvalidJsonError) {
      return badRequest("Invalid JSON payload");
    }
    return internalServerError("Preferences POST error", e);
  }
}

export async function DELETE(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "preferences-delete",
    limit: 60,
    windowMs: 10 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const { searchParams } = new URL(request.url);
    const { id } = PreferenceDeleteQuerySchema.parse({
      id: searchParams.get("id"),
    });

    deletePreferenceKeyword(id);

    return NextResponse.json({ success: true });
  } catch (e) {
    if (e instanceof z.ZodError) {
      return validationError(e);
    }
    return internalServerError("Preferences DELETE error", e);
  }
}

// POST endpoint to manually trigger rebuild
export async function PUT(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "preferences-put",
    limit: 30,
    windowMs: 10 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const { categorySlug } = await parseJsonBody(request, PreferenceRebuildSchema);

    rebuildPreferences(categorySlug);

    return NextResponse.json({ success: true });
  } catch (e) {
    if (e instanceof z.ZodError) {
      return validationError(e);
    }
    if (e instanceof InvalidJsonError) {
      return badRequest("Invalid JSON payload");
    }
    return internalServerError("Preferences PUT error", e);
  }
}
