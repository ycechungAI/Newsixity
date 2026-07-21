# Stage 2: Pydantic Schemas — Complete

**Status:** ✅ Complete  
**Author:** Haiku 4.5  
**Lines of code:** ~420 LOC in `backend/app/schemas.py`  
**Tests:** All validation rules pass (coercion, bounds checking, URL validation, aliasing)

## What was built

`backend/app/schemas.py` contains 30+ Pydantic models covering all API request/response shapes:

### Domain Models (port of src/types/index.ts)
- **Core:** `Category`, `Feed`, `Article`, `ArticleGroup`, `ArticleResearch`
- **Finance:** `StockQuote`, `StockChartData`, `MarketHeatmapSnapshot`
- **User:** `UserPreference`
- **API:** `HealthStatus`, `RefreshResult`, `ResearchSource`

### Request Body Schemas
- `ResearchRequestBody` — article_id (positive), question (1-500 chars)
- `PreferenceCreateRequestBody` — category_slug, keyword, weight (0.1-5.0), source
- `PreferenceDeleteRequestQuery` — id
- `PreferenceRebuildRequestBody` — optional category_slug
- `ManualArticleRequestBody` — url (http/https only), title (1-500), content (≤50KB), imageUrl, author
- `ManualArticleDeleteRequestQuery` — id
- `SettingsUpdateRequestBody` — brave_search_api_key, ollama_model, ollama_host (all optional, URL-validated)
- `FeedWeightUpdateRequestBody` — feed_id, weight (0.1-10.0)
- `SearchResultsRequestBody` — url, results list
- `FinanceQuoteRequestQuery` — symbols (comma-separated)
- `FinanceChartRequestQuery` — symbol, timeframe
- `FinanceSearchRequestBody` — query, limit
- `FinanceWatchlistActionRequestBody` — symbol, name, exchange
- `ArticlesMarkAllReadRequestBody` — optional category_slug

### Response & Utility Schemas
- `ErrorResponse`, `SuccessResponse`, `MessageResponse`, `DataResponse`

## Key Features

**Field aliasing:** All models use `Field(alias="...")` + `model_config = {"populate_by_name": True}` to auto-convert between:
- API input/output (camelCase, following Node.js convention)
- Database/internal (snake_case, matching SQLAlchemy models)

**Validation:** Custom validators via `@field_validator` for:
- Length bounds (title, question, API key, etc.)
- Positive integers (article_id, feed_id, etc.)
- URL validation (http/https only, no javascript: or credentials)
- Numeric ranges (weight: 0.1-10.0, etc.)
- String trimming and normalization

**Testing:** All validators tested against scratch data; edge cases verified (negative IDs rejected, malicious URLs rejected, bounds enforced).

## Next steps

**Stage 3** (Haiku 4.5) will port utility functions and pure business logic:
- `utils/date.ts` — date math, formatting
- `utils/search.ts` — search result parsing
- `utils/video.ts` — video extraction/metadata
- `dedup/similarity.ts` — title/content similarity hashing
- `dedup/grouping.ts` — article grouping logic
- Plus **Sonnet 5** will handle ranking math (preferences weighting, relevance scoring)

**Stage 4** (mixed Sonnet/Haiku) integrates external APIs:
- Sonnet: yfinance (stock data), ollama (LLM)
- Haiku: RSS feed parsing, weather API, HTTP-only content extraction (no Playwright)

**Stage 5** (Haiku + Sonnet review) wires schemas into 24 API routers.

---

**Schemas are ready for API route integration. No changes to database layer needed.**
