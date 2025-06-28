import pytest
import json
import os
from src.search_engine import load_knowledge_base, search_exact, search

# Percorso base per i file di test
# Si assume che i test vengano eseguiti dalla root del progetto
TEST_DATA_DIR = os.path.join('tests', 'test_data')
VALID_KB_PATH = os.path.join(TEST_DATA_DIR, 'valid_kb.json')
MALFORMED_KB_PATH = os.path.join(TEST_DATA_DIR, 'malformed_kb.json')
EMPTY_LIST_KB_PATH = os.path.join(TEST_DATA_DIR, 'empty_list_kb.json')
WRONG_STRUCTURE_KB_PATH = os.path.join(TEST_DATA_DIR, 'wrong_structure_kb.json')

# Dati di esempio per la knowledge base valida
SAMPLE_KB_DATA = {
    "entries": [
        {
            "id": 1, "domanda": "Cos'è l'Energia?", "varianti_domanda": ["Definizione energia", "TermineComune"],
            "risposta": "L'energia è la capacità di compiere lavoro.", "level": "general", "specificity_score": 10
        },
        {
            "id": 2, "domanda": "Cos'è Python?", "varianti_domanda": ["Definizione Python", "Linguaggio Python"],
            "risposta": "Python è un linguaggio di programmazione.", "level": "specific", "specificity_score": 50
        },
        {
            "id": 3, "domanda": "TermineComune", "varianti_domanda": ["Variante XYZ", "Altra Variante Python"], # Modificato per test
            "risposta": "Risposta per TermineComune.", "level": "general", "specificity_score": 20
        }
    ]
}
SAMPLE_KB_LIST_DATA = SAMPLE_KB_DATA["entries"] # Per testare il caricamento di una lista diretta

@pytest.fixture(scope="session", autouse=True)
def setup_test_knowledge_bases():
    """
    Crea i file JSON di test prima che i test vengano eseguiti e li pulisce dopo.
    L'autouse=True assicura che venga eseguito automaticamente per la sessione.
    """
    os.makedirs(TEST_DATA_DIR, exist_ok=True)

    with open(VALID_KB_PATH, 'w', encoding='utf-8') as f:
        json.dump(SAMPLE_KB_DATA, f, ensure_ascii=False, indent=2)

    with open(MALFORMED_KB_PATH, 'w', encoding='utf-8') as f:
        f.write("{'invalid_json': ") # JSON non valido intenzionalmente

    with open(EMPTY_LIST_KB_PATH, 'w', encoding='utf-8') as f:
        json.dump([], f) # KB che è una lista vuota

    with open(WRONG_STRUCTURE_KB_PATH, 'w', encoding='utf-8') as f:
        json.dump({"data": "valore"}, f) # Struttura non valida (né lista, né dict con 'entries')

    yield # Permette ai test di essere eseguiti

    # Cleanup dopo i test
    os.remove(VALID_KB_PATH)
    os.remove(MALFORMED_KB_PATH)
    os.remove(EMPTY_LIST_KB_PATH)
    os.remove(WRONG_STRUCTURE_KB_PATH)
    os.rmdir(TEST_DATA_DIR)

# Test per load_knowledge_base
def test_load_knowledge_base_success_dict_format():
    """Testa il caricamento corretto da un file JSON con struttura dict 'entries'."""
    entries = load_knowledge_base(VALID_KB_PATH)
    assert len(entries) == 3
    assert entries[0]["domanda"] == "Cos'è l'Energia?"

def test_load_knowledge_base_success_list_format(tmp_path):
    """Testa il caricamento corretto da un file JSON che è direttamente una lista."""
    list_kb_file = tmp_path / "list_kb.json"
    with open(list_kb_file, 'w', encoding='utf-8') as f:
        json.dump(SAMPLE_KB_LIST_DATA, f, ensure_ascii=False, indent=2)
    entries = load_knowledge_base(str(list_kb_file))
    assert len(entries) == 3
    assert entries[0]["domanda"] == "Cos'è l'Energia?"


def test_load_knowledge_base_file_not_found(capsys):
    """Testa la gestione di FileNotFoundError."""
    entries = load_knowledge_base("path/inesistente/kb.json")
    assert entries == []
    captured = capsys.readouterr()
    assert "Errore: File della knowledge base non trovato" in captured.out

def test_load_knowledge_base_json_decode_error(capsys):
    """Testa la gestione di json.JSONDecodeError."""
    entries = load_knowledge_base(MALFORMED_KB_PATH)
    assert entries == []
    captured = capsys.readouterr()
    assert "Errore: Il file della knowledge base" in captured.out
    assert "non è un JSON valido" in captured.out

def test_load_knowledge_base_wrong_structure(capsys):
    """Testa la gestione di un JSON valido ma con struttura errata."""
    entries = load_knowledge_base(WRONG_STRUCTURE_KB_PATH)
    assert entries == []
    captured = capsys.readouterr()
    assert "non ha la struttura attesa" in captured.out

# Test per search_exact
@pytest.fixture
def sample_kb():
    """Fixture per fornire la knowledge base di esempio ai test di search_exact."""
    return SAMPLE_KB_DATA["entries"]

def test_search_exact_match_in_domanda(sample_kb):
    """Testa la corrispondenza esatta nel campo 'domanda'."""
    results = search_exact("Cos'è Python?", sample_kb)
    assert len(results) == 1
    assert results[0]["id"] == 2

def test_search_exact_match_in_varianti(sample_kb):
    """Testa la corrispondenza esatta in 'varianti_domanda'."""
    results = search_exact("Definizione energia", sample_kb)
    assert len(results) == 1
    assert results[0]["id"] == 1

def test_search_exact_case_insensitivity(sample_kb):
    """Testa che la ricerca sia case-insensitive."""
    results_domanda = search_exact("cos'è l'energia?", sample_kb)
    assert len(results_domanda) == 1
    assert results_domanda[0]["id"] == 1

    results_variante = search_exact("linguaggio PYTHON", sample_kb)
    assert len(results_variante) == 1
    assert results_variante[0]["id"] == 2


def test_search_exact_multiple_matches_different_entries(sample_kb):
    """Testa quando una query matcha diverse entry (una su domanda, una su variante)."""
    results = search_exact("TermineComune", sample_kb)
    assert len(results) == 2
    ids_found = sorted([r['id'] for r in results])
    assert ids_found == [1, 3] # Entry 1 ha "TermineComune" in varianti, Entry 3 in domanda

def test_search_exact_match_other_variant(sample_kb):
    """Testa un match su un'altra variante per assicurare che il loop interno funzioni."""
    results = search_exact("Altra Variante Python", sample_kb)
    assert len(results) == 1
    assert results[0]["id"] == 3


def test_search_exact_no_match(sample_kb):
    """Testa il caso in cui non ci sono corrispondenze."""
    results = search_exact("Query Inesistente", sample_kb)
    assert len(results) == 0

def test_search_exact_empty_query(sample_kb):
    """Testa con una query vuota."""
    results = search_exact("", sample_kb)
    assert len(results) == 0

def test_search_exact_empty_kb():
    """Testa con una knowledge base vuota."""
    results = search_exact("Qualsiasi Query", [])
    assert len(results) == 0

def test_search_exact_query_not_string(sample_kb):
    """Testa quando la query non è una stringa."""
    results = search_exact(123, sample_kb)
    assert len(results) == 0

def test_search_exact_kb_not_list():
    """Testa quando la knowledge_base non è una lista."""
    results = search_exact("Qualsiasi Query", {"not_a_list": "data"})
    assert len(results) == 0

def test_search_exact_entry_without_domanda_or_varianti(sample_kb):
    """Testa entry senza 'domanda' o 'varianti_domanda'."""
    kb_con_entry_malformata = sample_kb + [{"id": 4, "risposta": "Solo risposta"}]
    results = search_exact("Solo risposta", kb_con_entry_malformata)
    assert len(results) == 0 # Non dovrebbe matchare sulla risposta
    results_domanda_mancante = search_exact("Domanda Test", kb_con_entry_malformata)
    assert len(results_domanda_mancante) == 0


# Test per la funzione search di alto livello
def test_search_function_success():
    """Testa l'integrazione della funzione search (caricamento + ricerca esatta)."""
    # Usa VALID_KB_PATH creato dalla fixture autouse
    results = search("Cos'è Python?", file_path=VALID_KB_PATH)
    assert len(results) == 1
    assert results[0]["id"] == 2

def test_search_function_no_match():
    """Testa la funzione search quando non ci sono corrispondenze."""
    results = search("Query Super Specifica Inesistente", file_path=VALID_KB_PATH)
    assert len(results) == 0

def test_search_function_kb_load_error():
    """Testa la funzione search quando il caricamento della KB fallisce."""
    results = search("Qualsiasi Query", file_path="path/inesistente/kb.json")
    assert len(results) == 0

def test_search_function_empty_kb_file():
    """Testa la funzione search con un file KB che contiene una lista vuota."""
    results = search("Qualsiasi Query", file_path=EMPTY_LIST_KB_PATH)
    assert len(results) == 0

# Per eseguire i test da riga di comando:
# Assicurati di essere nella directory root del progetto.
# Esegui: pytest
# Oppure: python -m pytest tests/test_search_engine.py
# (potrebbe essere necessario installare pytest: pip install pytest)
