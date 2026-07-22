interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onChange: (page: number) => void;
}

export default function Pagination({ currentPage, totalPages, onChange }: PaginationProps) {
  if (totalPages <= 1) return null;

  const start = Math.max(1, currentPage - 2);
  const end   = Math.min(totalPages, currentPage + 2);
  const pages: number[] = [];
  for (let i = start; i <= end; i++) pages.push(i);

  const renderButton = (page: number, label: React.ReactNode, isDisabled = false, key?: React.Key) => {
    if (isDisabled) {
      return <span key={key} className="pg-btn" style={{ opacity: .4 }}>{label}</span>;
    }
    return (
      <button
        key={key}
        onClick={() => onChange(page)}
        className="pg-btn"
      >
        {label}
      </button>
    );
  };

  return (
    <div className="pagination">
      {renderButton(currentPage - 1, "‹ Prev", currentPage <= 1)}

      {start > 1 && (
        <>
          {renderButton(1, "1")}
          {start > 2 && <span style={{ color: "var(--subtle)", padding: "0 2px" }}>…</span>}
        </>
      )}

      {pages.map(p =>
        p === currentPage
          ? <span key={p} className="pg-btn current">{p}</span>
          : renderButton(p, p, false, p)
      )}

      {end < totalPages && (
        <>
          {end < totalPages - 1 && <span style={{ color: "var(--subtle)", padding: "0 2px" }}>…</span>}
          {renderButton(totalPages, totalPages)}
        </>
      )}

      {renderButton(currentPage + 1, "Next ›", currentPage >= totalPages)}
    </div>
  );
}
