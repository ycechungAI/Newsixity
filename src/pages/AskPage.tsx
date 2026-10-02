import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { apiErrorMessage } from "@/lib/utils/apiError";

interface AskSource {
  url: string;
  title: string;
  snippet: string;
  articleId?: number | null;
}

interface AskArticle {
  id?: number | null;
  title?: string | null;
  link?: string | null;
  summary?: string | null;
  feedName?: string | null;
  publishedAt?: string | null;
}

interface AskTurn {
  question: string;
  answer: string | null;
  sources: AskSource[];
  synthesisAvailable: boolean;
  articles: AskArticle[];
  message?: string | null;
}

/** In-app article page when the source is a stored article, else outbound. */
function SourceLink({ source, children }: { source: AskSource; children: React.ReactNode }) {
  if (source.articleId) {
    return <Link to={`/article/${source.articleId}`} title={source.title}>{children}</Link>;
  }
  return (
    <a href={source.url} target="_blank" rel="noopener noreferrer" title={source.title}>
      {children}
    </a>
  );
}

/** Render "…according to [1] and [2, 3]…" with clickable citation links. */
function CitedAnswer({ answer, sources }: { answer: string; sources: AskSource[] }) {
  const parts = answer.split(/(\[\d+(?:,\s*\d+)*\])/g);
  return (
    <>
      {parts.map((part, i) => {
        if (!/^\[\d+(?:,\s*\d+)*\]$/.test(part)) return <span key={i}>{part}</span>;
        return part.match(/\d+/g)!.map((num, j) => {
          const source = sources[parseInt(num, 10) - 1];
          // A citation number the model invented has no source — keep it as
          // plain text rather than rendering a dead link.
          if (!source) return <span key={`${i}-${j}`}>[{num}]</span>;
          return (
            <SourceLink key={`${i}-${j}`} source={source}>
              <span className="ask-cite">[{num}]</span>
            </SourceLink>
          );
        });
      })}
    </>
  );
}

function ArticleFallbackList({ articles }: { articles: AskArticle[] }) {
  return (
    <ul className="ask-fallback">
      {articles.map((a, i) => {
        const body = (
          <>
            <div className="ask-fallback-title">{a.title || a.link}</div>
            {a.summary && <div className="ask-fallback-summary">{a.summary}</div>}
            {a.feedName && <div className="ask-fallback-meta">{a.feedName}</div>}
          </>
        );
        return (
          <li key={a.id ?? i}>
            {a.id ? (
              <Link to={`/article/${a.id}`}>{body}</Link>
            ) : (
              <a href={a.link || "#"} target="_blank" rel="noopener noreferrer">{body}</a>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/**
 * Ask Newsixity — a synthesized, cited answer from the local article
 * library. The thread lives only in this component: prior turns go back to
 * the server as `history` so follow-ups keep their context.
 */
export default function AskPage() {
  const [params] = useSearchParams();
  const initialQuestion = (params.get("q") ?? "").trim();
  const [turns, setTurns] = useState<AskTurn[]>([]);
  const [input, setInput] = useState(initialQuestion);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const autoAsked = useRef(false);

  async function ask(question: string) {
    if (!question || loading) return;
    setLoading(true);
    setError(null);

    const history = turns
      .filter((t) => t.answer)
      .map((t) => ({ question: t.question, answer: t.answer as string }));

    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, history }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data) {
        setError(apiErrorMessage(data, "Ask failed"));
        return;
      }
      setTurns((prev) => [
        ...prev,
        {
          question,
          answer: data.answer ?? null,
          sources: data.sources || [],
          synthesisAvailable: data.synthesisAvailable ?? false,
          articles: data.articles || [],
          message: data.message ?? null,
        },
      ]);
      setInput("");
    } catch {
      setError("Could not reach the Newsixity backend.");
    } finally {
      setLoading(false);
    }
  }

  // Arriving from the top-bar Ask button with ?q= asks straight away —
  // making the user press Ask a second time reads as "nothing happened".
  useEffect(() => {
    if (initialQuestion && !autoAsked.current) {
      autoAsked.current = true;
      void ask(initialQuestion);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuestion]);

  return (
    <div className="page ask-page">
      <div className="page-head">
        <div>
          <div className="page-title">Ask Newsixity</div>
          <div className="page-sub">
            Answers are synthesized from your fetched articles, with citations.
            Follow-ups keep the thread&apos;s context.
          </div>
        </div>
        {turns.length > 0 && (
          <button
            className="tb-btn"
            onClick={() => {
              setTurns([]);
              setError(null);
            }}
          >
            New thread
          </button>
        )}
      </div>

      {turns.map((turn, ti) => (
        <div key={ti} className="ask-turn">
          <div className="ask-question">{turn.question}</div>

          {turn.answer ? (
            <div className="ask-answer">
              <CitedAnswer answer={turn.answer} sources={turn.sources} />
            </div>
          ) : (
            turn.message && <div className="ask-notice">{turn.message}</div>
          )}

          {turn.sources.length > 0 && (
            <ol className="ask-sources">
              {turn.sources.map((source, i) => (
                <li key={i}>
                  <span className="ask-cite">[{i + 1}]</span>{" "}
                  <SourceLink source={source}>{source.title || source.url}</SourceLink>
                </li>
              ))}
            </ol>
          )}

          {!turn.synthesisAvailable && turn.articles.length > 0 && (
            <ArticleFallbackList articles={turn.articles} />
          )}
        </div>
      ))}

      {loading && (
        <div className="ask-loading">Searching your library and synthesizing an answer…</div>
      )}

      {error && <div className="ask-error">{error}</div>}

      <form
        className="ask-form"
        onSubmit={(e) => {
          e.preventDefault();
          void ask(input.trim());
        }}
      >
        <input
          type="text"
          className="settings-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={turns.length > 0 ? "Ask a follow-up…" : "Ask about your news…"}
          aria-label="Question"
          maxLength={500}
          disabled={loading}
        />
        <button type="submit" className="settings-save-btn" disabled={loading || !input.trim()}>
          {loading ? "Asking…" : "Ask"}
        </button>
      </form>
    </div>
  );
}
