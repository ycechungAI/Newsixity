import { NextResponse } from "next/server";
import {
  setSetting,
  getAllSettings,
  SettingsEncryptionRequiredError,
} from "@/lib/db/queries";
import { z } from "zod";
import { badRequest, internalServerError, validationError } from "@/lib/server/api-response";
import { parseHttpUrl } from "@/lib/utils/url";
import { enforceRateLimit } from "@/lib/server/rate-limit";
import { InvalidJsonError, parseJsonBody } from "@/lib/server/request";

const SettingsUpdateSchema = z
  .object({
    brave_search_api_key: z.string().max(2048).optional(),
    ollama_model: z.string().trim().min(1).max(128).optional(),
    ollama_host: z
      .string()
      .trim()
      .max(512)
      .optional()
      .refine((value) => value === undefined || parseHttpUrl(value) !== null, {
        message: "ollama_host must be a valid http/https URL",
      }),
  })
  .strict();

export async function GET(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "settings-get",
    limit: 120,
    windowMs: 10 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const settings = getAllSettings();

    // Mask the API key (show only last 4 chars if exists)
    if (settings.brave_search_api_key) {
      const key = settings.brave_search_api_key;
      if (key.length > 4) {
        settings.brave_search_api_key = "•".repeat(key.length - 4) + key.slice(-4);
      } else {
        settings.brave_search_api_key = "•".repeat(key.length);
      }
    }

    return NextResponse.json({
      settings: {
        brave_search_api_key: settings.brave_search_api_key || "",
        ollama_model: settings.ollama_model || "llama3.2",
        ollama_host: settings.ollama_host || "http://localhost:11434",
      },
    });
  } catch (e) {
    return internalServerError("Settings GET error", e);
  }
}

export async function POST(request: Request) {
  const rateLimited = enforceRateLimit(request, {
    routeKey: "settings-post",
    limit: 60,
    windowMs: 10 * 60 * 1000,
  });
  if (rateLimited) return rateLimited;

  try {
    const { brave_search_api_key, ollama_model, ollama_host } =
      await parseJsonBody(request, SettingsUpdateSchema);

    // Save settings (only if provided)
    if (brave_search_api_key !== undefined) {
      // If the key is masked (contains bullets), don't update it
      if (!brave_search_api_key.includes("•")) {
        setSetting("brave_search_api_key", brave_search_api_key || null);
      }
    }

    if (ollama_model !== undefined) {
      setSetting("ollama_model", ollama_model || "llama3.2");
    }

    if (ollama_host !== undefined) {
      setSetting("ollama_host", ollama_host || "http://localhost:11434");
    }

    return NextResponse.json({
      success: true,
      message: "Settings saved successfully",
    });
  } catch (e) {
    if (e instanceof z.ZodError) {
      return validationError(e);
    }
    if (e instanceof InvalidJsonError) {
      return badRequest("Invalid JSON payload");
    }
    if (e instanceof SettingsEncryptionRequiredError) {
      return badRequest(e.message);
    }
    return internalServerError("Settings POST error", e);
  }
}
