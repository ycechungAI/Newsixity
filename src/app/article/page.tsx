import { Suspense } from "react";
import ArticlePageClient from "./ArticlePageClient";

// Query-param based (/article?id=123), not a dynamic [id] route: article IDs
// are unbounded and grow with every RSS refresh, so generateStaticParams
// can't enumerate them for the static export the way it can for the fixed
// set of category slugs. This one static "article.html" shell is fetched
// once and reads ?id= client-side.
export default function ArticlePage() {
  return (
    <Suspense fallback={<div className="page" />}>
      <ArticlePageClient />
    </Suspense>
  );
}
