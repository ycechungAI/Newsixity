"""Tests for FTS5 full-text article search (app.db.repository.articles.search_articles).

Builds a temp on-disk SQLite DB per test (mirrors test_schema.py's approach),
then monkeypatches app.db.repository.articles.SessionLocal — the module
binds that name via `from app.db.session import SessionLocal`, so it must be
patched on the articles module itself, not app.db.session — to point at the
temp DB. This lets search_articles() run its real code path (including the
raw-SQL MATCH/bm25 query) against data we control, instead of mocking it out.
"""

import app.db.repository.articles as articles_module
import pytest
from app.db.init_db import init_fts5_search
from app.db.models import Article, Base, Category, Feed
from app.db.repository.articles import _fts5_available, _sanitize_fts5_query, search_articles
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def engine(tmp_path):
    """A real on-disk SQLite DB (not :memory:) so the sessionmaker's
    connection-per-session pooling behaves like production."""
    db_path = tmp_path / "search_test.db"
    eng = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False}, future=True)

    def enable_fk(dbapi_conn, connection_record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    event.listen(eng, "connect", enable_fk)
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@pytest.fixture
def fts5_db(session_factory, monkeypatch):
    """Point search_articles' SessionLocal at the temp DB and build the
    articles_fts index over it, mirroring what init_db() does at startup."""
    monkeypatch.setattr(articles_module, "SessionLocal", session_factory)
    with session_factory() as session:
        ok = init_fts5_search(session)
    assert ok, (
        "FTS5 was verified available in this dev venv (SQLite 3.51.0, ENABLE_FTS5); "
        "if this fails, the environment changed since that check."
    )
    return session_factory


@pytest.fixture
def like_only_db(session_factory, monkeypatch):
    """Same temp DB, but WITHOUT the articles_fts table — exercises the
    fallback path for SQLite builds without FTS5 compiled in."""
    monkeypatch.setattr(articles_module, "SessionLocal", session_factory)
    return session_factory


def _seed_article(session_factory, *, category_slug, title, content, summary=None, feed_name=None, feed_url=None):
    """Insert a category/feed/article triple, reusing an existing category
    by slug if one was already created in this test."""
    with session_factory() as session:
        category = session.query(Category).filter_by(slug=category_slug).one_or_none()
        if category is None:
            category = Category(name=category_slug.title(), slug=category_slug, sort_order=0)
            session.add(category)
            session.commit()

        feed = Feed(
            category_id=category.id,
            name=feed_name or f"Feed for {title}",
            url=feed_url or f"https://example.com/feeds/{title.replace(' ', '-').lower()}",
        )
        session.add(feed)
        session.commit()

        article = Article(
            feed_id=feed.id,
            guid=f"guid-{title}",
            title=title,
            link=f"https://example.com/articles/{title.replace(' ', '-').lower()}",
            content=content,
            summary=summary,
        )
        session.add(article)
        session.commit()
        return article.id


class TestSanitizeFts5Query:
    """Unit tests for the FTS5 query sanitizer — the piece that stops raw
    user input from breaking or hijacking FTS5's query syntax."""

    def test_plain_words_become_quoted_and_joined(self):
        assert _sanitize_fts5_query("hello world") == '"hello" AND "world"'

    def test_strips_fts5_operator_syntax(self):
        # Every token — including bare FTS5 keywords like OR/NEAR — comes out
        # individually double-quoted, so none of them can act as an operator
        # or column filter; the sanitizer doesn't try to recognise or drop
        # them, it just neutralises them by construction.
        result = _sanitize_fts5_query('"quoted" OR wild* -exclude NEAR/2 col:value')
        assert result == '"quoted" AND "OR" AND "wild" AND "exclude" AND "NEAR" AND "2" AND "col" AND "value"'

    def test_empty_or_symbols_only_returns_empty_string(self):
        assert _sanitize_fts5_query("") == ""
        assert _sanitize_fts5_query("!!! *** ---") == ""

    def test_does_not_raise_on_adversarial_input(self):
        adversarial = ['"; DROP TABLE articles; --', "*" * 500, "NEAR(a b, 10)", "a\"b\"c", "🔥emoji🔥"]
        for q in adversarial:
            # Must not raise — that's the whole point of sanitizing.
            _sanitize_fts5_query(q)


class TestFts5Probe:
    def test_available_when_table_exists(self, fts5_db):
        with fts5_db() as session:
            assert _fts5_available(session) is True

    def test_unavailable_when_table_missing(self, like_only_db):
        with like_only_db() as session:
            assert _fts5_available(session) is False


class TestSearchFindsBodyOnlyMatches:
    """The core win this feature exists for: a term that appears only in the
    article body (never the title) must now be found."""

    def test_finds_term_that_only_appears_in_content(self, fts5_db):
        article_id = _seed_article(
            fts5_db,
            category_slug="technology",
            title="Completely Unrelated Headline",
            content="This article discusses the migratory habits of the xylophonemania beetle in depth.",
        )

        results = search_articles("xylophonemania")

        assert [a.id for a in results] == [article_id]

    def test_finds_term_that_only_appears_in_summary(self, fts5_db):
        article_id = _seed_article(
            fts5_db,
            category_slug="technology",
            title="Another Unrelated Headline",
            content="Nothing special here.",
            summary="A rare mention of quetzalcoatlus appears in this summary only.",
        )

        results = search_articles("quetzalcoatlus")

        assert [a.id for a in results] == [article_id]

    def test_title_only_match_still_works(self, fts5_db):
        article_id = _seed_article(
            fts5_db,
            category_slug="technology",
            title="Breaking Narwhal News",
            content="No distinguishing terms here.",
        )

        results = search_articles("narwhal")

        assert [a.id for a in results] == [article_id]

    def test_no_match_returns_empty_list(self, fts5_db):
        _seed_article(
            fts5_db,
            category_slug="technology",
            title="Something",
            content="Something else entirely.",
        )

        assert search_articles("nonexistentterm12345") == []


class TestSearchRelevanceOrdering:
    def test_higher_term_frequency_ranks_first(self, fts5_db):
        low_relevance_id = _seed_article(
            fts5_db,
            category_slug="technology",
            title="Wildlife Roundup",
            content="A single gorilla was spotted near the reserve.",
        )
        high_relevance_id = _seed_article(
            fts5_db,
            category_slug="technology",
            title="Gorilla Troop Documentary",
            content=(
                "Gorilla behavior fascinates researchers. This gorilla troop, led by a "
                "silverback gorilla, was observed for months. Gorilla family bonds run deep."
            ),
        )

        results = search_articles("gorilla")
        result_ids = [a.id for a in results]

        assert high_relevance_id in result_ids
        assert low_relevance_id in result_ids
        assert result_ids.index(high_relevance_id) < result_ids.index(low_relevance_id)


class TestSearchCategoryFilter:
    def test_category_filter_applies_on_fts5_path(self, fts5_db):
        tech_id = _seed_article(
            fts5_db,
            category_slug="technology",
            title="Quokka Sighting in Tech Park",
            content="A quokka wandered into the office.",
        )
        _seed_article(
            fts5_db,
            category_slug="finance",
            title="Quokka Mascot Boosts Sales",
            content="The quokka mascot theme continued.",
        )

        results = search_articles("quokka", category="technology")

        assert [a.id for a in results] == [tech_id]

    def test_category_filter_applies_on_like_fallback(self, like_only_db):
        tech_id = _seed_article(
            like_only_db,
            category_slug="technology",
            title="Platypus Update Tech Edition",
            content="irrelevant",
        )
        _seed_article(
            like_only_db,
            category_slug="finance",
            title="Platypus Update Finance Edition",
            content="irrelevant",
        )

        results = search_articles("Platypus", category="technology")

        assert [a.id for a in results] == [tech_id]


class TestSearchSpecialCharacters:
    """User queries containing FTS5 syntax characters must never raise, and
    should still match on whatever word content they contain."""

    @pytest.mark.parametrize(
        "query",
        [
            '"quoted phrase"',
            "wildcard*",
            "AND OR NOT",
            "term1 NEAR/3 term2",
            "-exclude this",
            'col:value',
            "unterminated \" quote",
            "!!!only-symbols***",
            "",
        ],
    )
    def test_does_not_raise(self, fts5_db, query):
        _seed_article(
            fts5_db,
            category_slug="technology",
            title="Baseline Article",
            content="baseline content",
        )

        # Must not raise regardless of what characters/keywords are present.
        search_articles(query)

    def test_finds_word_content_despite_surrounding_syntax(self, fts5_db):
        # The sanitizer AND-joins every token it extracts (see
        # _sanitize_fts5_query), so a query is only ever a *stricter*
        # search than intended, never a broken/injected one — punctuation
        # and operator keywords around real words just get stripped, not
        # dropped from the requirement to match.
        article_id = _seed_article(
            fts5_db,
            category_slug="technology",
            title="Cheetah Speed Study",
            content="The cheetah is known for its incredible speed on land.",
        )

        results = search_articles('"cheetah"* "speed"!!!')

        assert article_id in [a.id for a in results]


class TestSearchLikeFallback:
    """When articles_fts isn't available, search_articles must still work —
    via the pre-FTS5 title-only LIKE path."""

    def test_title_match_found_via_like(self, like_only_db):
        article_id = _seed_article(
            like_only_db,
            category_slug="technology",
            title="Falcon Spotted Downtown",
            content="No matching term in content.",
        )

        results = search_articles("falcon")

        assert [a.id for a in results] == [article_id]

    def test_body_only_term_not_found_via_like(self, like_only_db):
        """Confirms the fallback really is the old title-only behaviour: a
        term that only exists in content is invisible without FTS5."""
        _seed_article(
            like_only_db,
            category_slug="technology",
            title="Unrelated Title Here",
            content="This mentions supercalifragilisticexpialidocious only here.",
        )

        results = search_articles("supercalifragilisticexpialidocious")

        assert results == []

    def test_special_characters_do_not_raise_on_like_path(self, like_only_db):
        _seed_article(
            like_only_db,
            category_slug="technology",
            title="Baseline",
            content="content",
        )
        search_articles('"weird" * query- AND stuff')


class TestPrefixMatching:
    """The search box widens the final token so typing feels responsive.

    FTS5 matches whole tokens, so without this a search box appears broken
    mid-word — the old LIKE search matched substrings, and users expect that.
    """

    def _seed(self, fts5_db):
        return _seed_article(
            fts5_db,
            category_slug="technology",
            title="Google announces a new model",
            content="body text",
        )

    def test_partial_last_word_matches(self, fts5_db):
        article_id = self._seed(fts5_db)
        assert [a.id for a in search_articles("goog", prefix=True)] == [article_id]

    def test_partial_word_does_not_match_without_prefix(self, fts5_db):
        self._seed(fts5_db)
        assert search_articles("goog") == []

    def test_earlier_tokens_stay_exact(self, fts5_db):
        """Only the final token is widened; finished words must stay precise."""
        self._seed(fts5_db)
        # "annou" is in complete-word position here, so it must not match.
        assert search_articles("annou google", prefix=True) == []

    def test_full_word_still_matches_with_prefix_on(self, fts5_db):
        article_id = self._seed(fts5_db)
        assert [a.id for a in search_articles("google", prefix=True)] == [article_id]

    def test_prefix_still_rejects_operator_characters(self, fts5_db):
        self._seed(fts5_db)
        for hostile in ['goog" OR "x', "goog*", "goog:title", "NEAR/2 goog"]:
            search_articles(hostile, prefix=True)  # must not raise

    def test_prefix_on_punctuation_only_query_is_safe(self, fts5_db):
        assert search_articles("!!!", prefix=True) == []


class TestSanitizerPrefixForm:
    def test_star_sits_outside_the_quotes(self):
        """Inside the quotes the * would be a literal, not a prefix operator."""
        assert _sanitize_fts5_query("google news", prefix=True) == '"google" AND "news"*'

    def test_no_prefix_by_default(self):
        assert _sanitize_fts5_query("google news") == '"google" AND "news"'
