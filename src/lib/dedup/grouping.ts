import { Article } from "@/types";
import { bigramSimilarity, normalizeTitleForHash } from "./similarity";
import { getDb } from "@/lib/db";

interface GroupRow {
  id: number;
  label: string | null;
  category_id: number;
  representative_id: number;
  article_count: number;
  representative_title: string;
  representative_content: string | null;
}

function getRecentGroupsByCategory(categorySlug: string): GroupRow[] {
  const db = getDb();
  return db
    .prepare(
      `SELECT
        ag.id,
        ag.label,
        ag.category_id,
        ag.representative_id,
        ag.article_count,
        a.title AS representative_title,
        a.content AS representative_content
      FROM article_groups ag
      JOIN articles a ON a.id = ag.representative_id
      JOIN categories c ON c.id = ag.category_id
      WHERE c.slug = ?
        AND ag.created_at >= datetime('now', '-48 hours')
      ORDER BY ag.updated_at DESC`
    )
    .all(categorySlug) as GroupRow[];
}

function createGroup(
  categorySlug: string,
  articleId: number,
  label: string | null
): number {
  const db = getDb();

  const category = db
    .prepare(`SELECT id FROM categories WHERE slug = ?`)
    .get(categorySlug) as { id: number } | undefined;

  if (!category) {
    throw new Error(`Category "${categorySlug}" not found`);
  }

  const result = db
    .prepare(
      `INSERT INTO article_groups (label, category_id, representative_id, article_count)
       VALUES (?, ?, ?, 1)`
    )
    .run(label, category.id, articleId);

  const groupId = Number(result.lastInsertRowid);

  // Assign the article to this group
  db.prepare(`UPDATE articles SET group_id = ? WHERE id = ?`).run(
    groupId,
    articleId
  );

  return groupId;
}

function assignArticleToGroup(articleId: number, groupId: number): void {
  const db = getDb();
  db.prepare(`UPDATE articles SET group_id = ? WHERE id = ?`).run(
    groupId,
    articleId
  );
}

function incrementGroupCount(groupId: number): void {
  const db = getDb();
  db.prepare(
    `UPDATE article_groups
     SET article_count = article_count + 1,
         updated_at = datetime('now')
     WHERE id = ?`
  ).run(groupId);
}

function updateGroupRepresentative(
  groupId: number,
  articleId: number
): void {
  const db = getDb();
  db.prepare(
    `UPDATE article_groups SET representative_id = ?, updated_at = datetime('now') WHERE id = ?`
  ).run(articleId, groupId);
}

export function groupArticles(
  newArticles: Article[],
  categorySlug: string
): void {
  for (const article of newArticles) {
    const recentGroups = getRecentGroupsByCategory(categorySlug);

    const normalizedNewTitle = normalizeTitleForHash(article.title);

    let bestMatchGroupId: number | null = null;
    let bestMatchScore = 0;
    let bestMatchContent: string | null = null;

    for (const group of recentGroups) {
      const score = bigramSimilarity(article.title, group.representative_title);

      if (score > bestMatchScore) {
        bestMatchScore = score;
        bestMatchGroupId = group.id;
        bestMatchContent = group.representative_content;
      }
    }

    if (bestMatchGroupId !== null && bestMatchScore > 0.5) {
      // Assign to existing group
      assignArticleToGroup(article.id, bestMatchGroupId);
      incrementGroupCount(bestMatchGroupId);

      // Update representative if new article has more content
      const newContentLength = (article.content || "").length;
      const existingContentLength = (bestMatchContent || "").length;

      if (newContentLength > existingContentLength) {
        updateGroupRepresentative(bestMatchGroupId, article.id);
      }
    } else {
      // Create a new group with this article as the representative
      createGroup(categorySlug, article.id, normalizedNewTitle);
    }
  }
}
