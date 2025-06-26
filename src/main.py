import json
import os

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

def normalize_input(text: str) -> str:
    """
    Normalizza l'input dell'utente per facilitare la ricerca.
    Sostituisce gli spazi con underscore e converte in minuscolo.
    """
    return text.lower().replace(' ', '_')

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
        user_input = input("> ").strip()
        normalized_user_input = normalize_input(user_input)

        if user_input.lower() == 'esci':
            print("Arrivederci!")
            break

        if user_input.lower() == 'aiuto':
            print("Comandi disponibili:")
            print("  aiuto - Mostra questo messaggio di aiuto.")
            print("  esci  - Termina P.A.S.C.A.L.")
            print("Puoi anche farmi domande dirette, ad esempio 'chi ha dipinto la gioconda' o 'bop test frequenza'.")
            continue

        found_answer = False
        # Cerca l'input normalizzato nelle chiavi della base di conoscenza
        for category, questions in knowledge_base.items():
            if normalized_user_input in questions:
                print(questions[normalized_user_input])
                found_answer = True
                break
            # Tentativo di ricerca con chiavi parziali (più complesso, per ora semplice)
            # Ad esempio, se l'utente scrive "rivoluzione francese" e la chiave è "rivoluzione_francese_cause"
            # Questo potrebbe essere migliorato con tecniche NLP più avanzate in futuro.
            # Per ora, ci si aspetta una corrispondenza quasi esatta dopo la normalizzazione.

        if not found_answer:
            # Un semplice tentativo di matchare se l'input dell'utente è contenuto in una chiave più lunga
            # Questo è molto basilare e potrebbe dare falsi positivi o mancare corrispondenze volute.
            # Es. utente: "bop test", chiave: "bop_test_frequenza"
            possible_match = None
            for category, questions in knowledge_base.items():
                for key_kb, answer_kb in questions.items():
                    if normalized_user_input in key_kb: # Se l'input è una sottostringa di una chiave
                        possible_match = answer_kb # Troviamo la prima occorrenza
                        break
                if possible_match:
                    break

            if possible_match:
                print(possible_match)
                found_answer = True

        if not found_answer:
            print("Sto ancora imparando. Per ora, posso solo gestire 'esci', 'aiuto' o cercare alcune parole chiave esatte.")

if __name__ == "__main__":
    start_pascal_cli()
