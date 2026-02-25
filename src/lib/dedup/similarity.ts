const NEWS_PREFIXES =
  /^\s*(BREAKING|UPDATE|UPDATED|EXCLUSIVE|OPINION|ANALYSIS|WATCH|LIVE|DEVELOPING|JUST IN|BREAKING NEWS|REPORT|VIDEO|PHOTOS?|GALLERY|INTERVIEW|REVIEW|EXPLAINER|FACT CHECK|COLUMN|EDITORIAL|LETTER|COMMENTARY)\s*:\s*/i;

export function normalizeTitleForHash(title: string): string {
  return title
    .toLowerCase()
    .replace(NEWS_PREFIXES, "")
    .replace(/[^\w\s]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function hashTitle(title: string): string {
  return normalizeTitleForHash(title);
}

export function getBigrams(str: string): string[] {
  const bigrams: string[] = [];
  for (let i = 0; i < str.length - 1; i++) {
    bigrams.push(str.substring(i, i + 2));
  }
  return bigrams;
}

export function bigramSimilarity(a: string, b: string): number {
  const normalizedA = normalizeTitleForHash(a);
  const normalizedB = normalizeTitleForHash(b);

  if (normalizedA === normalizedB) return 1;
  if (normalizedA.length < 2 || normalizedB.length < 2) return 0;

  const bigramsA = getBigrams(normalizedA);
  const bigramsB = getBigrams(normalizedB);

  if (bigramsA.length === 0 || bigramsB.length === 0) return 0;

  const setB = new Map<string, number>();
  for (const bigram of bigramsB) {
    setB.set(bigram, (setB.get(bigram) || 0) + 1);
  }

  let intersectionSize = 0;
  const usedB = new Map<string, number>();

  for (const bigram of bigramsA) {
    const availableInB = (setB.get(bigram) || 0) - (usedB.get(bigram) || 0);
    if (availableInB > 0) {
      intersectionSize++;
      usedB.set(bigram, (usedB.get(bigram) || 0) + 1);
    }
  }

  // Dice coefficient: 2 * |intersection| / (|A| + |B|)
  return (2 * intersectionSize) / (bigramsA.length + bigramsB.length);
}

export function isDuplicate(
  newTitle: string,
  existingTitle: string,
  threshold: number = 0.7
): boolean {
  return bigramSimilarity(newTitle, existingTitle) >= threshold;
}
