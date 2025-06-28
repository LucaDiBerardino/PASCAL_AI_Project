import json
import os
from rapidfuzz import fuzz # Import per il fuzzy matching

# Definisce il percorso predefinito relativo alla posizione di questo script
DEFAULT_KB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'knowledge_base.json')

def _normalize_text_for_search(text: str) -> str:
    """
    Helper function to normalize text for searching (lowercase).
    Potrebbe essere espansa per rimuovere punteggiatura o altro se necessario.
    """
    if not isinstance(text, str):
        return ""
    return text.lower()

def calculate_confidence_score(query: str, entry: dict, is_exact_match: bool = False) -> float:
    """
    Calcola il punteggio di confidenza per una data query rispetto a una voce della knowledge base.

    Se is_exact_match è True, indica che la query ha già trovato una corrispondenza esatta
    con questa voce, quindi il punteggio di confidenza è massimo (100).

    Altrimenti, il punteggio viene calcolato usando la similarità fuzzy (rapidfuzz.fuzz.WRatio)
    tra la query e il miglior testo corrispondente trovato nella voce (tra "domanda" e
    le "varianti_domanda").

    Args:
        query (str): La stringa di ricerca.
        entry (dict): La voce della knowledge base (un dizionario) contro cui calcolare
                      il punteggio. Ci si aspetta che contenga chiavi come "domanda"
                      e "varianti_domanda".
        is_exact_match (bool, optional): Se True, la funzione restituisce 100.
                                         Default a False.

    Returns:
        float: Il punteggio di confidenza (0-100). Restituisce 0 se la query o l'entry
               non sono valide per il calcolo fuzzy o se non ci sono campi testuali
               validi nell'entry con cui confrontare.
    """
    if is_exact_match:
        return 100.0

    if not query or not isinstance(query, str) or \
       not entry or not isinstance(entry, dict):
        return 0.0

    normalized_query = _normalize_text_for_search(query)
    if not normalized_query:
        return 0.0

    max_score = 0.0

    # Controlla la domanda principale
    domanda_text = entry.get("domanda", "")
    normalized_domanda = _normalize_text_for_search(domanda_text)
    if normalized_domanda:
        score_domanda = fuzz.WRatio(normalized_query, normalized_domanda)
        if score_domanda > max_score:
            max_score = score_domanda

    # Controlla le varianti della domanda
    varianti = entry.get("varianti_domanda", [])
    if isinstance(varianti, list):
        for variante_text in varianti:
            normalized_variante = _normalize_text_for_search(variante_text)
            if normalized_variante:
                score_variante = fuzz.WRatio(normalized_query, normalized_variante)
                if score_variante > max_score:
                    max_score = score_variante

    return max_score

def load_knowledge_base(file_path: str = DEFAULT_KB_PATH) -> list[dict]:
    """
    Carica la knowledge base da un file JSON.

    Args:
        file_path (str): Il percorso del file JSON della knowledge base.
                         Default a 'data/knowledge_base.json' relativo alla root del progetto.

    Returns:
        list[dict]: Una lista di dizionari, dove ogni dizionario rappresenta una voce
                    della knowledge base. Restituisce una lista vuota se il file non viene
                    trovato, non è un JSON valido, o non ha la struttura attesa.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict) and "entries" in data and isinstance(data["entries"], list):
                return data["entries"]
            elif isinstance(data, list): # Supporta anche il caso in cui il JSON sia direttamente una lista di entries
                return data
            else:
                print(f"Errore: Il file della knowledge base in {file_path} non ha la struttura attesa (oggetto con chiave 'entries' o lista di entries).")
                return []
    except FileNotFoundError:
        print(f"Errore: File della knowledge base non trovato in {file_path}")
        return []
    except json.JSONDecodeError:
        print(f"Errore: Il file della knowledge base in {file_path} non è un JSON valido.")
        return []

def search_exact(query: str, knowledge_base_entries: list[dict]) -> list[dict]:
    """
    Cerca una corrispondenza esatta (case-insensitive) della query nella knowledge base.

    La ricerca viene effettuata nel campo "domanda" e in ogni stringa
    all'interno della lista "varianti_domanda" di ciascuna voce.

    Args:
        query (str): La stringa di ricerca.
        knowledge_base_entries (list[dict]): La knowledge base caricata, rappresentata come
                                              una lista di dizionari (voci).

    Returns:
        list[dict]: Una lista di voci complete (dizionari) che corrispondono
                    esattamente alla query. Restituisce una lista vuota se
                    non viene trovata alcuna corrispondenza o se l'input non è valido.
    """
    if not query or not isinstance(query, str) or \
       not isinstance(knowledge_base_entries, list):
        return []

    matched_entries = []
    normalized_query = _normalize_text_for_search(query)

    if not normalized_query: # Se la query normalizzata è vuota
        return []

    for entry in knowledge_base_entries:
        # Controlla la domanda principale
        domanda_text = entry.get("domanda", "")
        normalized_domanda = _normalize_text_for_search(domanda_text)

        if normalized_domanda == normalized_query:
            if entry not in matched_entries:
                matched_entries.append(entry)

        if entry not in matched_entries:
            varianti = entry.get("varianti_domanda", [])
            if isinstance(varianti, list):
                for variante_text in varianti:
                    normalized_variante = _normalize_text_for_search(variante_text)
                    if normalized_variante == normalized_query:
                        if entry not in matched_entries:
                            matched_entries.append(entry)
                        break

    return matched_entries

def search_fuzzy(query: str, knowledge_base_entries: list[dict], threshold: int = 80) -> list[tuple[dict, float]]:
    """
    Cerca corrispondenze fuzzy (simili) della query nella knowledge base.

    Args:
        query (str): La stringa di ricerca.
        knowledge_base_entries (list[dict]): La knowledge base (lista di dizionari/voci).
        threshold (int, optional): La soglia minima di similarità (0-100)
                                   per considerare una corrispondenza. Default a 80.

    Returns:
        list[tuple[dict, float]]: Una lista di tuple, dove ogni tupla contiene
                                  la voce corrispondente e il punteggio di similarità massimo
                                  trovato per quella voce.
    """
    if not query or not isinstance(query, str) or \
       not isinstance(knowledge_base_entries, list) or not knowledge_base_entries:
        return []

    normalized_query = _normalize_text_for_search(query)
    if not normalized_query:
        return []
    
    results_with_scores = []
    for entry in knowledge_base_entries:
        max_score_for_this_entry = 0

        domanda_text = entry.get("domanda", "")
        normalized_domanda = _normalize_text_for_search(domanda_text)
        if normalized_domanda:
            score = fuzz.WRatio(normalized_query, normalized_domanda)
            if score > max_score_for_this_entry:
                max_score_for_this_entry = score

        varianti = entry.get("varianti_domanda", [])
        if isinstance(varianti, list):
            for variante_text in varianti:
                normalized_variante = _normalize_text_for_search(variante_text)
                if normalized_variante:
                    score = fuzz.WRatio(normalized_query, normalized_variante)
                    if score > max_score_for_this_entry:
                        max_score_for_this_entry = score

        if max_score_for_this_entry >= threshold:
            results_with_scores.append((entry, max_score_for_this_entry))

    return results_with_scores

def search(query: str, file_path: str = DEFAULT_KB_PATH, fuzzy_threshold: int = 80, limit: int | None = None) -> list[tuple[dict, float]]:
    """
    Funzione di alto livello per eseguire una ricerca nella knowledge base.
    Combina risultati da ricerca esatta e fuzzy, calcolando un punteggio di confidenza
    per ciascun risultato usando calculate_confidence_score.
    Gestisce i duplicati dando priorità ai match esatti.
    Ordina i risultati per punteggio (decrescente) e applica un limite opzionale.

    Args:
        query (str): La stringa di ricerca.
        file_path (str, optional): Il percorso del file JSON della knowledge base.
                                    Default a 'data/knowledge_base.json'.
        fuzzy_threshold (int, optional): La soglia minima di similarità (0-100)
                                         per considerare una corrispondenza fuzzy.
                                         Default a 80.
        limit (int | None, optional): Il numero massimo di risultati da restituire.
                                      Se None o un intero non valido (es. negativo),
                                      vengono restituiti tutti i risultati.
                                      Se 0, restituisce una lista vuota. Default a None.
    Returns:
        list[tuple[dict, float]]: Una lista di tuple (entry, score) ordinate ed eventualmente limitate.
                                  Restituisce una lista vuota se non ci sono corrispondenze
                                  o in caso di errore nel caricamento della KB.
    """
    knowledge_base_entries = load_knowledge_base(file_path)
    if not knowledge_base_entries:
        return []

    results_with_id_map = {}
    results_without_id_list = []

    exact_match_entries = search_exact(query, knowledge_base_entries)
    for entry in exact_match_entries:
        score = calculate_confidence_score(query, entry, is_exact_match=True)
        entry_id = entry.get("id")
        if entry_id is not None:
            results_with_id_map[entry_id] = (entry, score)
        else:
            results_without_id_list.append((entry, score))

    fuzzy_candidates_with_internal_scores = search_fuzzy(query, knowledge_base_entries, threshold=fuzzy_threshold)

    for entry, _ in fuzzy_candidates_with_internal_scores:
        entry_id = entry.get("id")
        if entry_id is not None:
            if entry_id in results_with_id_map:
                continue
            score = calculate_confidence_score(query, entry, is_exact_match=False)
            if score >= fuzzy_threshold:
                results_with_id_map[entry_id] = (entry, score)
        else:
            score = calculate_confidence_score(query, entry, is_exact_match=False)
            if score >= fuzzy_threshold:
                is_duplicate_exact_no_id = False
                for ex_entry_no_id, _ in results_without_id_list:
                    if ex_entry_no_id is entry:
                        is_duplicate_exact_no_id = True
                        break
                if not is_duplicate_exact_no_id:
                    results_without_id_list.append((entry, score))

    final_results = list(results_with_id_map.values()) + results_without_id_list
    final_results.sort(key=lambda x: x[1], reverse=True)

    if isinstance(limit, int):
        if limit == 0:
            return []
        if limit > 0:
            return final_results[:limit]

    return final_results
