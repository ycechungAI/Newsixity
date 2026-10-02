import { useState } from "react";
import { useNavigate } from "react-router";

/** "Search this category" — hands off to /search with the category preset. */
export default function CategorySearchBox({ slug, name }: { slug: string; name: string }) {
  const [term, setTerm] = useState("");
  const navigate = useNavigate();

  return (
    <form
      className="search-in-category"
      role="search"
      onSubmit={(e) => {
        e.preventDefault();
        const q = term.trim();
        if (q) navigate(`/search?${new URLSearchParams({ q, category: slug })}`);
      }}
    >
      <input
        type="search"
        className="settings-input"
        value={term}
        onChange={(e) => setTerm(e.target.value)}
        placeholder={`Search ${name}…`}
        aria-label={`Search ${name}`}
      />
      <button type="submit" className="tb-btn" disabled={!term.trim()}>Search</button>
    </form>
  );
}
