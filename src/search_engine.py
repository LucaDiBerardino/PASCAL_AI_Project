import json
import os

# Definisce il percorso predefinito relativo alla posizione di questo script
DEFAULT_KB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'knowledge_base.json')

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
       not isinstance(knowledge_base_entries, list): # Assicura che KB sia una lista
        return []

    matched_entries = []
    query_lower = query.lower()

    for entry in knowledge_base_entries:
        # Controlla la domanda principale
        domanda = entry.get("domanda", "")
        if isinstance(domanda, str) and domanda.lower() == query_lower:
            matched_entries.append(entry)
            continue  # Trovato, passa alla prossima entry per evitare duplicati dalla stessa entry

        # Controlla le varianti della domanda
        varianti = entry.get("varianti_domanda", [])
        if isinstance(varianti, list):
            for variante in varianti:
                if isinstance(variante, str) and variante.lower() == query_lower:
                    matched_entries.append(entry)
                    break # Trovato in varianti, passa alla prossima entry

    return matched_entries

def search(query: str, file_path: str = DEFAULT_KB_PATH) -> list[dict]:
    """
    Funzione di alto livello per eseguire una ricerca esatta nella knowledge base.

    Carica la knowledge base dal percorso specificato (o predefinito) e poi
    esegue una ricerca esatta.

    Args:
        query (str): La stringa di ricerca.
        file_path (str, optional): Il percorso del file JSON della knowledge base.
                                    Default a 'data/knowledge_base.json'.

    Returns:
        list[dict]: Una lista di voci complete (dizionari) che corrispondono
                    esattamente alla query. Restituisce una lista vuota se
                    non viene trovata alcuna corrispondenza o in caso di errore
                    nel caricamento della knowledge base.
    """
    knowledge_base_entries = load_knowledge_base(file_path)
    if not knowledge_base_entries: # Se il caricamento fallisce o KB è vuota
        return []
    return search_exact(query, knowledge_base_entries)

if __name__ == '__main__':
    # Esempio di utilizzo (per test rapido)
    kb_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'knowledge_base.json') # Assicura percorso corretto

    # Test load_knowledge_base
    print("--- Test load_knowledge_base ---")
    entries = load_knowledge_base(kb_path)
    if entries:
        print(f"Caricate {len(entries)} voci dalla knowledge base.")
        # print("Prima entry:", entries[0])
    else:
        print("Knowledge base non caricata o vuota.")

    print("\n--- Test search_exact (con KB caricata a parte) ---")
    if entries:
        test_query_1 = "Cos'è l'energia?"
        results_1 = search_exact(test_query_1, entries)
        print(f"Risultati per '{test_query_1}': {len(results_1)} trovati.")
        if results_1:
            for r in results_1:
                print(f"  ID: {r.get('id')}, Domanda: {r.get('domanda')}")

        test_query_2 = "Definizione di energia di movimento" # Variante
        results_2 = search_exact(test_query_2, entries)
        print(f"Risultati per '{test_query_2}': {len(results_2)} trovati.")
        if results_2:
             for r in results_2:
                print(f"  ID: {r.get('id')}, Domanda: {r.get('domanda')}")

        test_query_3 = "Questa query non esiste"
        results_3 = search_exact(test_query_3, entries)
        print(f"Risultati per '{test_query_3}': {len(results_3)} trovati.")
    else:
        print("Skipping search_exact tests, KB non caricata.")

    print("\n--- Test search (funzione di alto livello) ---")
    test_query_4 = "Cos'è Python?"
    results_4 = search(test_query_4, file_path=kb_path)
    print(f"Risultati per '{test_query_4}' (tramite search()): {len(results_4)} trovati.")
    if results_4:
        for r in results_4:
            print(f"  ID: {r.get('id')}, Domanda: {r.get('domanda')}")

    results_5 = search("domanda inesistente", file_path=kb_path)
    print(f"Risultati per 'domanda inesistente' (tramite search()): {len(results_5)} trovati.")

    # Test con file non esistente
    print("\n--- Test search con file KB non esistente ---")
    results_non_existent_kb = search("qualsiasi cosa", file_path="path/inesistente/kb.json")
    print(f"Risultati con KB non esistente: {len(results_non_existent_kb)} trovati.")

    # Test con JSON malformato (crea un file temporaneo malformato)
    malformed_json_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'malformed_kb.json')
    with open(malformed_json_path, 'w') as f:
        f.write("{'invalid_json': ") # JSON non valido

    print("\n--- Test search con JSON malformato ---")
    results_malformed_kb = search("qualsiasi cosa", file_path=malformed_json_path)
    print(f"Risultati con KB malformata: {len(results_malformed_kb)} trovati.")
    os.remove(malformed_json_path) # Pulisci file temporaneo

    print("\n--- Test search_exact con query minuscola e KB con maiuscola ---")
    if entries:
        test_query_case = "cos'è l'energia?"
        results_case = search_exact(test_query_case, entries)
        print(f"Risultati per '{test_query_case}': {len(results_case)} trovati.")
        if results_case:
            for r in results_case:
                print(f"  ID: {r.get('id')}, Domanda: {r.get('domanda')}")
    else:
        print("Skipping case test, KB non caricata.")

    # Test con KB che è solo una lista (non un dict con "entries")
    list_kb_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'list_kb.json')
    sample_list_kb = [{"id":100, "domanda":"Test domanda lista", "varianti_domanda":["variante lista"], "risposta":"Risposta lista"}]
    with open(list_kb_path, 'w', encoding='utf-8') as f:
        json.dump(sample_list_kb, f)
    print("\n--- Test search con KB come lista diretta ---")
    results_list_kb = search("Test domanda lista", file_path=list_kb_path)
    print(f"Risultati per 'Test domanda lista' (KB come lista): {len(results_list_kb)} trovati.")
    if results_list_kb:
         print(f"  ID: {results_list_kb[0].get('id')}, Domanda: {results_list_kb[0].get('domanda')}")
    os.remove(list_kb_path)

    # Test con KB che ha struttura errata (non dict con "entries" né lista)
    wrong_structure_kb_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'wrong_structure_kb.json')
    wrong_structure_kb = {"data": "valore"}
    with open(wrong_structure_kb_path, 'w', encoding='utf-8') as f:
        json.dump(wrong_structure_kb, f)
    print("\n--- Test search con KB con struttura errata ---")
    results_wrong_kb = search("qualsiasi", file_path=wrong_structure_kb_path)
    print(f"Risultati per 'qualsiasi' (KB struttura errata): {len(results_wrong_kb)} trovati.")
    os.remove(wrong_structure_kb_path)

    print("\nFine dei test rapidi.")
