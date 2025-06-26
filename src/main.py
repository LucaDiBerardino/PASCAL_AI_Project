import json
import os
import re

KNOWLEDGE_BASE_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'knowledge_base.json')

def load_knowledge_base(filepath: str) -> dict:
    """
    Carica la base di conoscenza da un file JSON.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            knowledge_base = json.load(f)
        return knowledge_base
    except FileNotFoundError:
        print(f"Errore: Il file della base di conoscenza non è stato trovato in {filepath}")
        return {}
    except json.JSONDecodeError:
        print(f"Errore: Il file della base di conoscenza in {filepath} non è un JSON valido.")
        return {}

def normalize_input_for_exact_match(text: str) -> str:
    """
    Normalizza l'input dell'utente per la ricerca di corrispondenza esatta.
    Converte in minuscolo, rimuove punteggiatura base, sostituisce spazi con underscore.
    """
    text = text.lower()
    # Rimuove la punteggiatura comune ma cerca di preservare parole chiave
    text = re.sub(r'[^\w\s-]', '', text) # Mantiene alphanumeric, spazi, underscore, trattini
    text = re.sub(r'\s+', '_', text) # Sostituisce uno o più spazi con un singolo underscore
    text = text.strip('_') # Rimuove underscore iniziali/finali
    return text

def normalize_text_for_keyword_search(text: str) -> str:
    """
    Normalizza il testo per l'estrazione di parole chiave.
    Converte in minuscolo, rimuove tutta la punteggiatura, poi splitta per spazi.
    """
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text) # Rimuove tutta la punteggiatura
    return text


def start_pascal_cli():
    """
    Avvia l'interfaccia a riga di comando (CLI) per P.A.S.C.A.L.
    """
    knowledge_base = load_knowledge_base(KNOWLEDGE_BASE_PATH)

    if not knowledge_base:
        print("Avvio di P.A.S.C.A.L. non riuscito a causa di problemi con la base di conoscenza.")
        return

    print("Ciao! Sono P.A.S.C.A.L. il tuo assistente AI. Digita 'aiuto' per le mie capacità o 'esci' per terminare.")

    while True:
        user_input_original = input("> ").strip()

        if not user_input_original: # Ignora input vuoto
            continue

        if user_input_original.lower() == 'esci':
            print("Arrivederci!")
            break

        if user_input_original.lower() == 'aiuto':
            print("Comandi disponibili:")
            print("  aiuto - Mostra questo messaggio di aiuto.")
            print("  esci  - Termina P.A.S.C.A.L.")
            print("Puoi anche farmi domande dirette, ad esempio 'chi ha dipinto la gioconda' o 'cause rivoluzione francese'.")
            continue

        found_answer_text = None

        # --- Strategia 1: Corrispondenza Esatta Normalizzata ---
        normalized_for_exact = normalize_input_for_exact_match(user_input_original)
        for category_content in knowledge_base.values():
            if normalized_for_exact in category_content:
                found_answer_text = category_content[normalized_for_exact]
                break

        if found_answer_text:
            print(found_answer_text)
            continue

        # --- Strategia 2: Contenimento dell'Input Normalizzato in una Chiave KB ---
        # (Es. input "bop test", chiave KB "bop_test_frequenza")
        # Questa è una versione leggermente modificata della precedente logica di fallback
        if not found_answer_text:
            best_match_key_strat2 = None
            # Cerchiamo la chiave più corta che contiene l'input normalizzato per evitare match troppo generici
            min_len_key_strat2 = float('inf')

            for category_content in knowledge_base.values():
                for kb_key, kb_answer in category_content.items():
                    if normalized_for_exact in kb_key:
                        if len(kb_key) < min_len_key_strat2:
                            min_len_key_strat2 = len(kb_key)
                            best_match_key_strat2 = kb_answer

            if best_match_key_strat2:
                found_answer_text = best_match_key_strat2

        if found_answer_text:
            print(found_answer_text)
            continue

        # --- Strategia 3: Ricerca basata su Parole Chiave ---
        if not found_answer_text:
            user_keywords = set(normalize_text_for_keyword_search(user_input_original).split())

            if not user_keywords: # Se dopo la normalizzazione non ci sono parole chiave
                print("Sto ancora imparando. Per ora, posso solo gestire 'esci', 'aiuto' o cercare alcune parole chiave nella mia conoscenza.")
                continue

            best_match_score = 0
            best_answer = None

            for category_content in knowledge_base.values():
                for kb_key, kb_answer in category_content.items():
                    kb_key_keywords = set(kb_key.split('_')) # Le chiavi KB sono già normalizzate

                    common_keywords = user_keywords.intersection(kb_key_keywords)

                    # Semplice score: numero di parole chiave in comune.
                    # Si potrebbe pesare di più se tutte le parole utente sono nella chiave,
                    # o usare metriche come Jaccard index.
                    score = len(common_keywords)

                    # Diamo una priorità se tutte le parole chiave dell'utente sono presenti nella chiave KB
                    if common_keywords == user_keywords and score > 0 : # Tutte le parole utente sono nella chiave KB
                        score += len(user_keywords) # Bonus per specificità

                    if score > best_match_score:
                        best_match_score = score
                        best_answer = kb_answer
                    # Se lo score è uguale, preferiamo una risposta più corta (potrebbe essere più specifica)
                    # o una chiave KB più corta. Per ora, prendiamo la prima che massimizza lo score.

            # Definiamo una soglia minima per considerare una corrispondenza valida
            # es. almeno 1 parola chiave in comune e uno score > 0
            if best_match_score > 0: # Soglia minima (almeno una parola in comune)
                found_answer_text = best_answer

        if found_answer_text:
            print(found_answer_text)
        else:
            print("Sto ancora imparando. Per ora, posso solo gestire 'esci', 'aiuto' o cercare alcune parole chiave nella mia conoscenza.")

if __name__ == "__main__":
    start_pascal_cli()
