import type { ResearchSource } from "@/types";
import { searchDuckDuckGo } from "./search";
import { fetchArticleContent } from "@/lib/content/fetcher";
import { answerResearchQuestion } from "@/lib/ollama/research";

const MAX_SOURCE_LENGTH = 1500;

export async function conductResearch(
  articleTitle: string,
  articleContent: string | null,
  question: string,
  model?: string,
  apiKey?: string | null
): Promise<{ answer: string; sources: ResearchSource[] }> {
  // 1. Search DuckDuckGo
  const searchQuery = `${question} ${articleTitle}`;
  const searchResults = await searchDuckDuckGo(searchQuery, 8, apiKey);

  if (searchResults.length === 0) {
    return {
      answer:
        "I don't have enough information from the available sources to answer this question. The web search returned no results.",
      sources: [],
    };
  }

  // 2. Fetch top 5 result pages in parallel
  const topResults = searchResults.slice(0, 5);
  const fetchPromises = topResults.map(async (result) => {
    try {
      const content = await fetchArticleContent(result.url);
      return {
        url: result.url,
        title: result.title,
        snippet: content
          ? content.slice(0, MAX_SOURCE_LENGTH)
          : result.snippet,
      } as ResearchSource;
    } catch {
      return {
        url: result.url,
        title: result.title,
        snippet: result.snippet,
      } as ResearchSource;
    }
  });

  const sources = await Promise.all(fetchPromises);
  const usableSources = sources.filter((s) => s.snippet.length > 20);

  if (usableSources.length === 0) {
    return {
      answer:
        "I don't have enough information from the available sources to answer this question. Could not extract content from search results.",
      sources: [],
    };
  }

  // 3. Call Ollama with research prompt
  const answer = await answerResearchQuestion(
    question,
    articleTitle,
    articleContent,
    usableSources,
    model
  );

  return { answer, sources: usableSources };
}
