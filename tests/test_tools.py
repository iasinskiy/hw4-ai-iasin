import json
import pytest
from tools import calculate, lookup


# --- CALCULATE TESTS ---


def test_calculate_required_expression():
    """B2 requirement: calculate gets 48317 * 1.0947 right."""
    res = calculate("48317 * 1.0947")
    assert float(res) == pytest.approx(52892.6201, rel=1e-5)


def test_calculate_refuse_import_os():
    """B2 requirement: refuses __import__('os').system('echo hi')."""
    res = json.loads(calculate("__import__('os').system('echo hi')"))
    assert "error" in res


def test_calculate_refuse_class_attribute():
    """B2 requirement: refuses (1).__class__."""
    res = json.loads(calculate("(1).__class__"))
    assert "error" in res


def test_calculate_refuse_overflow_power():
    """B2 requirement: refuses 9**9**9 without freezing/crashing."""
    res = json.loads(calculate("9**9**9"))
    assert "error" in res


def test_calculate_division_by_zero():
    """B2 requirement: handles division by zero safely."""
    res = json.loads(calculate("100 / 0"))
    assert "error" in res
    assert res["error"] == "Division by zero"


# --- LOOKUP TESTS ---


def test_lookup_finds_2025_number(tmp_path):
    """B2 requirement: lookup finds a correct 2025 number."""
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(
        json.dumps(
            {
                "doc_id": "NR-01",
                "title": "Oakhaven",
                "text": "2025 consumption was 12400 kL.",
            }
        ),
        encoding="utf-8",
    )
    res = json.loads(lookup("Oakhaven", corpus_path=str(corpus)))
    assert isinstance(res, list)
    assert "12400" in res[0]["snippet"]


def test_lookup_misspelled_name():
    """B2 requirement: lookup handles misspelled name (Ossbrige)."""
    res = json.loads(lookup("Ossbrige"))
    assert "error" in res
    assert "did you mean Ossbridge or Ossford?" in res["error"]


def test_lookup_archived_profile():
    """B2 requirement: lookup handles archived profile request (NR-13)."""
    res = json.loads(lookup("NR-13"))
    assert "error" in res
    assert "archived" in res["error"]


def test_lookup_not_found(tmp_path):
    """B2 requirement: handles missing queries safely."""
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(
        json.dumps({"doc_id": "NR-01", "title": "Test", "text": "Sample"}),
        encoding="utf-8",
    )
    res = json.loads(lookup("non_existent_query", corpus_path=str(corpus)))
    assert "error" in res


def test_lookup_returns_snippet_not_full_doc(tmp_path):
    """B2 requirement: returns a limited amount of text."""
    long_text = "A" * 1000
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(
        json.dumps({"doc_id": "NR-02", "title": "LongDoc", "text": long_text}),
        encoding="utf-8",
    )
    res = json.loads(lookup("LongDoc", corpus_path=str(corpus)))
    assert len(res[0]["snippet"]) <= 305