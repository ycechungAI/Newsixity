import { NextResponse } from "next/server";
import { Ollama } from "ollama";
import { getSetting } from "@/lib/db/queries";

// Suggested models with descriptions
const SUGGESTED_MODELS = [
  {
    name: "llama3.2",
    size: "2GB",
    description: "Fast, efficient model for general tasks",
    recommended: true,
  },
  {
    name: "llama3.2:3b",
    size: "2GB",
    description: "Compact 3B model, very fast",
    recommended: false,
  },
  {
    name: "llama3.1:8b",
    size: "4.7GB",
    description: "More capable 8B model, good balance",
    recommended: false,
  },
  {
    name: "qwen2.5:7b",
    size: "4.7GB",
    description: "Strong multilingual model",
    recommended: false,
  },
  {
    name: "mistral:7b",
    size: "4.1GB",
    description: "Popular, high quality model",
    recommended: false,
  },
];

export async function GET() {
  try {
    // Get Ollama host from settings or use default
    const host = getSetting("ollama_host") || "http://localhost:11434";
    const ollama = new Ollama({ host });

    // Try to list models
    let installedModels: any[] = [];
    let isRunning = false;

    try {
      const response = await ollama.list();
      installedModels = response.models || [];
      isRunning = true;
    } catch (e) {
      console.warn("[Newsixity] Ollama not reachable:", e instanceof Error ? e.message : String(e));
    }

    // Extract model names
    const installedModelNames = installedModels.map((m) => m.name);

    // Mark suggested models as installed if they exist
    const suggestions = SUGGESTED_MODELS.map((model) => ({
      ...model,
      installed: installedModelNames.some((name) =>
        name.startsWith(model.name.split(":")[0])
      ),
    }));

    return NextResponse.json({
      isRunning,
      host,
      installed: installedModels.map((m) => ({
        name: m.name,
        size: m.size,
        modified: m.modified_at,
      })),
      suggestions,
    });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    console.error("[Newsixity] Ollama models error:", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
