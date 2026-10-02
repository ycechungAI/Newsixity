"""Tests for POST /api/ask (Ask Newsixity, v0.4).

DB-free by design: route presence via the OpenAPI schema (same approach as
test_api_contract.py), request validation via pydantic directly, and source
normalization via the router's pure helpers. Anything needing FTS5 rows or a
running Ollama belongs in the manual end-to-end checklist instead.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.main import app
from app.routers.ask import _conversation_context, _to_source
from app.schemas import AskHistoryTurn, AskRequestBody


class TestAskRouteRegistered:
    def test_post_ask_exists_in_openapi(self):
        paths = app.openapi()["paths"]
        assert "/api/ask" in paths
        assert "post" in paths["/api/ask"]

    def test_no_double_api_prefix(self):
        assert not any(p.startswith("/api/api") for p in app.openapi()["paths"])


class TestAskRequestValidation:
    def test_empty_question_rejected(self):
        with pytest.raises(ValidationError):
            AskRequestBody(question="   ")

    def test_long_question_rejected(self):
        with pytest.raises(ValidationError):
            AskRequestBody(question="x" * 501)

    def test_history_defaults_to_empty(self):
        body = AskRequestBody(question="What happened today?")
        assert body.history == []

    def test_history_turns_accepted(self):
        body = AskRequestBody(
            question="And then?",
            history=[AskHistoryTurn(question="What happened?", answer="Things.")],
        )
        assert len(body.history) == 1


class TestSourceNormalization:
    def test_dict_hit(self):
        source = _to_source(
            {"id": 7, "title": "T", "link": "https://x.example/a",
             "summary": "A sufficiently long summary for the snippet rule."}
        )
        assert source is not None
        assert source["articleId"] == 7
        assert source["url"] == "https://x.example/a"

    def test_dataclass_like_hit(self):
        class Hit:
            id = 3
            title = "T"
            link = "https://x.example/b"
            summary = None
            content = "Content long enough to clear the minimum snippet length."

        source = _to_source(Hit())
        assert source is not None
        assert source["articleId"] == 3
        assert "Content long enough" in source["snippet"]

    def test_thin_hit_dropped(self):
        assert _to_source({"id": 1, "title": "T", "summary": "short"}) is None

    def test_untitled_hit_dropped(self):
        assert _to_source({"id": 1, "summary": "A sufficiently long summary here."}) is None


class TestConversationContext:
    def test_none_without_history(self):
        assert _conversation_context([]) is None

    def test_turns_formatted_in_order(self):
        history = [
            AskHistoryTurn(question="Q1", answer="A1"),
            AskHistoryTurn(question="Q2", answer="A2"),
        ]
        ctx = _conversation_context(history)
        assert ctx is not None
        assert "Q: Q1" in ctx and "A: A2" in ctx
        assert ctx.index("Q1") < ctx.index("Q2")

    def test_only_last_six_turns_kept(self):
        history = [AskHistoryTurn(question=f"Q{i}", answer="A") for i in range(10)]
        ctx = _conversation_context(history)
        assert "Q: Q0" not in ctx
        assert "Q: Q9" in ctx


class TestAskRoute:
    """Route-level behaviour with retrieval and Ollama stubbed out."""

    @pytest.fixture
    def client(self, monkeypatch):
        from fastapi.testclient import TestClient

        from app.routers import ask as ask_router

        async def default_model():
            return "llama3.2"

        monkeypatch.setattr(ask_router, "get_default_model", default_model)
        self.ask_router = ask_router
        return TestClient(app, base_url="http://localhost")

    HITS = [
        {"id": 11, "title": "Fed holds rates", "link": "https://x.example/fed",
         "summary": "The Federal Reserve held interest rates steady on Wednesday."},
        {"id": 12, "title": "Markets react", "link": "https://x.example/mkt",
         "summary": "Stocks rose after the central bank decision was announced."},
    ]

    def test_no_matches(self, client, monkeypatch):
        monkeypatch.setattr(self.ask_router, "search_articles", lambda *a, **k: [])
        r = client.post("/api/ask", json={"question": "anything about mars?"})
        assert r.status_code == 200
        body = r.json()
        assert body["synthesisAvailable"] is False
        assert body["answer"] is None and body["articles"] == []

    def test_question_uses_any_term_retrieval(self, client, monkeypatch):
        seen = {}

        def fake_search(*args, **kwargs):
            seen.update(kwargs)
            return []

        monkeypatch.setattr(self.ask_router, "search_articles", fake_search)
        client.post("/api/ask", json={"question": "what happened with the fed?"})
        assert seen.get("match_any") is True

    def test_follow_up_retrieval_includes_previous_question(self, client, monkeypatch):
        seen = []
        monkeypatch.setattr(self.ask_router, "search_articles",
                            lambda q, *a, **k: seen.append(q) or [])
        client.post("/api/ask", json={
            "question": "what about upscaling on it?",
            "history": [{"question": "PS5 emulation news?", "answer": "It improved [1]."}],
        })
        assert "PS5" in seen[0] and "upscaling" in seen[0]

    def test_ollama_offline_falls_back_to_articles(self, client, monkeypatch):
        from app.lib.integrations import OllamaUnavailableError

        async def offline(*a, **k):
            raise OllamaUnavailableError("down")

        monkeypatch.setattr(self.ask_router, "search_articles", lambda *a, **k: self.HITS)
        monkeypatch.setattr(self.ask_router, "answer_research_question", offline)
        body = client.post("/api/ask", json={"question": "fed rates"}).json()
        assert body["synthesisAvailable"] is False
        assert [a["id"] for a in body["articles"]] == [11, 12]
        assert "offline" in body["message"]

    def test_missing_model_falls_back_instead_of_500(self, client, monkeypatch):
        from app.lib.integrations import OllamaModelNotFoundError

        async def no_model(*a, **k):
            raise OllamaModelNotFoundError("model 'llama3.2' not found")

        monkeypatch.setattr(self.ask_router, "search_articles", lambda *a, **k: self.HITS)
        monkeypatch.setattr(self.ask_router, "answer_research_question", no_model)
        r = client.post("/api/ask", json={"question": "fed rates"})
        assert r.status_code == 200
        assert r.json()["synthesisAvailable"] is False

    def test_answer_with_citations_resolving_to_articles(self, client, monkeypatch):
        captured = {}

        async def answer(question, **kwargs):
            captured.update(kwargs)
            return "The Fed held rates [1] and stocks rose [2]."

        monkeypatch.setattr(self.ask_router, "search_articles", lambda *a, **k: self.HITS)
        monkeypatch.setattr(self.ask_router, "answer_research_question", answer)
        body = client.post(
            "/api/ask",
            json={"question": "and markets?",
                  "history": [{"question": "fed?", "answer": "Held [1]."}]},
        ).json()
        assert body["synthesisAvailable"] is True
        assert [s["articleId"] for s in body["sources"]] == [11, 12]
        # Grounding: the model only ever sees the retrieved sources...
        assert [s["title"] for s in captured["sources"]] == ["Fed holds rates", "Markets react"]
        # ...and a follow-up carries the earlier turn.
        assert "Q: fed?" in captured["conversation"]

    def test_placeholder_summary_not_used_as_snippet(self):
        source = _to_source({"id": 1, "title": "Saved link title here",
                             "summary": "[Manual link - not summarizable]",
                             "content": None})
        assert source is None or "[Manual link" not in source["snippet"]
