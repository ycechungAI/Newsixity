import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { apiErrorMessage } from "@/lib/utils/apiError";

interface BriefingSource {
  n: number;
  articleId: number;
  title: string;
  feedName?: string;
}

interface Briefing {
  date: string;
  status: "ready" | "missing" | "generating";
  content: string | null;
  sources: BriefingSource[];
  model: string | null;
  createdAt: string | null;
  error: string | null;
}

const POLL_MS = 3000;

/** **bold** and [n] / [n, m] citations — the only markup the prompt asks for. */
function InlineText({ text, sources }: { text: string; sources: Map<number, BriefingSource> }) {
  const parts = text.split(/(\*\*[^*]+\*\*|\[\d+(?:,\s*\d+)*\])/g);
  return (
    <>
      {parts.map((part, i) => {
        const bold = part.match(/^\*\*([^*]+)\*\*$/);
        if (bold) return <strong key={i}>{bold[1]}</strong>;
        if (!/^\[\d+(?:,\s*\d+)*\]$/.test(part)) return <span key={i}>{part}</span>;
        // One link per number; a number with no source stays plain text.
        return part.match(/\d+/g)!.map((num, j) => {
          const source = sources.get(parseInt(num, 10));
          if (!source) return <span key={`${i}-${j}`}>[{num}]</span>;
          return (
            <Link key={`${i}-${j}`} to={`/article/${source.articleId}`} className="ask-cite" title={source.title}>
              [{num}]
            </Link>
          );
        });
      })}
    </>
  );
}

function BriefingBody({ content, sources }: { content: string; sources: BriefingSource[] }) {
  const byNumber = new Map(sources.map((s) => [s.n, s]));
  const lines = content.split("\n").map((l) => l.trim()).filter(Boolean);
  const bullets = lines.filter((l) => /^[-*•]\s+/.test(l));
  // Small models sometimes ignore the bullet instruction — show prose then.
  if (bullets.length === 0) {
    return (
      <div className="briefing-prose">
        {lines.map((l, i) => <p key={i}><InlineText text={l} sources={byNumber} /></p>)}
      </div>
    );
  }
  return (
    <ul className="briefing-list">
      {bullets.map((l, i) => (
        <li key={i}><InlineText text={l.replace(/^[-*•]\s+/, "")} sources={byNumber} /></li>
      ))}
    </ul>
  );
}

function localToday(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/**
 * Daily AI briefing: once-a-day summary of what mattered, generated locally
 * by Ollama from the day's top articles. Reading never generates — that
 * happens on the 7 AM job or the Regenerate button, and this page polls
 * while it runs.
 */
export default function BriefingPage() {
  const [params, setParams] = useSearchParams();
  const date = params.get("date") ?? localToday();
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [dates, setDates] = useState<string[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`/api/briefing?date=${date}`);
      const data = await res.json().catch(() => null);
      if (!res.ok || !data) {
        setLoadError(apiErrorMessage(data, "Could not load the briefing."));
        return;
      }
      setLoadError(null);
      setBriefing(data);
    } catch {
      setLoadError("Could not reach the Newsixity backend.");
    }
  }, [date]);

  const loadDates = useCallback(() => {
    fetch("/api/briefing/dates")
      .then((r) => (r.ok ? r.json() : { dates: [] }))
      .then((data) => setDates(data.dates ?? []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    setBriefing(null);
    void load();
    loadDates();
  }, [load, loadDates]);

  // Poll only while a generation is running; stop as soon as it settles.
  useEffect(() => {
    if (briefing?.status !== "generating") return;
    const timer = setInterval(() => {
      void load().then(loadDates);
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [briefing?.status, load, loadDates]);

  async function regenerate() {
    setActionError(null);
    try {
      const res = await fetch(`/api/briefing/regenerate?date=${date}`, { method: "POST" });
      const data = await res.json().catch(() => null);
      if (res.status === 409) {
        setActionError(`A briefing for ${data?.date ?? "another day"} is already being generated.`);
        return;
      }
      if (!res.ok) {
        setActionError(apiErrorMessage(data, "Could not start generation."));
        return;
      }
      await load();
    } catch {
      setActionError("Could not reach the Newsixity backend.");
    }
  }

  const dateOptions = Array.from(new Set([localToday(), date, ...dates])).sort().reverse();
  const generating = briefing?.status === "generating";

  return (
    <div className="page briefing-page">
      <div className="page-head">
        <div>
          <div className="page-title">Daily Briefing</div>
          <div className="page-sub">
            What mattered, summarized on this computer by Ollama from the day&apos;s top articles.
          </div>
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <select
            className="feed-select"
            value={date}
            onChange={(e) => setParams(e.target.value === localToday() ? {} : { date: e.target.value })}
            aria-label="Briefing date"
          >
            {dateOptions.map((d) => (
              <option key={d} value={d}>{d === localToday() ? `Today (${d})` : d}</option>
            ))}
          </select>
          <button className="tb-btn" onClick={regenerate} disabled={generating || !briefing}>
            {generating ? "Generating…" : briefing?.status === "ready" ? "↺ Regenerate" : "Generate now"}
          </button>
        </div>
      </div>

      {loadError && <div className="ask-error">{loadError}</div>}
      {actionError && <div className="ask-error">{actionError}</div>}

      {generating && (
        <div className="ask-loading">
          Generating with Ollama — this can take a minute. You can leave this page; it keeps going.
        </div>
      )}

      {briefing?.status === "missing" && (
        <div className="empty">
          <div className="empty-title">No briefing for {date === localToday() ? "today" : date} yet</div>
          <div className="empty-desc">
            {briefing.error ??
              "It is generated automatically at 7 AM, or press Generate now. Needs Ollama running."}
          </div>
        </div>
      )}

      {briefing?.content && (
        <>
          {briefing.error && <div className="ask-notice">Last regenerate failed: {briefing.error}</div>}
          <div className="briefing-card">
            <BriefingBody content={briefing.content} sources={briefing.sources} />
          </div>
          <div className="briefing-meta">
            {briefing.model && <>Generated by {briefing.model}</>}
            {briefing.createdAt && <> · {new Date(briefing.createdAt.replace(" ", "T") + "Z").toLocaleString()}</>}
          </div>
          {briefing.sources.length > 0 && (
            <details className="briefing-sources">
              <summary>{briefing.sources.length} source articles</summary>
              <ol>
                {briefing.sources.map((s) => (
                  <li key={s.n}>
                    <span className="ask-cite">[{s.n}]</span>{" "}
                    <Link to={`/article/${s.articleId}`}>{s.title}</Link>
                    {s.feedName && <span className="briefing-feed"> · {s.feedName}</span>}
                  </li>
                ))}
              </ol>
            </details>
          )}
        </>
      )}
    </div>
  );
}
