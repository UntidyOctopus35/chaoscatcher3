"""Tests for storage.load_json and storage.save_json."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from chaoscatcher.storage import load_json, save_json


@pytest.fixture()
def tmp_json(tmp_path: Path) -> Path:
    return tmp_path / "data.json"


# ---- save_json ----


def test_save_creates_file(tmp_json):
    save_json(tmp_json, {"key": "value"})
    assert tmp_json.exists()


def test_save_writes_valid_json(tmp_json):
    save_json(tmp_json, {"a": 1, "b": [1, 2, 3]})
    data = json.loads(tmp_json.read_text())
    assert data == {"a": 1, "b": [1, 2, 3]}


def test_save_creates_parent_dirs(tmp_path):
    deep = tmp_path / "a" / "b" / "c" / "data.json"
    save_json(deep, {"x": 1})
    assert deep.exists()


def test_save_is_atomic_no_tmp_left(tmp_json):
    save_json(tmp_json, {"x": 1})
    tmp = tmp_json.with_name(tmp_json.name + ".tmp")
    assert not tmp.exists()


def test_save_sets_permissions(tmp_json):
    save_json(tmp_json, {})
    mode = oct(os.stat(tmp_json).st_mode & 0o777)
    assert mode == "0o600"


# ---- load_json ----


def test_load_missing_returns_empty_dict(tmp_json):
    result = load_json(tmp_json)
    assert result == {}


def test_load_missing_creates_file(tmp_json):
    load_json(tmp_json)
    assert tmp_json.exists()


def test_load_empty_file_returns_empty_dict(tmp_json):
    tmp_json.write_text("", encoding="utf-8")
    result = load_json(tmp_json)
    assert result == {}


def test_load_valid_json(tmp_json):
    save_json(tmp_json, {"moods": [], "water": []})
    result = load_json(tmp_json)
    assert result == {"moods": [], "water": []}


def test_load_corrupt_returns_empty_and_backs_up(tmp_json):
    tmp_json.write_text("not valid json {{{{", encoding="utf-8")
    result = load_json(tmp_json)
    assert result == {}
    backups = list(tmp_json.parent.glob("*.corrupt-*.json"))
    assert len(backups) == 1


def test_load_non_dict_json_returns_empty(tmp_json):
    tmp_json.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    result = load_json(tmp_json)
    assert result == {}


# ---- round-trip ----


def test_roundtrip(tmp_json):
    original = {"medications": [{"ts": "2026-01-01T09:00:00", "name": "Test", "dose": "10mg"}]}
    save_json(tmp_json, original)
    result = load_json(tmp_json)
    assert result == original
