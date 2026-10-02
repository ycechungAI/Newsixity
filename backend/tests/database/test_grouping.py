"""Topic grouping during refresh (lib/dedup/grouping.py).

Regression: group_articles() never ran in the Python port — a TypeError on
its first repository call was swallowed into the refresh error list, so no
group was ever created and the Topics view had nothing to group by.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

import app.db.repository.article_groups as groups_module
import app.db.repository.articles as articles_module
import app.db.repository.categories as categories_module
from app.db.models import Article, Base, Category, Feed
from app.lib.dedup.grouping import group_articles


@pytest.fixture
def db(tmp_path, monkeypatch):
    eng = create_engine(f"sqlite:///{tmp_path / 'g.db'}", connect_args={"check_same_thread": False})

    @event.listens_for(eng, "connect")
    def _fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(eng)
    factory = sessionmaker(bind=eng, autoflush=False, future=True)
    for module in (groups_module, articles_module, categories_module):
        monkeypatch.setattr(module, "SessionLocal", factory)
    with factory() as s:
        cat = Category(name="World", slug="world")
        s.add(cat)
        s.flush()
        s.add(Feed(name="F", url="https://f.example/rss", category_id=cat.id))
        s.commit()
    return factory


def _add(db, title, content=""):
    with db() as s:
        a = Article(feed_id=1, guid=title, title=title, link=f"https://f.example/{len(title)}", content=content)
        s.add(a)
        s.commit()
        return a.id


def test_similar_titles_share_a_group_and_others_get_their_own(db):
    ids = [
        _add(db, "G7 nations agree to release emergency diesel stocks", "short"),
        _add(db, "G7 nations agree to release emergency diesel stockpiles", "much longer body text"),
        _add(db, "Volcano erupts on remote island"),
    ]
    group_articles(articles_module.get_articles_by_ids(ids), "world")

    with db() as s:
        rows = s.execute(text("SELECT id, group_id FROM articles ORDER BY id")).fetchall()
        groups = s.execute(text(
            "SELECT id, representative_id, article_count FROM article_groups ORDER BY id")).fetchall()

    assert all(g is not None for _, g in rows), "every article must be grouped"
    assert rows[0][1] == rows[1][1] != rows[2][1]
    # The longer article took over as representative of the shared group.
    shared = next(g for g in groups if g[0] == rows[0][1])
    assert (shared[1], shared[2]) == (ids[1], 2)
