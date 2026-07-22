import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="empty">
      <div className="empty-title">Page not found</div>
      <div className="empty-desc">The page you're looking for doesn't exist.</div>
      <Link to="/" className="link" style={{ marginTop: 12 }}>
        Go home
      </Link>
    </div>
  );
}
