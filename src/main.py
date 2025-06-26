import json
import os
import re
import pandas as pd
from datetime import datetime, timedelta
import random
import math

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

    """
    Scompone l'input dell'utente in potenziali sotto-domande.
    Fase 1: Splitta per delimitatori di frase (.?!)
    Fase 2: Per ogni frase, splitta per congiunzioni (e, o, ecc.)
    """
    if not original_user_input:
        return []

    # Fase 1: Scomposizione per Delimitatori di Frase Forti
    # Usiamo re.findall per trovare tutte le sottostringhe che terminano con un delimitatore o la fine della stringa.
    # Questo approccio è generalmente più pulito di split e ricomposizione.
    sentences = re.findall(r'[^.?!]+(?:[.?!]|$)', original_user_input)
    if not sentences: # Fallback se findall non trova nulla (es. input senza delimitatori)
        sentences = [original_user_input]

    final_sub_questions = []

    # Fase 2: Scomposizione per Congiunzioni per ogni frase
    conjunction_pattern = r'\s+\b(e|o|oppure|e poi|e anche|ed anche|o anche)\b\s+'

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        # Applica lo split per congiunzioni alla frase corrente
        parts = re.split(conjunction_pattern, sentence, flags=re.IGNORECASE)

        current_sub_sentence = ""
        if len(parts) > 1:
            for part_idx, part_content in enumerate(parts):
                # Le congiunzioni stesse appaiono come elementi separati nello split se il pattern le cattura.
                # Il nostro pattern non le cattura esplicitamente nel gruppo principale, quindi dovremmo ottenere solo le parti di testo.
                # Tuttavia, re.split a volte si comporta in modo strano con i gruppi.
                # Assicuriamoci di non aggiungere le congiunzioni stesse come sotto-domande.
                is_conjunction = part_content.lower().strip() in ["e", "o", "oppure", "e poi", "e anche", "ed anche", "o anche"]

                if not is_conjunction and part_content.strip():
                    current_sub_sentence += part_content # Aggiunge la parte di testo
                    # Se la prossima parte è una congiunzione (o siamo alla fine), finalizziamo la current_sub_sentence
                    is_last_part = (part_idx == len(parts) - 1)
                    next_part_is_conjunction_or_end = True # Default a True se siamo all'ultimo pezzo
                    if not is_last_part and (part_idx + 1 < len(parts)):
                         next_part_is_conjunction_or_end = parts[part_idx+1].lower().strip() in ["e", "o", "oppure", "e poi", "e anche", "ed anche", "o anche"]

                    if current_sub_sentence.strip() and (is_last_part or next_part_is_conjunction_or_end) :
                        final_sub_questions.append(current_sub_sentence.strip())
                        current_sub_sentence = "" # Reset
                elif is_conjunction and current_sub_sentence.strip():
                    # Se incontriamo una congiunzione e avevamo qualcosa accumulato, lo salviamo.
                    final_sub_questions.append(current_sub_sentence.strip())
                    current_sub_sentence = "" # Reset
            if current_sub_sentence.strip(): # Aggiunge l'ultima parte se non è vuota
                final_sub_questions.append(current_sub_sentence.strip())
        else: # Nessuna congiunzione trovata nella frase
            final_sub_questions.append(sentence.strip())

    # Fase 3: Filtraggio Finale
    # Rimuovi stringhe vuote e quelle troppo corte (es. solo una parola, a meno che non sia voluta)
    # Per ora, il filtro di lunghezza > 1 parola è un euristica.
    filtered_questions = [
        q.strip() for q in final_sub_questions if q.strip() and len(q.strip().split()) > 1
    ]

    # Se il filtraggio aggressivo non lascia nulla, ma l'originale aveva contenuto,
    # restituisci le parti pre-filtraggio (solo strip e non vuote) o l'originale.
    if not filtered_questions and original_user_input.strip():
        # Fallback meno aggressivo: prendi tutte le parti non vuote post-congiunzioni
        less_filtered = [q.strip() for q in final_sub_questions if q.strip()]
        if less_filtered:
            return less_filtered
        return [original_user_input.strip()] # Ultimo fallback

    return filtered_questions if filtered_questions else [original_user_input.strip()]


# --- Funzioni per la gestione dinamica della Knowledge Base ---

def normalize_key_for_storage(text: str) -> str:
    """
    Normalizza una chiave prima di salvarla nella knowledge base.
    Simile a normalize_input_for_exact_match.
    """
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'\s+', '_', text)
    return text.strip('_')

def add_knowledge(category: str, key: str, value: str, filepath: str = KNOWLEDGE_BASE_PATH) -> bool:
    """
    Aggiunge una nuova voce alla base di conoscenza JSON e la salva.
    Normalizza la chiave prima di salvarla.
    """
    try:
        # Carica la KB esistente o crea un dizionario vuoto se non esiste/è vuota
        current_kb = {}
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                try:
                    current_kb = json.load(f)
                except json.JSONDecodeError:
                    print(f"Avviso: {filepath} contiene JSON non valido. Sarà sovrascritto se si aggiunge conoscenza.")
                    current_kb = {} # Inizia con una KB vuota se il file è corrotto

        normalized_key = normalize_key_for_storage(key)

        if category not in current_kb:
            current_kb[category] = {}

        current_kb[category][normalized_key] = value

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(current_kb, f, indent=4, ensure_ascii=False)
        return True
    except IOError as e:
        print(f"Errore di I/O durante l'aggiunta di conoscenza: {e}")
        return False
    except Exception as e:
        print(f"Errore imprevisto durante l'aggiunta di conoscenza: {e}")
        return False

def get_categories(knowledge_base: dict) -> list[str]:
    """
    Restituisce una lista di tutte le categorie presenti nella base di conoscenza.
    """
    if not knowledge_base:
        return []
    return list(knowledge_base.keys())

# --- Funzioni per la simulazione dei dati CCU ---

def simulate_ccu_data_acquisition(num_records: int) -> pd.DataFrame:
    """
    Genera un DataFrame di Pandas con dati CCU simulati.
    """
    data = []
    current_time = datetime.now()
    sensor_statuses = ['OK', 'WARNING', 'ALARM']

    for _ in range(num_records):
        # Timestamp casuale negli ultimi 5 minuti (300 secondi)
        timestamp = current_time - timedelta(seconds=random.randint(0, 300))

        record = {
            'timestamp': timestamp,
            'well_pressure_psi': round(random.uniform(5000.0, 10000.0), 2),
            'mud_flow_rate_gpm': round(random.uniform(800.0, 1200.0), 2),
            'bop_ram_position_mm': round(random.uniform(0.0, 250.0), 2),
            'sensor_status': random.choice(sensor_statuses),
            'temperature_celsius': round(random.uniform(50.0, 150.0), 2)
        }
        data.append(record)

    df = pd.DataFrame(data)
    # Assicura che i timestamp siano in ordine cronologico (anche se generati casualmente all'indietro)
    df = df.sort_values(by='timestamp').reset_index(drop=True)
    return df

def analyze_ccu_data(df: pd.DataFrame) -> dict:
    """
    Calcola statistiche descrittive di base per le colonne numeriche specificate del DataFrame.
    """
    numerical_cols = ['well_pressure_psi', 'mud_flow_rate_gpm', 'bop_ram_position_mm', 'temperature_celsius']
    analysis_results = {}

    for col in numerical_cols:
        if col in df.columns:
            # Calcola le statistiche richieste
            stats = df[col].agg(['mean', 'std', 'min', 'max']).to_dict()
            # Arrotonda i valori per una migliore leggibilità
            analysis_results[col] = {stat_name: round(stat_value, 2) if pd.notnull(stat_value) else None
                                     for stat_name, stat_value in stats.items()}
        else:
            analysis_results[col] = {"error": "Colonna non trovata nel DataFrame"}

    return analysis_results

def detect_simple_anomalies(df: pd.DataFrame) -> list[str]:
    """
    Rileva anomalie semplici nei dati CCU basate su soglie predefinite.
    """
    anomalies = []

    # Soglie (hardcoded per ora)
    WELL_PRESSURE_LOW = 5500.0
    WELL_PRESSURE_HIGH = 9500.0
    MUD_FLOW_LOW = 850.0
    MUD_FLOW_HIGH = 1150.0
    BOP_CLOSED = 0.0
    BOP_OPEN = 250.0
    # Usiamo una piccola tolleranza per i confronti in virgola mobile per BOP
    BOP_TOLERANCE = 0.01

    for row in df.itertuples(index=False): # index=False per non avere 'Index' come primo campo
        ts = row.timestamp.strftime('%Y-%m-%d %H:%M:%S') # Formatta il timestamp per leggibilità
        anomaly_record = None

        # Controllo well_pressure_psi
        if row.well_pressure_psi < WELL_PRESSURE_LOW:
            anomaly_record = {
                'message': f"[{ts}] Pressione Pozzo BASSA: {row.well_pressure_psi:.2f} PSI (Soglia < {WELL_PRESSURE_LOW:.2f} PSI)",
                'type': "pressione_pozzo_bassa"
            }
        elif row.well_pressure_psi > WELL_PRESSURE_HIGH:
            anomaly_record = {
                'message': f"[{ts}] Pressione Pozzo ALTA: {row.well_pressure_psi:.2f} PSI (Soglia > {WELL_PRESSURE_HIGH:.2f} PSI)",
                'type': "pressione_pozzo_alta"
            }
        if anomaly_record: anomalies.append(anomaly_record); anomaly_record = None # Aggiungi e resetta

        # Controllo mud_flow_rate_gpm
        if row.mud_flow_rate_gpm < MUD_FLOW_LOW:
            anomaly_record = {
                'message': f"[{ts}] Portata Fango BASSA: {row.mud_flow_rate_gpm:.2f} GPM (Soglia < {MUD_FLOW_LOW:.2f} GPM)",
                'type': "mud_flow_rate_bassa"
            }
        elif row.mud_flow_rate_gpm > MUD_FLOW_HIGH:
            anomaly_record = {
                'message': f"[{ts}] Portata Fango ALTA: {row.mud_flow_rate_gpm:.2f} GPM (Soglia > {MUD_FLOW_HIGH:.2f} GPM)",
                'type': "mud_flow_rate_alta"
            }
        if anomaly_record: anomalies.append(anomaly_record); anomaly_record = None

        # Controllo bop_ram_position_mm
        is_closed = math.isclose(row.bop_ram_position_mm, BOP_CLOSED, abs_tol=BOP_TOLERANCE)
        is_open = math.isclose(row.bop_ram_position_mm, BOP_OPEN, abs_tol=BOP_TOLERANCE)
        if not (is_closed or is_open):
            anomaly_record = {
                'message': f"[{ts}] Posizione RAM BOP anomala: {row.bop_ram_position_mm:.2f} mm (non è Chiuso né Aperto)",
                'type': "bop_posizione_anomala"
            }
        if anomaly_record: anomalies.append(anomaly_record); anomaly_record = None

        # Controllo sensor_status
        if row.sensor_status == 'WARNING':
            anomaly_record = {
                'message': f"[{ts}] Stato Sensore: WARNING (Parametro: {row.sensor_status} per una delle letture)",
                'type': "sensor_warning" # Chiave generica per warning
            }
        elif row.sensor_status == 'ALARM':
            anomaly_record = {
                'message': f"[{ts}] Stato Sensore: ALARM (Parametro: {row.sensor_status} per una delle letture)",
                'type': "sensor_alarm" # Chiave generica per alarm
            }
        if anomaly_record: anomalies.append(anomaly_record); anomaly_record = None

    return anomalies

def generate_anomaly_report(anomalies_details: list[dict], knowledge_base: dict) -> str:
    """
    Genera una stringa di report formattata per le anomalie rilevate,
    includendo suggerimenti dalla knowledge base.
    """
    if not anomalies_details:
        return "Report Anomalie: Nessuna anomalia significativa rilevata."

    report_parts = ["REPORT ANOMALIE RILEVATE:"]
    for detail in anomalies_details:
        report_parts.append(f"  - {detail['message']}")

    suggestions_found = []
    problem_solving_kb = knowledge_base.get("problem_solving_suggestions", {})

    # Raccogli i tipi unici di anomalie per evitare suggerimenti duplicati
    unique_anomaly_types = sorted(list(set(detail['type'] for detail in anomalies_details)))

    for anomaly_type in unique_anomaly_types:
        suggestion_key = f"{anomaly_type}_suggerimento"
        suggestion = problem_solving_kb.get(suggestion_key)
        if suggestion:
            # Formatta il tipo di anomalia per la visualizzazione
            display_anomaly_type = anomaly_type.replace('_', ' ').capitalize()
            suggestions_found.append(f"  - Riguardo '{display_anomaly_type}': {suggestion}")

    if suggestions_found:
        report_parts.append("\n\nSuggerimenti per il Problem Solving:")
        report_parts.extend(suggestions_found)

    report_parts.append("\n\nSi consiglia verifica approfondita dei parametri segnalati.")

    return "\n".join(report_parts)

def assess_sensor_health(df: pd.DataFrame) -> dict:
    """
    Valuta la salute generale dei sensori basandosi sulla colonna 'sensor_status'.
    """
    if df is None or df.empty or 'sensor_status' not in df.columns:
        return {
            'OK': 0, 'WARNING': 0, 'ALARM': 0,
            'percent_warning': 0.0, 'percent_alarm': 0.0,
            'overall_health': 'Indeterminato (dati non disponibili o colonna sensor_status mancante)'
        }

    counts = df['sensor_status'].value_counts()
    ok_count = counts.get('OK', 0)
    warning_count = counts.get('WARNING', 0)
    alarm_count = counts.get('ALARM', 0)

    total_records = len(df)
    if total_records == 0: # Dovrebbe essere già gestito da df.empty ma per sicurezza
        return {
            'OK': 0, 'WARNING': 0, 'ALARM': 0,
            'percent_warning': 0.0, 'percent_alarm': 0.0,
            'overall_health': 'Indeterminato (nessun record)'
        }

    percent_warning = round((warning_count / total_records) * 100, 2)
    percent_alarm = round((alarm_count / total_records) * 100, 2)

    # Soglie per la valutazione della salute (possono essere affinate)
    # Regola più stringente: qualsiasi allarme è critico.
    ALARM_IS_CRITICAL = True
    WARNING_ATTENTION_THRESHOLD_PERCENT = 20.0
    # Se gli allarmi non sono considerati automaticamente critici, si potrebbe usare una soglia %
    # ALARM_CRITICAL_THRESHOLD_PERCENT = 5.0

    overall_health = 'Stabile'
    if ALARM_IS_CRITICAL and alarm_count > 0:
        overall_health = 'Critico'
    # elif percent_alarm >= ALARM_CRITICAL_THRESHOLD_PERCENT: # Alternativa se non si vuole che un singolo allarme sia critico
    #     overall_health = 'Critico'
    elif percent_warning >= WARNING_ATTENTION_THRESHOLD_PERCENT:
        overall_health = 'Attenzione'

    return {
        'OK': ok_count,
        'WARNING': warning_count,
        'ALARM': alarm_count,
        'percent_warning': percent_warning,
        'percent_alarm': percent_alarm,
        'overall_health': overall_health
    }

# --- Funzione principale di ricerca ---

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
            print("  aggiungi conoscenza - Permette di inserire nuove informazioni nella base di conoscenza.")
            print("  simula dati ccu - Simula l'acquisizione di dati dalla Central Control Unit.")
            print("Puoi anche farmi domande dirette, ad esempio 'chi ha dipinto la gioconda' o 'cause rivoluzione francese e conseguenze'.")
            continue

        # Gestione comandi specifici prima della scomposizione/ricerca KB
        user_input_lower = user_input_original.lower()

        if user_input_lower == 'aggiungi conoscenza':
            print("\n--- Aggiunta Nuova Conoscenza ---")
            if not knowledge_base:
                print("Attenzione: la base di conoscenza sembra essere vuota o non caricata.")

            print(f"Categorie esistenti: {get_categories(knowledge_base)}")
            category_input = input("Inserisci la categoria (es. 'storia', 'scienza', 'nuova_categoria'): ").strip()
            if not category_input:
                print("Categoria non valida. Annullamento.")
                continue

            key_input = input("Inserisci la domanda o la chiave (es. 'inventore lampadina'): ").strip()
            if not key_input:
                print("Chiave/domanda non valida. Annullamento.")
                continue

            value_input = input("Inserisci la risposta o il valore: ").strip()
            if not value_input:
                print("Valore/risposta non valido. Annullamento.")
                continue

            # La normalizzazione della chiave avviene dentro add_knowledge
            if add_knowledge(category_input, key_input, value_input):
                print("Conoscenza aggiunta con successo!")
                # Ricarica la KB per rendere disponibili le modifiche immediatamente
                knowledge_base = load_knowledge_base(KNOWLEDGE_BASE_PATH)
                if not knowledge_base: # Controllo post-ricarica
                     print("Attenzione: problemi durante il ricaricamento della base di conoscenza aggiornata.")
            else:
                print("Errore durante l'aggiunta della conoscenza.")
            print("-----------------------------------\n")
            continue

        if user_input_lower == 'simula dati ccu':
            print("\n--- Simulazione Dati CCU ---")
            try:
                df_ccu = simulate_ccu_data_acquisition(num_records=10)
                print("Dati CCU simulati e acquisiti con successo!")
                print("\nPrime 5 righe dei dati CCU simulati:")
                print(df_ccu.head().to_string())

                # Analisi dei dati CCU
                analysis = analyze_ccu_data(df_ccu)
                print("\nAnalisi di base dei dati CCU:")
                for column_name, stats_dict in analysis.items():
                    print(f"\nStatistiche per {column_name}:")
                    if "error" in stats_dict:
                        print(f"  - Errore: {stats_dict['error']}")
                    else:
                        for stat_name, stat_value in stats_dict.items():
                            # Gestisce il caso in cui stat_value potrebbe essere None (es. std di un singolo valore)
                            value_str = f"{stat_value:.2f}" if stat_value is not None else "N/A"
                            print(f"  - {stat_name.capitalize()}: {value_str}")
            except Exception as e:
                print(f"Errore durante la simulazione o analisi dei dati CCU: {e}")

            # Rilevamento anomalie e generazione report
            if 'df_ccu' in locals() and df_ccu is not None: # Assicurati che df_ccu esista
                anomalies_details_list = detect_simple_anomalies(df_ccu)
                anomaly_report_str = generate_anomaly_report(anomalies_details_list, knowledge_base)
                print(f"\n{anomaly_report_str}")
            else:
                # Se df_ccu non esiste, generate_anomaly_report gestirà una lista vuota se chiamata,
                # ma è meglio essere espliciti qui se il problema è la generazione dei dati.
                print("\nReport Anomalie: Non è stato possibile generare il report perché i dati CCU non sono stati creati.")

            # Valutazione salute sensori
            if 'df_ccu' in locals() and df_ccu is not None:
                sensor_health_assessment = assess_sensor_health(df_ccu)
                print("\nValutazione Salute Sensori:")
                print(f"  - Conteggio OK: {sensor_health_assessment['OK']}")
                print(f"  - Conteggio WARNING: {sensor_health_assessment['WARNING']}")
                print(f"  - Conteggio ALARM: {sensor_health_assessment['ALARM']}")
                print(f"  - Percentuale WARNING: {sensor_health_assessment['percent_warning']:.2f}%")
                print(f"  - Percentuale ALARM: {sensor_health_assessment['percent_alarm']:.2f}%")
                print(f"  - Stato Generale Sensori: {sensor_health_assessment['overall_health']}")
            else:
                print("\nValutazione Salute Sensori: Non è stato possibile eseguire la valutazione perché i dati CCU non sono stati generati.")

            print("----------------------------\n")
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
