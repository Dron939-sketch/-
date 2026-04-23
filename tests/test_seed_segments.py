"""Tests for the segmented SQL parser used by `db.seed.run_migrations`."""

from __future__ import annotations

from db.seed import _split_segments


def test_no_markers_returns_single_default_segment():
    sql = "CREATE TABLE foo (id INT);\nCREATE INDEX foo_idx ON foo (id);"
    out = _split_segments(sql)
    assert out == [("default", sql)]


def test_markers_split_into_named_segments():
    sql = """
-- @SEGMENT core
CREATE TABLE cities (id INT);

-- @SEGMENT extras
CREATE INDEX cities_trgm_idx ON cities USING gin (name);
""".strip()
    out = _split_segments(sql)
    names = [name for name, _ in out]
    assert names == ["core", "extras"]
    assert "CREATE TABLE cities" in dict(out)["core"]
    assert "CREATE INDEX cities_trgm_idx" in dict(out)["extras"]
    # Nothing from extras leaks into core.
    assert "CREATE INDEX" not in dict(out)["core"]


def test_preamble_before_first_marker_is_preserved():
    sql = """
-- Top-of-file comment
CREATE EXTENSION pg_trgm;

-- @SEGMENT core
CREATE TABLE cities (id INT);
""".strip()
    out = _split_segments(sql)
    assert [name for name, _ in out] == ["preamble", "core"]
    assert "CREATE EXTENSION pg_trgm" in dict(out)["preamble"]


def test_empty_segments_are_skipped():
    sql = """
-- @SEGMENT empty
-- @SEGMENT actual
CREATE TABLE ok (id INT);
""".strip()
    out = _split_segments(sql)
    assert [name for name, _ in out] == ["actual"]


def test_multiple_markers_keep_order():
    sql = """
-- @SEGMENT one
SELECT 1;
-- @SEGMENT two
SELECT 2;
-- @SEGMENT three
SELECT 3;
""".strip()
    out = _split_segments(sql)
    assert [name for name, _ in out] == ["one", "two", "three"]
    assert dict(out)["one"].strip() == "SELECT 1;"
    assert dict(out)["three"].strip() == "SELECT 3;"
