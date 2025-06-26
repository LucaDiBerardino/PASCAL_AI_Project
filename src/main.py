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
    """
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'\s+', '_', text)
    text = text.strip('_')
    return text

def normalize_text_for_keyword_search(text: str) -> str:
    """
    Normalizza il testo per l'estrazione di parole chiave.
    """
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    return text

def decompose_question(original_user_input: str) -> list[str]:
    """
    Scompone l'input dell'utente in potenziali sotto-domande basate su congiunzioni.
    Opera sull'input originale per preservare la struttura per la ricerca successiva.
    """
    # Pattern per identificare congiunzioni e separatori comuni.
    # Cerca di essere non troppo aggressivo per non spezzare frasi che non dovrebbero essere spezzate.
    # Il lookbehind (?i) rende il match case-insensitive per le congiunzioni.
    # \b assicura che matchiamo parole intere per le congiunzioni.
    # Le parentesi catturano i delimitatori in modo che re.split() li mantenga,
    # ma per questo caso semplice, vogliamo splittare *attorno* ad essi.
    # Quindi non catturiamo i delimitatori, ma splittiamo la stringa in base ad essi.

    # Semplifichiamo: cerchiamo " e ", ", e ", " o " come separatori principali.
    # Per "cos'è X e cos'è Y", lo split su " e " potrebbe essere sufficiente se le parti rimanenti sono query valide.

    # Un approccio più semplice per iniziare: split su " e " e " o ".
    # Potremmo dover iterare e raffinare questo.
    # Usiamo lowercase per il matching delle congiunzioni.
    input_lower = original_user_input.lower()

    # Tentativo di split su " e ", " o ", ", e ", ", o "
    # Dobbiamo gestire gli spazi attorno alle congiunzioni.
    # re.split può essere complesso con i gruppi. Un approccio più diretto:

    potential_splits = re.split(r'\s+\b(e|o|e poi|e anche)\b\s+', original_user_input, flags=re.IGNORECASE)

    # Pulizia degli split: re.split può lasciare elementi vuoti o le congiunzioni stesse.
    sub_questions = []
    if len(potential_splits) > 1: # Se c'è stato almeno uno split
        current_sub_question = ""
        for part in potential_splits:
            if part.lower().strip() in ["e", "o", "e poi", "e anche"]:
                if current_sub_question.strip():
                    sub_questions.append(current_sub_question.strip())
                current_sub_question = "" # Reset per la prossima parte
            else:
                current_sub_question += " " + part # Aggiunge la parte di domanda
        if current_sub_question.strip(): # Aggiunge l'ultima parte
             sub_questions.append(current_sub_question.strip())

        # Filtra eventuali stringhe vuote risultanti da split consecutivi
        sub_questions = [sq for sq in sub_questions if sq]

    if not sub_questions: # Se nessuno split è avvenuto o ha prodotto risultati validi
        return [original_user_input.strip()]

    # Ulteriore tentativo di raffinare: se una sotto-domanda è molto corta o sembra una congiunzione residua,
    # potrebbe essere meglio unirla alla precedente o successiva. Per ora, manteniamo semplice.
    # Esempio: "cos'è AI e machine learning" -> ["cos'è AI", "machine learning"]
    # "AI, machine learning e deep learning" -> ["AI, machine learning", "deep learning"] (se split solo su 'e')

    # Per ora, questo split è basilare. Può essere migliorato significativamente.
    # Ad esempio, "cos'è l'AI e il machine learning" -> split su " e " -> ["cos'è l'AI", "il machine learning"]
    # La seconda parte "il machine learning" potrebbe non essere una query ideale da sola.
    # Una decomposizione semantica sarebbe molto più robusta.

    # Se dopo lo split otteniamo solo una domanda, restituiamo l'originale
    if len(sub_questions) == 1 and sub_questions[0].lower() == original_user_input.lower().strip():
        return [original_user_input.strip()]

    # Se lo split ha prodotto qualcosa di diverso dall'originale, lo usiamo
    if sub_questions and not (len(sub_questions) == 1 and sub_questions[0] == original_user_input.strip()):
         # Rimuoviamo eventuali frasi troppo corte che potrebbero essere solo articoli o congiunzioni residue
        return [sq for sq in sub_questions if len(sq.split()) > 1] if any(len(sq.split()) > 1 for sq in sub_questions) else [original_user_input.strip()]


    return [original_user_input.strip()]


def find_answer_for_query(query_text: str, knowledge_base: dict) -> str | None:
    """
    Trova una risposta per una singola query usando le strategie definite.
    """
    found_answer_text = None

    # Strategia 1: Corrispondenza Esatta Normalizzata
    normalized_for_exact = normalize_input_for_exact_match(query_text)
    for category_content in knowledge_base.values():
        if normalized_for_exact in category_content:
            found_answer_text = category_content[normalized_for_exact]
            return found_answer_text # Trovato, esci subito

    # Strategia 2: Contenimento dell'Input Normalizzato in una Chiave KB
    if not found_answer_text:
        best_match_key_strat2 = None
        min_len_key_strat2 = float('inf')
        for category_content in knowledge_base.values():
            for kb_key, kb_answer in category_content.items():
                if normalized_for_exact in kb_key:
                    if len(kb_key) < min_len_key_strat2:
                        min_len_key_strat2 = len(kb_key)
                        best_match_key_strat2 = kb_answer
        if best_match_key_strat2:
            return best_match_key_strat2 # Trovato, esci

    # Strategia 3: Ricerca basata su Parole Chiave
    if not found_answer_text:
        user_keywords_text = normalize_text_for_keyword_search(query_text)
        if not user_keywords_text.strip(): # Se non ci sono parole chiave dopo la normalizzazione
            return None

        user_keywords = set(user_keywords_text.split())
        if not user_keywords:
            return None

        best_match_score = 0
        best_answer_strat3 = None
        for category_content in knowledge_base.values():
            for kb_key, kb_answer in category_content.items():
                kb_key_keywords = set(kb_key.split('_'))
                common_keywords = user_keywords.intersection(kb_key_keywords)
                score = len(common_keywords)

                # Bonus se tutte le parole chiave dell'utente sono presenti nella chiave KB
                # (o se le parole chiave della KB sono un sottoinsieme di quelle dell'utente, per query più specifiche)
                if common_keywords == user_keywords and score > 0:
                    score += len(user_keywords) # Bonus per specificità completa della query utente
                elif common_keywords == kb_key_keywords and score > 0:
                     score += len(kb_key_keywords) # Bonus se la chiave KB è completamente coperta

                if score > best_match_score:
                    best_match_score = score
                    best_answer_strat3 = kb_answer

        if best_match_score > 0: # Soglia minima
            return best_answer_strat3 # Trovato

    return None # Nessuna risposta trovata con nessuna strategia


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

        if not user_input_original:
            continue

        if user_input_original.lower() == 'esci':
            print("Arrivederci!")
            break

        if user_input_original.lower() == 'aiuto':
            print("Comandi disponibili:")
            print("  aiuto - Mostra questo messaggio di aiuto.")
            print("  esci  - Termina P.A.S.C.A.L.")
            print("Puoi anche farmi domande dirette, ad esempio 'chi ha dipinto la gioconda' o 'cause rivoluzione francese e conseguenze'.")
            continue

        sub_question_strings = decompose_question(user_input_original)

        collected_answers = []
        for sub_query_string in sub_question_strings:
            if not sub_query_string.strip(): # Salta sotto-query vuote
                continue
            answer = find_answer_for_query(sub_query_string, knowledge_base)
            if answer and answer not in collected_answers:
                collected_answers.append(answer)

        if collected_answers:
            print("\n---\n".join(collected_answers))
        else:
            print("Sto ancora imparando. Per ora, posso solo gestire 'esci', 'aiuto' o cercare alcune parole chiave nella mia conoscenza. Prova a riformulare o a dividere la tua domanda.")

if __name__ == "__main__":
    start_pascal_cli()
