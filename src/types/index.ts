export interface Category {
  id: number;
  name: string;
  slug: string;
  sortOrder: number;
}

export interface Feed {
  id: number;
  categoryId: number;
  categorySlug?: string | null;
  name: string;
  url: string;
  enabled: boolean;
  lastFetchedAt: string | null;
  lastError: string | null;
  sourceWeight: number;
}

export interface Article {
  id: number;
  feedId: number;
  feedName: string;
  categorySlug: string;
  guid: string;
  title: string;
  link: string;
  author: string | null;
  publishedAt: string | null;
  content: string | null;
  imageUrl: string | null;
  summary: string | null;
  summaryModel: string | null;
  isRead: boolean;
  isSaved: boolean;
  groupId: number | null;
  fetchedAt: string;
  relevanceScore: number;
  isPromoted: boolean;
}

export interface ArticleGroup {
  id: number;
  label: string | null;
  categoryId: number;
  representativeId: number;
  articleCount: number;
  representative: Article;
  articles: Article[];
}

export interface FeedConfig {
  name: string;
  url: string;
}

export interface ParsedArticle {
  guid: string;
  title: string;
  link: string;
  author: string | null;
  publishedAt: string;
  content: string | null;
  imageUrl: string | null;
}

export interface HealthStatus {
  db: boolean;
  ollama: boolean;
  ollamaModels: string[];
  feedsCount: number;
  articlesCount: number;
  lastRefresh: string | null;
}

export interface RefreshResult {
  refreshed: number;
  newArticles: number;
  errors: string[];
}

export interface ResearchSource {
  url: string;
  title: string;
  snippet: string;
}

export interface ArticleResearch {
  id: number;
  articleId: number;
  question: string;
  answer: string;
  sources: ResearchSource[];
  model: string | null;
  createdAt: string;
}

export class OllamaUnavailableError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "OllamaUnavailableError";
  }
}

export class OllamaModelNotFoundError extends Error {
  constructor(model: string) {
    super(`Model "${model}" not found. Run: ollama pull ${model}`);
    this.name = "OllamaModelNotFoundError";
  }
}
