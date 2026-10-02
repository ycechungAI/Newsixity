const ENTITIES: Record<string, string> = {
  "&amp;": "&",
  "&lt;": "<",
  "&gt;": ">",
  "&quot;": '"',
  "&#x27;": "'",
  "&#39;": "'",
};

function decode(text: string): string {
  return text.replace(/&(amp|lt|gt|quot|#x27|#39);/g, (m) => ENTITIES[m] ?? m);
}

/**
 * Render a search snippet whose only markup is <mark>…</mark>.
 *
 * The server HTML-escapes the snippet and then inserts the markers. This
 * never hands the string to innerHTML: it splits on the two marker tags,
 * decodes the escaped text, and lets React escape it again — so anything
 * else that looks like a tag is shown as text, not run.
 */
export default function Highlight({ snippet }: { snippet: string }) {
  const parts = snippet.split(/(<mark>|<\/mark>)/);
  let marked = false;
  const out: React.ReactNode[] = [];
  parts.forEach((part, i) => {
    if (part === "<mark>") marked = true;
    else if (part === "</mark>") marked = false;
    else if (part) out.push(marked ? <mark key={i}>{decode(part)}</mark> : decode(part));
  });
  return <>{out}</>;
}
