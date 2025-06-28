import json
import os
import pytest
from src.search_engine import (
    load_knowledge_base,
    search_exact,
    search_fuzzy,
    search,
    calculate_confidence_score
)

# Dati di esempio per i test
SAMPLE_KB_DATA = {
    "entries": [
        {
            "id": 1,
            "domanda": "Cos'è l'Energia?",
            "varianti_domanda": ["Definizione Energia", "Spiegazione Energia", "TermineComune"],
            "risposta": "L'energia è la capacità di un sistema di compiere lavoro."
        },
        {
            "id": 2,
            "domanda": "Cos'è Python?",
            "varianti_domanda": ["Definizione Python", "Linguaggio Python"],
            "risposta": "Python è un linguaggio di programmazione interpretato..."
        },
        {
            "id": 3,
            "domanda": "TermineComune",
            "varianti_domanda": [],
            "risposta": "Questa è la risposta per TermineComune."
        }
    ]
}

@pytest.fixture(scope="module", autouse=True)
def create_test_kb_file(tmp_path_factory):
    """Crea un file KB di test valido per tutti i test nel modulo."""
    kb_path = tmp_path_factory.mktemp("data") / "knowledge_base.json"
    with open(kb_path, 'w', encoding='utf-8') as f:
        json.dump(SAMPLE_KB_DATA, f)
    # Rende il percorso disponibile globalmente per i test (sebbene non sia la best practice di pytest)
    # è più semplice che passare tmp_path a ogni test. In alternativa, ogni test che
    # ne ha bisogno può usare la fixture.
    global VALID_KB_PATH
    VALID_KB_PATH = str(kb_path)
    return str(kb_path)

@pytest.fixture
def sample_kb():
    """Fornisce i dati della KB come oggetto Python."""
    return SAMPLE_KB_DATA["entries"]

@pytest.fixture
def sample_kb_for_fuzzy(tmp_path):
    """Crea una KB specifica per i test di fuzzy matching."""
    kb_data = {
        "entries": [
            {"id": 101, "domanda": "Cos'è l'intelligenza artificiale?", "varianti_domanda": ["Definizione IA"], "risposta": "Risposta IA"},
            {"id": 102, "domanda": "Come funziona il machine learning?", "varianti_domanda": [], "risposta": "Risposta ML"},
            {"id": 103, "domanda": "Test Driven Development", "varianti_domanda": ["TDD"], "risposta": "Risposta TDD"}
        ]
    }
    fuzzy_kb_file = tmp_path / "fuzzy_kb.json"
    with open(fuzzy_kb_file, 'w', encoding='utf-8') as f:
        json.dump(kb_data, f)
    return kb_data["entries"]

# Test per load_knowledge_base
def test_load_knowledge_base_success():
    """Verifica che il caricamento di una KB valida funzioni."""
    entries = load_knowledge_base(VALID_KB_PATH)
    assert len(entries) == 3
    assert entries[0]["id"] == 1

def test_load_knowledge_base_file_not_found():
    """Verifica che gestisca correttamente un file non trovato."""
    entries = load_knowledge_base("path/inesistente/kb.json")
    assert entries == []

def test_load_knowledge_base_invalid_json(tmp_path):
    """Verifica che gestisca correttamente un file JSON malformato."""
    invalid_json_file = tmp_path / "invalid.json"
    with open(invalid_json_file, 'w') as f:
        f.write("{'invalid_json': ")
    entries = load_knowledge_base(str(invalid_json_file))
    assert entries == []

# Test per search_exact
def test_search_exact_match_in_domanda(sample_kb):
    results = search_exact("Cos'è Python?", sample_kb)
    assert len(results) == 1
    assert results[0]["id"] == 2

def test_search_exact_match_in_varianti(sample_kb):
    results = search_exact("Linguaggio Python", sample_kb)
    assert len(results) == 1
    assert results[0]["id"] == 2

def test_search_exact_case_insensitive(sample_kb):
    results = search_exact("cos'è python?", sample_kb)
    assert len(results) == 1
    assert results[0]["id"] == 2

def test_search_exact_no_match(sample_kb):
    results = search_exact("Questa domanda non esiste", sample_kb)
    assert len(results) == 0

def test_search_exact_multiple_matches(sample_kb):
    results = search_exact("TermineComune", sample_kb)
    assert len(results) == 2
    ids_found = {entry["id"] for entry in results}
    assert {1, 3} == ids_found

# Test per search_fuzzy
def test_search_fuzzy_finds_similar_match(sample_kb_for_fuzzy):
    query = "machine learnin" # Errore di battitura
    results = search_fuzzy(query, sample_kb_for_fuzzy, threshold=80)
    assert len(results) == 1
    assert results[0][0]["id"] == 102
    assert results[0][1] >= 80

def test_search_fuzzy_respects_threshold(sample_kb_for_fuzzy):
    query = "machine learnin"
    results_high_threshold = search_fuzzy(query, sample_kb_for_fuzzy, threshold=95)
    assert len(results_high_threshold) == 0

# Test per la funzione di alto livello search
def test_search_function_success():
    results = search("Cos'è Python?", file_path=VALID_KB_PATH)
    assert len(results) >= 1
    entry, score = results[0]
    assert entry["id"] == 2
    assert score == 100.0

def test_search_function_no_match():
    results = search("Questa domanda non esiste", file_path=VALID_KB_PATH)
    assert len(results) == 0

def test_search_combines_exact_and_fuzzy_correctly(tmp_path, sample_kb_for_fuzzy):
    combined_kb_data = SAMPLE_KB_DATA["entries"] + sample_kb_for_fuzzy
    combined_kb_file = tmp_path / "combined_test_kb.json"
    with open(combined_kb_file, 'w', encoding='utf-8') as f:
        json.dump({"entries": combined_kb_data}, f)

    results_python = search("Cos'è Python?", file_path=str(combined_kb_file), fuzzy_threshold=70)
    assert len(results_python) >= 1
    assert results_python[0][0]["id"] == 2
    assert results_python[0][1] == 100.0

    ids_in_python_results = [e["id"] for e,s in results_python]
    assert ids_in_python_results.count(2) == 1

    results_ia = search("intelligenza artif", file_path=str(combined_kb_file), fuzzy_threshold=80)
    assert len(results_ia) == 1
    entry_ia, score_ia = results_ia[0]
    assert entry_ia["id"] == 101
    assert 80.0 <= score_ia < 100.0

# Test per calculate_confidence_score
class TestCalculateConfidenceScore:
    def test_exact_match_returns_100(self):
        entry = {"id": 1, "domanda": "Qualsiasi domanda"}
        query = "Qualsiasi domanda"
        assert calculate_confidence_score(query, entry, is_exact_match=True) == 100.0

    def test_fuzzy_match_calculates_score(self):
        entry = {"id": 1, "domanda": "Cos'è l'intelligenza artificiale?", "varianti_domanda": ["Definizione IA"]}
        query = "cose linteligenza artificial"
        score = calculate_confidence_score(query, entry, is_exact_match=False)
        assert 80 < score < 100

    def test_empty_query_returns_zero_score(self):
        entry = {"id": 1, "domanda": "Domanda valida"}
        assert calculate_confidence_score("", entry, is_exact_match=False) == 0.0

# Test per ordinamento e limite
class TestSortingAndLimiting:
    @pytest.fixture
    def kb_for_final_test(self, tmp_path):
        test_entries = [
            {"id": 10, "domanda": "Risposta esatta al cento per cento"},
            {"id": 20, "domanda": "Risposta simile al novanta per cento"},
            {"id": 30, "domanda": "Risposta quasi all'ottanta per cento"},
            {"id": 40, "domanda": "Questa è una risposta diversa"},
        ]
        kb_file = tmp_path / "final_test_kb.json"
        with open(kb_file, 'w', encoding='utf-8') as f:
            json.dump({"entries": test_entries}, f)
        return str(kb_file)

    def test_search_results_are_sorted_by_score(self, kb_for_final_test):
        query = "Risposta"
        results = search(query, file_path=kb_for_final_test, fuzzy_threshold=50)
        assert len(results) == 4
        scores = [score for entry, score in results]
        assert scores == sorted(scores, reverse=True), "I risultati non sono ordinati per punteggio."
        
        expected_id_order = [10, 20, 30, 40]
        actual_id_order = [entry['id'] for entry, score in results]
        assert actual_id_order == expected_id_order

    def test_limit_returns_correct_number_of_results(self, kb_for_final_test):
        query = "Risposta"
        results = search(query, file_path=kb_for_final_test, fuzzy_threshold=50, limit=2)
        assert len(results) == 2
        assert results[0][0]["id"] == 10
        assert results[1][0]["id"] == 20

    def test_limit_zero_returns_empty_list(self, kb_for_final_test):
        query = "Risposta"
        results = search(query, file_path=kb_for_final_test, fuzzy_threshold=50, limit=0)
        assert len(results) == 0

    def test_limit_greater_than_results_returns_all(self, kb_for_final_test):
        query = "Risposta"
        results = search(query, file_path=kb_for_final_test, fuzzy_threshold=50, limit=10)
        assert len(results) == 4
