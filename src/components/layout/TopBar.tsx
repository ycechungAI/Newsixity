import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { RefreshButton } from "@/components/ui/RefreshButton";

export default function TopBar() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [term, setTerm] = useState("");

  // Keep the box in step with the URL, so a reload or a back/forward step
  // shows the term that produced the results on screen. Previously this form
  // submitted to "/" with a `search` param that nothing read, so typing a
  // query just reloaded the front page.
  useEffect(() => {
    setTerm(params.get("q") ?? "");
  }, [params]);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const q = term.trim();
    if (q) navigate(`/search?q=${encodeURIComponent(q)}`);
  }

  // v0.4 Ask Newsixity: same box, but answered from the article library
  // instead of a result list.
  function onAsk() {
    const q = term.trim();
    navigate(q ? `/ask?q=${encodeURIComponent(q)}` : "/ask");
  }

  return (
    <div className="topbar">
      <form className="search-form" onSubmit={onSubmit} role="search">
        <input
          className="search-input"
          type="search"
          name="q"
          value={term}
          onChange={(e) => setTerm(e.target.value)}
          placeholder="Search articles..."
          autoComplete="off"
          aria-label="Search articles"
        />
        <button className="search-btn" type="submit">Go</button>
        <button className="search-btn" type="button" onClick={onAsk} title="Ask Newsixity — synthesized answer from your library">Ask</button>
      </form>
      <RefreshButton />
    </div>
  );
}
