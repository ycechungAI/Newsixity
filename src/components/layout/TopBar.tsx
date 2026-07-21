import { RefreshButton } from "@/components/ui/RefreshButton";

export default function TopBar() {
  return (
    <div className="topbar">
      <form className="search-form" method="GET" action="/">
        <input
          className="search-input"
          type="search"
          name="search"
          placeholder="Search articles..."
          autoComplete="off"
        />
        <button className="search-btn" type="submit">Go</button>
      </form>
      <RefreshButton />
    </div>
  );
}
