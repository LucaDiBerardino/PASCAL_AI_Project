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
            # Non usare 'continue' qui, perché una entry potrebbe essere matchata esattamente
            # dalla domanda, e un'altra entry potrebbe essere matchata esattamente da una variante.
            # Il controllo 'if entry not in matched_entries' previene che la STESSA entry
            # venga aggiunta più volte se la query matcha sia la sua domanda che una sua variante.

        # Controlla le varianti della domanda solo se non già matchata tramite la domanda principale
        # per questa specifica entry.
        if entry not in matched_entries:
            varianti = entry.get("varianti_domanda", [])
            if isinstance(varianti, list):
                for variante_text in varianti:
                    normalized_variante = _normalize_text_for_search(variante_text)
                    if normalized_variante == normalized_query:
                        if entry not in matched_entries: # Dovrebbe essere sempre vero qui se non ha matchato la domanda
                            matched_entries.append(entry)
                        break # Trovato un match esatto in varianti per QUESTA entry, inutile controllare altre varianti della stessa entry.

    return matched_entries

def search_fuzzy(query: str, knowledge_base_entries: list[dict], threshold: int = 80) -> list[tuple[dict, float]]:
    """
    Cerca corrispondenze fuzzy (simili) della query nella knowledge base.

    Utilizza rapidfuzz.fuzz.WRatio per calcolare la similarità tra la query e
    i campi "domanda" e "varianti_domanda" di ogni voce, tenendo conto
    delle differenze di lunghezza e ordine delle parole.

    Args:
        query (str): La stringa di ricerca.
        knowledge_base_entries (list[dict]): La knowledge base (lista di dizionari/voci).
        threshold (int, optional): La soglia minima di similarità (0-100)
                                   per considerare una corrispondenza. Default a 80.

    Returns:
        list[tuple[dict, float]]: Una lista di tuple, dove ogni tupla contiene
                                  la voce corrispondente e il punteggio di similarità massimo
                                  trovato per quella voce. Restituisce una lista vuota se
                                  non ci sono match sopra la soglia o se l'input non è valido.
    """
    if not query or not isinstance(query, str) or \
       not isinstance(knowledge_base_entries, list) or not knowledge_base_entries:
        return []

    normalized_query = _normalize_text_for_search(query)
    if not normalized_query:
        return []

    potential_matches = {} # Usiamo un dizionario per tenere traccia del miglior score per entry ID

    for entry in knowledge_base_entries:
        entry_id = entry.get("id", None) # Assumiamo che le entry abbiano un ID univoco
        if entry_id is None:
            # Se non c'è ID, non possiamo garantire l'unicità del miglior match per entry
            # Potremmo usare l'oggetto entry stesso come chiave, ma è meno pulito.
            # Per ora, saltiamo le entry senza ID per il fuzzy matching o le trattiamo individualmente.
            # Qui scegliamo di calcolare comunque, ma l'aggiornamento di potential_matches potrebbe non essere ottimale.
            # Un approccio migliore sarebbe generare un hash dell'entry o usare l'indice nella lista.
            # Per semplicità, qui usiamo l'ID se presente, altrimenti non aggiorniamo in modo intelligente.
            pass

        current_max_score_for_entry = 0

        # Controlla la domanda principale
        domanda_text = entry.get("domanda", "")
        normalized_domanda = _normalize_text_for_search(domanda_text)
        if normalized_domanda:
            score_domanda = fuzz.WRatio(normalized_query, normalized_domanda)
            if score_domanda > current_max_score_for_entry:
                current_max_score_for_entry = score_domanda

        # Controlla le varianti della domanda
        varianti = entry.get("varianti_domanda", [])
        if isinstance(varianti, list):
            for variante_text in varianti:
                normalized_variante = _normalize_text_for_search(variante_text)
                if normalized_variante:
                    score_variante = fuzz.WRatio(normalized_query, normalized_variante)
                    if score_variante > current_max_score_for_entry:
                        current_max_score_for_entry = score_variante

        if current_max_score_for_entry >= threshold:
            # Se l'entry ha un ID e abbiamo già un punteggio per esso, aggiorna solo se il nuovo è migliore
            # Questo previene che la stessa entry appaia più volte se diverse sue parti matchano sopra soglia.
            # Vogliamo solo il miglior match per entry.
            if entry_id is not None:
                if entry_id not in potential_matches or current_max_score_for_entry > potential_matches[entry_id][1]:
                    potential_matches[entry_id] = (entry, current_max_score_for_entry)
            else:
                # Entry senza ID: la aggiungiamo direttamente. Potrebbe portare a "duplicati logici" se non gestita attentamente.
                # Per questo scenario, aggiungeremo una tupla (entry, score) a una lista e poi la filtreremo.
                # Alternativa: non supportare entry senza ID in fuzzy search o generare un ID temporaneo.
                # Semplificazione: per ora, aggiungiamo direttamente se non usiamo ID come chiave.
                # Rivediamo: usiamo una lista e filtriamo dopo per mantenere le cose semplici se ID non è affidabile.
                # Cambio approccio: usiamo una lista di tuple (score, entry_object_itself) per evitare problemi con ID.
                # Questo significa che una entry potrebbe apparire più volte se diverse sue parti (domanda, variante1, variante2)
                # indipendentemente superano la soglia con score diversi. Il sort e il pick del top N gestirà questo.
                # NO, l'obiettivo è il *miglior score per entry*.
                # Quindi, il dizionario basato su ID (o un hash dell'entry) è più corretto.
                # Se l'ID non è presente o non affidabile, si può usare l'indice originale o l'oggetto stesso come chiave (se hashable).
                # Per ora, assumiamo che l'ID sia il modo per identificare unicamente un'entry.
                # Se l'ID è None, potremmo usare l'oggetto entry come chiave se è hashable,
                # ma i dizionari non sono hashable. Quindi, è meglio avere ID.
                # Se non c'è ID, potremmo non includerla o usare l'indice.
                # Per semplicità, se non c'è ID, la entry viene aggiunta con il suo score
                # e si affida al chiamante la gestione di eventuali "duplicati logici" se più parti matchano.
                # Riconsiderazione: Il modo più pulito è mantenere il dizionario potential_matches[entry_id]
                # e gestire le entry senza ID come un caso speciale o richiedere che tutte le entry abbiano un ID.
                # Per questa implementazione, se manca l'ID, usiamo l'oggetto entry stesso se è immutabile,
                # ma dato che è un dict, non lo è.
                # Soluzione: Iteriamo e teniamo traccia del miglior punteggio per *oggetto entry*.
                # Non usiamo ID per il dict, ma l'oggetto entry stesso se possibile, o un suo rappresentante.
                # Più semplice: creare una lista di (entry, score) e poi filtrare per avere solo il miglior score per entry unica.
                # Questo è computazionalmente più costoso.
                # L'approccio con dict[entry_id] è il migliore se gli ID sono affidabili.
                # Se non lo sono, si può usare un set di entry già processate per il punteggio più alto.

                # Approccio finale per search_fuzzy:
                # 1. Itera su tutte le entries.
                # 2. Per ogni entry, calcola il massimo punteggio fuzzy tra la query e (domanda, varianti).
                # 3. Se questo max_score_for_entry >= threshold, aggiungi (entry, max_score_for_entry) a una lista di risultati.
                # Non c'è bisogno di preoccuparsi di duplicati qui perché ogni entry viene processata una volta.
                # La logica precedente era troppo complessa.
                pass # La logica di aggiornamento di potential_matches è già fuori dal loop interno.

    # Ricostruisci la lista dai valori del dizionario (se si usa l'approccio con ID)
    # return list(potential_matches.values())
    # Se invece si costruisce una lista semplice e si vuole il miglior score per entry:
    # (Questo è implicito se calcoliamo max_score_for_entry e aggiungiamo solo una volta per entry)

    # Semplificazione della logica di `search_fuzzy` come descritto sopra:
    # L'obiettivo è restituire una lista di tuple (entry, punteggio_massimo_per_quella_entry)
    # solo se punteggio_massimo_per_quella_entry >= threshold.

    # Reset della logica per `search_fuzzy` per maggiore chiarezza e correttezza:
    results_with_scores = []
    processed_entry_ids = set() # Per evitare di processare/aggiungere la stessa entry più volte se gli ID non sono unici

    for entry in knowledge_base_entries:
        entry_id = entry.get("id") # Usiamo l'ID per tracciare le entry uniche

        # Se l'ID non è None e l'abbiamo già processato con un punteggio più alto, saltiamo.
        # Questo non è necessario se calcoliamo il max_score_for_entry e poi decidiamo.
        # La logica di avere un solo (entry, score) per entry è più semplice.

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
            # Per evitare di aggiungere la stessa entry più volte se gli ID sono duplicati o mancanti
            # e stiamo solo iterando, potremmo voler aggiungere solo l'entry con il suo miglior punteggio.
            # Se gli ID sono unici, questo non è un problema. Se non lo sono, potremmo avere duplicati.
            # Assumiamo che le entry siano oggetti distinti anche se gli ID potessero non esserlo.
            # L'approccio più semplice è aggiungere (entry, max_score_for_this_entry)
            results_with_scores.append((entry, max_score_for_this_entry))

    return results_with_scores


def search(query: str, file_path: str = DEFAULT_KB_PATH, fuzzy_threshold: int = 80) -> list[dict]:
    """
    Funzione di alto livello per eseguire una ricerca nella knowledge base.
    Esegue prima una ricerca esatta. Se non trova risultati, esegue una ricerca fuzzy.
    I risultati fuzzy vengono ordinati per punteggio di similarità (decrescente).

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
    if not knowledge_base_entries:
        return []

    exact_matches = search_exact(query, knowledge_base_entries)
    if exact_matches:
        # print(f"DEBUG: Trovati {len(exact_matches)} risultati esatti per '{query}'")
        return exact_matches

    # Se non ci sono match esatti, prova con il fuzzy search
    # print(f"DEBUG: Nessun risultato esatto per '{query}', avvio ricerca fuzzy...")
    fuzzy_matches_with_scores = search_fuzzy(query, knowledge_base_entries, threshold=fuzzy_threshold)

    if fuzzy_matches_with_scores:
        # Ordina i risultati fuzzy per punteggio, dal più alto al più basso
        fuzzy_matches_with_scores.sort(key=lambda x: x[1], reverse=True)

        # Estrai solo le entries (rimuovendo i punteggi)
        sorted_fuzzy_entries = [entry for entry, score in fuzzy_matches_with_scores]
        # print(f"DEBUG: Trovati {len(sorted_fuzzy_entries)} risultati fuzzy per '{query}' (soglia {fuzzy_threshold})")
        return sorted_fuzzy_entries

    # print(f"DEBUG: Nessun risultato fuzzy per '{query}' (soglia {fuzzy_threshold})")
    return []


if __name__ == '__main__':
    # Esempio di utilizzo aggiornato per testare anche fuzzy
    kb_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'knowledge_base.json')

    print("--- Test load_knowledge_base ---")
    entries = load_knowledge_base(kb_path)
    if entries:
        print(f"Caricate {len(entries)} voci dalla knowledge base.")
        # print("Prima entry:", entries[0])
    else:
        print("Knowledge base non caricata o vuota.")

    # Esempi di test per search_fuzzy e la nuova logica di search
    if entries:
        print("\n--- Test search_fuzzy ---")
        fuzzy_query = "cos'è l'energa?" # Leggero errore di battitura
        fuzzy_results_with_scores = search_fuzzy(fuzzy_query, entries, threshold=75)
        print(f"Risultati fuzzy per '{fuzzy_query}' (soglia 75): {len(fuzzy_results_with_scores)} trovati.")
        for entry, score in fuzzy_results_with_scores:
            print(f"  ID: {entry.get('id')}, Domanda: {entry.get('domanda')}, Score: {score:.2f}")

        print("\n--- Test search (con fallback a fuzzy) ---")
        # Caso 1: Match esatto
        exact_search_results = search("Cos'è Python?", file_path=kb_path)
        print(f"Risultati search per 'Cos'è Python?': {len(exact_search_results)} trovati (dovrebbe essere esatto)")
        if exact_search_results:
            print(f"  ID: {exact_search_results[0].get('id')}, Risposta: {exact_search_results[0].get('risposta')[:30]}...")

        # Caso 2: Match solo fuzzy
        fuzzy_search_results = search("cos'è l'energa?", file_path=kb_path, fuzzy_threshold=75)
        print(f"Risultati search per 'cos'è l'energa?': {len(fuzzy_search_results)} trovati (dovrebbe essere fuzzy ordinato)")
        for r in fuzzy_search_results:
            print(f"  ID: {r.get('id')}, Domanda: {r.get('domanda')}")

        # Caso 3: Nessun match
        no_match_results = search("domanda super casuale e inesistente xyz", file_path=kb_path, fuzzy_threshold=75)
        print(f"Risultati search per 'domanda super casuale e inesistente xyz': {len(no_match_results)} trovati.")

    # Test con file non esistente per la funzione search
    print("\n--- Test search con file KB non esistente (per search) ---")
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
