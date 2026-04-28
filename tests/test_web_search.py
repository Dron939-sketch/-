"""Тесты parser'а DuckDuckGo HTML (без реальных HTTP-вызовов)."""

import asyncio
from unittest.mock import patch

import pytest

from ai.web_search import _decode_ddg_link, _parse_html, search


def test_parse_html_extracts_results():
    html = """
    <html><body>
    <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpage1">
      Title <b>One</b>
    </a>
    <a class="result__snippet" href="https://example.com/page1">
      Snippet content first
    </a>
    <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpage2">
      Second Title
    </a>
    <a class="result__snippet" href="...">Second snippet</a>
    </body></html>
    """
    out = _parse_html(html, limit=5)
    assert len(out) == 2
    assert out[0]["title"] == "Title One"
    assert "Snippet content first" in out[0]["snippet"]
    assert out[0]["url"] == "https://example.com/page1"
    assert out[1]["title"] == "Second Title"


def test_parse_html_limit():
    blocks = "".join(
        f'<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fa{i}.com">T{i}</a>'
        f'<a class="result__snippet">S{i}</a>'
        for i in range(10)
    )
    out = _parse_html(blocks, limit=3)
    assert len(out) == 3


def test_parse_html_empty():
    assert _parse_html("", limit=5) == []
    assert _parse_html("<html></html>", limit=5) == []


def test_decode_ddg_link_with_uddg():
    href = "//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Ftest"
    assert _decode_ddg_link(href) == "https://example.com/test"


def test_decode_ddg_link_protocol_relative():
    assert _decode_ddg_link("//example.com/path") == "https://example.com/path"


def test_decode_ddg_link_pass_through():
    assert _decode_ddg_link("https://example.com") == "https://example.com"


# ---------------------------------------------------------------------------
# search() — мок aiohttp
# ---------------------------------------------------------------------------

class _FakeResp:
    def __init__(self, status, text):
        self.status = status
        self._text = text

    async def text(self): return self._text
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return None


class _FakeSession:
    def __init__(self, resp):
        self.resp = resp

    def post(self, url, **kw):
        return self.resp

    async def __aenter__(self): return self
    async def __aexit__(self, *a): return None


def test_search_returns_parsed():
    html = (
        '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fa.com">A</a>'
        '<a class="result__snippet">snippet</a>'
    )
    fake = _FakeSession(_FakeResp(200, html))
    with patch("ai.web_search.aiohttp.ClientSession", return_value=fake):
        out = asyncio.run(search("test", limit=3))
    assert len(out) == 1
    assert out[0]["title"] == "A"
    assert out[0]["url"] == "https://a.com"


def test_search_empty_query():
    out = asyncio.run(search(""))
    assert out == []


def test_search_http_error():
    fake = _FakeSession(_FakeResp(500, ""))
    with patch("ai.web_search.aiohttp.ClientSession", return_value=fake):
        out = asyncio.run(search("test"))
    assert out == []


def test_search_swallows_exception():
    class _Err:
        async def __aenter__(self): raise RuntimeError("network down")
        async def __aexit__(self, *a): return None
    with patch("ai.web_search.aiohttp.ClientSession", return_value=_Err()):
        out = asyncio.run(search("test"))
    assert out == []
