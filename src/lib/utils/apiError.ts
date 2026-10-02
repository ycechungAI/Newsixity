/** Extract a readable message from an API error body.

FastAPI returns `{"detail": "..."}` for HTTPException but
`{"detail": [{loc, msg, type}, ...]}` for 422 validation errors — rendering
the array directly would show "[object Object]". */
export function apiErrorMessage(body: unknown, fallback: string): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string" && detail.length > 0) return detail;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((d) =>
        typeof d === "string" ? d : (d as { msg?: unknown } | null)?.msg
      )
      .filter((m): m is string => typeof m === "string" && m.length > 0)
      // Pydantic prefixes custom validator messages with "Value error, ".
      .map((m) => m.replace(/^Value error, /, ""));
    if (parts.length > 0) return parts.join("; ");
  }
  return fallback;
}
