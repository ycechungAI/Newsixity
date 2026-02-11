import { NextResponse } from "next/server";
import { getSetting, setSetting, getAllSettings } from "@/lib/db/queries";

export async function GET() {
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
    const message = e instanceof Error ? e.message : String(e);
    console.error("[Newsixity] Settings GET error:", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { brave_search_api_key, ollama_model, ollama_host } = body as {
      brave_search_api_key?: string;
      ollama_model?: string;
      ollama_host?: string;
    };

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
    const message = e instanceof Error ? e.message : String(e);
    console.error("[Newsixity] Settings POST error:", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
