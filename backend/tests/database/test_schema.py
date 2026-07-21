"""Tests for database schema and table structure."""

import pytest
from sqlalchemy import create_engine, text, inspect, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from app.db.models import Base, Category, Feed, Article, Setting, StockWatchlist, UserPreference


@pytest.fixture
def engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    # Enable foreign key constraints for SQLite
    def enable_fk(dbapi_conn, connection_record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    event.listen(engine, "connect", enable_fk)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create a session for database operations."""
    Session = sessionmaker(bind=engine)
    sess = Session()
    yield sess
    sess.close()


class TestSchemaTables:
    """Tests for database table existence."""

    def test_categories_table_exists(self, engine):
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "categories" in tables

    def test_feeds_table_exists(self, engine):
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "feeds" in tables

    def test_articles_table_exists(self, engine):
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "articles" in tables

    def test_settings_table_exists(self, engine):
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "settings" in tables

    def test_stock_watchlist_table_exists(self, engine):
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "stock_watchlist" in tables

    def test_user_preferences_table_exists(self, engine):
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        assert "user_preferences" in tables


class TestCategoriesTable:
    """Tests for categories table constraints."""

    def test_inserts_category_successfully(self, session):
        category = Category(name="Test", slug="test", sort_order=10)
        session.add(category)
        session.commit()
        assert category.id is not None

    def test_enforces_unique_name_constraint(self, session, engine):
        cat1 = Category(name="Unique Name", slug="slug1", sort_order=1)
        session.add(cat1)
        session.commit()

        # Try to add duplicate name
        cat2 = Category(name="Unique Name", slug="slug2", sort_order=2)
        session.add(cat2)
        with pytest.raises(Exception):  # IntegrityError
            session.commit()

    def test_enforces_unique_slug_constraint(self, session):
        cat1 = Category(name="Name1", slug="unique-slug", sort_order=1)
        session.add(cat1)
        session.commit()

        cat2 = Category(name="Name2", slug="unique-slug", sort_order=2)
        session.add(cat2)
        with pytest.raises(Exception):  # IntegrityError
            session.commit()


class TestFeedsTable:
    """Tests for feeds table constraints."""

    def test_inserts_feed_successfully(self, session):
        category = Category(name="Tech", slug="tech", sort_order=1)
        session.add(category)
        session.commit()

        feed = Feed(
            category_id=category.id,
            name="Test Feed",
            url="https://example.com/rss.xml"
        )
        session.add(feed)
        session.commit()
        assert feed.id is not None

    def test_enforces_unique_url_constraint(self, session):
        category = Category(name="Tech", slug="tech", sort_order=1)
        session.add(category)
        session.commit()

        feed1 = Feed(
            category_id=category.id,
            name="Feed 1",
            url="https://example.com/rss.xml"
        )
        session.add(feed1)
        session.commit()

        feed2 = Feed(
            category_id=category.id,
            name="Feed 2",
            url="https://example.com/rss.xml"
        )
        session.add(feed2)
        with pytest.raises(Exception):  # IntegrityError
            session.commit()

    def test_enforces_foreign_key_constraint(self, session):
        feed = Feed(
            category_id=99999,
            name="Orphan Feed",
            url="https://orphan.com/rss.xml"
        )
        session.add(feed)
        with pytest.raises(IntegrityError):
            session.commit()

    def test_enabled_defaults_to_true(self, session):
        category = Category(name="Tech", slug="tech", sort_order=1)
        session.add(category)
        session.commit()

        feed = Feed(
            category_id=category.id,
            name="Test Feed",
            url="https://example.com/rss.xml"
        )
        session.add(feed)
        session.commit()
        assert feed.enabled == 1


class TestArticlesTable:
    """Tests for articles table constraints."""

    @pytest.fixture
    def feed(self, session):
        category = Category(name="Finance", slug="finance", sort_order=1)
        session.add(category)
        session.commit()

        feed = Feed(
            category_id=category.id,
            name="Finance Feed",
            url="https://finance.com/rss.xml"
        )
        session.add(feed)
        session.commit()
        return feed

    def test_inserts_article_successfully(self, session, feed):
        article = Article(
            feed_id=feed.id,
            guid="guid-001",
            title="Test Article",
            link="https://example.com/article/1"
        )
        session.add(article)
        session.commit()
        assert article.id is not None

    def test_is_read_defaults_to_false(self, session, feed):
        article = Article(
            feed_id=feed.id,
            guid="guid-001",
            title="Test",
            link="https://example.com/1"
        )
        session.add(article)
        session.commit()
        assert article.is_read == 0

    def test_is_saved_defaults_to_false(self, session, feed):
        article = Article(
            feed_id=feed.id,
            guid="guid-002",
            title="Test",
            link="https://example.com/2"
        )
        session.add(article)
        session.commit()
        assert article.is_saved == 0

    def test_enforces_unique_feed_id_guid_constraint(self, session, feed):
        article1 = Article(
            feed_id=feed.id,
            guid="guid-001",
            title="Article 1",
            link="https://example.com/1"
        )
        session.add(article1)
        session.commit()

        article2 = Article(
            feed_id=feed.id,
            guid="guid-001",
            title="Article 2",
            link="https://example.com/2"
        )
        session.add(article2)
        with pytest.raises(Exception):  # IntegrityError
            session.commit()

    def test_enforces_foreign_key_constraint(self, session):
        article = Article(
            feed_id=99999,
            guid="guid-orphan",
            title="Orphan",
            link="https://orphan.com/1"
        )
        session.add(article)
        with pytest.raises(IntegrityError):
            session.commit()


class TestSettingsTable:
    """Tests for settings table constraints."""

    def test_inserts_setting_successfully(self, session):
        setting = Setting(key="theme", value="dark")
        session.add(setting)
        session.commit()
        assert setting.key == "theme"

    def test_enforces_unique_key_constraint(self, session):
        setting1 = Setting(key="theme", value="dark")
        session.add(setting1)
        session.commit()

        setting2 = Setting(key="theme", value="light")
        session.add(setting2)
        with pytest.raises(Exception):  # IntegrityError
            session.commit()


class TestStockWatchlistTable:
    """Tests for stock_watchlist table constraints."""

    def test_inserts_stock_successfully(self, session):
        stock = StockWatchlist(symbol="AAPL", name="Apple Inc.")
        session.add(stock)
        session.commit()
        assert stock.symbol == "AAPL"

    def test_enforces_unique_symbol_constraint(self, session):
        stock1 = StockWatchlist(symbol="AAPL", name="Apple Inc.")
        session.add(stock1)
        session.commit()

        stock2 = StockWatchlist(symbol="AAPL", name="Apple")
        session.add(stock2)
        with pytest.raises(Exception):  # IntegrityError
            session.commit()


class TestUserPreferencesTable:
    """Tests for user_preferences table constraints."""

    def test_inserts_preference_successfully(self, session):
        pref = UserPreference(
            category_slug="technology",
            keyword="ai",
            weight=2.5,
            source="manual"
        )
        session.add(pref)
        session.commit()
        assert pref.keyword == "ai"

    def test_enforces_unique_category_keyword_constraint(self, session):
        pref1 = UserPreference(
            category_slug="technology",
            keyword="ai",
            weight=2.5,
            source="manual"
        )
        session.add(pref1)
        session.commit()

        pref2 = UserPreference(
            category_slug="technology",
            keyword="ai",
            weight=1.0,
            source="auto"
        )
        session.add(pref2)
        with pytest.raises(Exception):  # IntegrityError
            session.commit()

    def test_allows_same_keyword_in_different_categories(self, session):
        pref1 = UserPreference(
            category_slug="technology",
            keyword="ai",
            weight=2.5,
            source="manual"
        )
        session.add(pref1)
        session.commit()

        pref2 = UserPreference(
            category_slug="finance",
            keyword="ai",
            weight=1.0,
            source="auto"
        )
        session.add(pref2)
        session.commit()
        assert pref2.keyword == "ai"
