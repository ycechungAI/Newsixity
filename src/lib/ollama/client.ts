import { Ollama } from "ollama";
import { OllamaUnavailableError } from "@/types";
import {
  SUMMARIZATION_SYSTEM_PROMPT,
  GROUP_LABEL_SYSTEM_PROMPT,
} from "./prompts";

const ollama = new Ollama({ host: "http://localhost:11434" });

const DEFAULT_MODEL = "qwen3-coder-next:cloud";
const MAX_CONTENT_LENGTH = 3000;

// ---------------------------------------------------------------------------
// Simple in-memory summarization queue (mutex)
// ---------------------------------------------------------------------------

let summarizationInProgress = false;
const queue: Array<{
  resolve: (v: string) => void;
  reject: (e: Error) => void;
  fn: () => Promise<string>;
}> = [];

async function enqueue(fn: () => Promise<string>): Promise<string> {
  return new Promise((resolve, reject) => {
    queue.push({ resolve, reject, fn });
    processQueue();
  });
}

async function processQueue() {
  if (summarizationInProgress || queue.length === 0) return;
  summarizationInProgress = true;
  const item = queue.shift()!;
  try {
    const result = await item.fn();
    item.resolve(result);
  } catch (e) {
    item.reject(e as Error);
  } finally {
    summarizationInProgress = false;
    processQueue();
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export async function isOllamaAvailable(): Promise<boolean> {
  try {
    await ollama.list();
    return true;
  } catch {
    return false;
  }
}

export async function getAvailableModels(): Promise<string[]> {
  try {
    const response = await ollama.list();
    return response.models.map((m) => m.name);
  } catch {
    return [];
  }
}

export async function summarizeArticle(
  title: string,
  content: string,
  model: string = DEFAULT_MODEL,
): Promise<string> {
  return enqueue(async () => {
    const available = await isOllamaAvailable();
    if (!available) {
      throw new OllamaUnavailableError(
        "Ollama is not running or not reachable at http://localhost:11434",
      );
    }

    const truncatedContent =
      content.length > MAX_CONTENT_LENGTH
        ? content.slice(0, MAX_CONTENT_LENGTH)
        : content;

    try {
      const response = await ollama.chat({
        model,
        stream: false,
        messages: [
          { role: "system", content: SUMMARIZATION_SYSTEM_PROMPT },
          {
            role: "user",
            content: `Title: ${title}\n\nContent: ${truncatedContent}`,
          },
        ],
        options: {
          temperature: 0.3,
          num_predict: 200,
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
          "Lost connection to Ollama during summarization",
        );
      }
      throw error;
    }
  });
}

export async function generateGroupLabel(
  titles: string[],
  model: string = DEFAULT_MODEL,
): Promise<string> {
  const available = await isOllamaAvailable();
  if (!available) {
    throw new OllamaUnavailableError(
      "Ollama is not running or not reachable at http://localhost:11434",
    );
  }

  try {
    const response = await ollama.chat({
      model,
      stream: false,
      messages: [
        { role: "system", content: GROUP_LABEL_SYSTEM_PROMPT },
        { role: "user", content: titles.join("\n") },
      ],
      options: {
        temperature: 0.2,
        num_predict: 30,
      },
    });

    return response.message.content.trim();
  } catch (e) {
    const error = e as Error;
    if (
      error.message.includes("ECONNREFUSED") ||
      error.message.includes("fetch failed")
    ) {
      throw new OllamaUnavailableError(
        "Lost connection to Ollama during label generation",
      );
    }
    throw error;
  }
}
