import { Ollama } from "ollama";
import { OllamaUnavailableError } from "@/types";
import type { ResearchSource } from "@/types";
import { RESEARCH_SYSTEM_PROMPT } from "./prompts";
import { getSetting } from "@/lib/db/queries";

const DEFAULT_MODEL = "llama3.2";
const DEFAULT_HOST = "http://localhost:11434";

export async function answerResearchQuestion(
  question: string,
  articleTitle: string,
  articleContent: string | null,
  sources: ResearchSource[],
  model: string = DEFAULT_MODEL
): Promise<string> {
  // Get Ollama host from settings or use default
  const host = getSetting("ollama_host") || DEFAULT_HOST;
  const ollama = new Ollama({ host });

  try {
    await ollama.list();
  } catch {
    throw new OllamaUnavailableError(
      `Ollama is not running or not reachable at ${host}`
    );
  }

  // Build numbered source context
  const sourceContext = sources
    .map((s, i) => `[${i + 1}] ${s.title}\nURL: ${s.url}\n${s.snippet}`)
    .join("\n\n");

  const articleContext = articleContent
    ? `Article: "${articleTitle}"\n${articleContent.slice(0, 1500)}`
    : `Article: "${articleTitle}"`;

  const userPrompt = `${articleContext}

---

Research Sources:
${sourceContext || "(No sources available)"}

---

Question: ${question}`;

  try {
    const response = await ollama.chat({
      model,
      stream: false,
      messages: [
        { role: "system", content: RESEARCH_SYSTEM_PROMPT },
        { role: "user", content: userPrompt },
      ],
      options: {
        temperature: 0.2,
        num_predict: 500,
      },
    });

    return response.message.content;
  } catch (e) {
    const error = e as Error;
    if (
      error.message.includes("ECONNREFUSED") ||
      error.message.includes("fetch failed")
    ) {
      throw new OllamaUnavailableError(
        "Lost connection to Ollama during research"
      );
    }
    throw error;
  }
}
