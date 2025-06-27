import json
import os
import re
import pandas as pd
from datetime import datetime, timedelta
import random
# import math # Non più usato direttamente, rimosso per pulizia
import sqlite3
from thefuzz import fuzz # Import per il calcolo della similarità fuzzy

KNOWLEDGE_BASE_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'knowledge_base.json')
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'ccu_data.db')

def load_knowledge_base(filepath: str) -> list[dict]:
    """
    Carica la base di conoscenza da un file JSON.
    La nuova struttura prevede un array di "entries" direttamente.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # La base di conoscenza è ora un array di entries
            if isinstance(data, dict) and "entries" in data and isinstance(data["entries"], list):
                return data["entries"]
            else:
                print(f"Errore: Il file della base di conoscenza in {filepath} non ha la struttura attesa con un array 'entries'.")
                return []
    except FileNotFoundError:
        print(f"Errore: Il file della base di conoscenza non è stato trovato in {filepath}")
        return []
    except json.JSONDecodeError:
        print(f"Errore: Il file della base di conoscenza in {filepath} non è un JSON valido.")
        return []

# Non più necessario con la nuova struttura KB, la ricerca sarà basata su keywords/fuzzy
# def normalize_input_for_exact_match(text: str) -> str:
#     text = text.lower()
#     text = re.sub(r'[^\w\s-]', '', text)
#     text = re.sub(r'\s+', '_', text)
#     text = text.strip('_')
#     return text

def normalize_text_for_search(text: str) -> str:
    """
    Normalizza il testo per la ricerca: lowercase e rimozione punteggiatura base.
    """
    text = text.lower()
    # Rimuove la punteggiatura eccetto apostrofi e trattini che potrebbero essere in parole
    text = re.sub(r'[^\w\s\'-]', '', text)
    text = re.sub(r'\s+', ' ', text).strip() # Normalizza spazi multipli
    return text

def decompose_question(original_user_input: str) -> list[str]:
    if not original_user_input:
        return []
    sentences = re.findall(r'[^.?!]+(?:[.?!]|$)', original_user_input)
    if not sentences:
        sentences = [original_user_input]
    final_sub_questions = []
    conjunction_pattern = r'\s+\b(e|o|oppure|e poi|e anche|ed anche|o anche)\b\s+'
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        parts = re.split(conjunction_pattern, sentence, flags=re.IGNORECASE)
        current_sub_sentence = ""
        if len(parts) > 1:
            for part_idx, part_content in enumerate(parts):
                is_conjunction = part_content.lower().strip() in ["e", "o", "oppure", "e poi", "e anche", "ed anche", "o anche"]
                if not is_conjunction and part_content.strip():
                    current_sub_sentence += part_content
                    is_last_part = (part_idx == len(parts) - 1)
                    next_part_is_conjunction_or_end = True
                    if not is_last_part and (part_idx + 1 < len(parts)):
                         next_part_is_conjunction_or_end = parts[part_idx+1].lower().strip() in ["e", "o", "oppure", "e poi", "e anche", "ed anche", "o anche"]
                    if current_sub_sentence.strip() and (is_last_part or next_part_is_conjunction_or_end) :
                        final_sub_questions.append(current_sub_sentence.strip())
                        current_sub_sentence = ""
                elif is_conjunction and current_sub_sentence.strip():
                    final_sub_questions.append(current_sub_sentence.strip())
                    current_sub_sentence = ""
            if current_sub_sentence.strip():
                final_sub_questions.append(current_sub_sentence.strip())
        else:
            final_sub_questions.append(sentence.strip())
    filtered_questions = [q.strip() for q in final_sub_questions if q.strip() and len(q.strip().split()) > 1]
    if not filtered_questions and original_user_input.strip():
        less_filtered = [q.strip() for q in final_sub_questions if q.strip()]
        if less_filtered:
            return less_filtered
        return [original_user_input.strip()]
    return filtered_questions if filtered_questions else [original_user_input.strip()]

def normalize_key_for_storage(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'\s+', '_', text)
    return text.strip('_')

def add_knowledge(category: str, key: str, value: str, filepath: str = KNOWLEDGE_BASE_PATH) -> bool:
    try:
        current_kb = {}
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                try:
                    current_kb = json.load(f)
                except json.JSONDecodeError:
                    print(f"Avviso: {filepath} contiene JSON non valido. Sarà sovrascritto se si aggiunge conoscenza.")
                    current_kb = {}
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
    if not knowledge_base:
        return []
    # La vecchia funzione get_categories non è più applicabile con la nuova struttura KB
    # if not knowledge_base:
    #     return []
    # return list(knowledge_base.keys())
    # Invece, se necessario, si potrebbe estrarre le categorie uniche dalle entries:
    if not knowledge_base_entries: # Usa il nuovo nome della variabile
        return []
    categories = set()
    for entry in knowledge_base_entries:
        if "category" in entry and isinstance(entry["category"], str):
            # Le categorie possono essere stringhe separate da virgole
            cats = [c.strip() for c in entry["category"].split(',')]
            categories.update(cats)
        elif "category" in entry and isinstance(entry["category"], list): # Supporta anche liste di categorie
             categories.update(entry["category"])
    return sorted(list(categories))


def is_query_generic(normalized_query: str, common_generic_terms: set) -> bool:
    """
    Determina se una query è generica basandosi sulla lunghezza e sulla presenza di termini comuni.
    """
    query_words = set(normalized_query.split())
    # Considera generica una query con poche parole O che contiene termini molto comuni
    # e non molti altri termini specifici.
    if len(query_words) <= 3: # Query molto corte sono spesso generiche
        return True
    if any(term in query_words for term in common_generic_terms) and len(query_words - common_generic_terms) <= 2:
        # Se contiene termini generici e solo 1-2 altre parole, probabilmente è generica
        return True
    return False

def find_answer_for_query(user_input: str, knowledge_base_entries: list[dict]) -> str | None:
    """
    Trova la risposta migliore per una data query utente utilizzando la nuova struttura della knowledge base.
    Considera 'domanda', 'varianti_domanda', 'level', e 'specificity_score'.
    """
    if not knowledge_base_entries:
        return None

    normalized_user_input = normalize_text_for_search(user_input)
    if not normalized_user_input.strip():
        return None # Input utente vuoto o solo spazi

    best_match_entry = None
    highest_score = -1

    # Termini comuni che indicano una domanda generica (da espandere se necessario)
    COMMON_GENERIC_TERMS = {"cosa", "cos'è", "spiega", "spiegami", "dimmi", "che", "qual è", "come funziona", "definizione"}
    query_is_potentially_generic = is_query_generic(normalized_user_input, COMMON_GENERIC_TERMS)

    # Soglia minima di similarità testuale per considerare un match valido
    MIN_FUZZY_SCORE_THRESHOLD = 75 # Abbassato per permettere più match iniziali, poi filtrati da specificità
    HIGH_FUZZY_SCORE_FOR_SPECIFIC_OVERRIDE = 90 # Se il match testuale è molto alto, la specificità alta può vincere

    for entry in knowledge_base_entries:
        current_text_match_score = 0

        # 1. Calcolo del punteggio di similarità testuale (Fuzzy Matching)
        # Controlla la domanda principale
        q_text = normalize_text_for_search(entry.get("domanda", ""))
        score_domanda = fuzz.WRatio(normalized_user_input, q_text) # WRatio gestisce bene differenze di lunghezza
        current_text_match_score = score_domanda

        # Controlla le varianti della domanda e prendi il punteggio massimo
        for variante in entry.get("varianti_domanda", []):
            v_text = normalize_text_for_search(variante)
            score_variante = fuzz.WRatio(normalized_user_input, v_text)
            if score_variante > current_text_match_score:
                current_text_match_score = score_variante

        # Se il punteggio di similarità testuale è troppo basso, scarta questa entry
        if current_text_match_score < MIN_FUZZY_SCORE_THRESHOLD:
            continue

        # 2. Calcolo del punteggio finale considerando specificità e level
        # Inizializza il punteggio finale con il punteggio testuale
        final_entry_score = float(current_text_match_score)

        specificity_score = entry.get("specificity_score", 50) # Default a media specificità
        level = entry.get("level", "general") # Default a general

        # Logica di priorità per specificità e level:
        if query_is_potentially_generic:
            # Per domande generiche, favorisci risposte 'general' e con basso `specificity_score`
            if level == "general":
                final_entry_score += 20 # Bonus per level general su query generica
            # Penalizza o favorisci in base a `specificity_score` (inversamente)
            # Un `specificity_score` più basso è migliore per query generiche.
            # Normalizziamo il punteggio di specificità (0-100) in un modificatore.
            # Ad esempio, un punteggio di 10 (molto generale) aggiunge di più di un punteggio di 80.
            final_entry_score += (100 - specificity_score) * 0.2 # Modificatore basato su quanto è generale
        else: # Query probabilmente specifica
            # Per domande specifiche, favorisci risposte con alto `specificity_score`
            # a meno che il level sia 'general' e il match testuale non sia altissimo.
            if level == "specific":
                 final_entry_score += 15 # Bonus per level specific su query specifica
            final_entry_score += specificity_score * 0.3 # Modificatore basato su quanto è specifica

            # Se una risposta 'general' ha un match testuale molto alto, può comunque essere una buona candidata
            if level == "general" and current_text_match_score >= HIGH_FUZZY_SCORE_FOR_SPECIFIC_OVERRIDE:
                final_entry_score += 10 # Piccolo bonus per risposte generali con ottimo match testuale anche per query specifiche
            elif level == "general": # Penalizza risposte generali per query specifiche se il match non è eccellente
                final_entry_score -= (specificity_score * 0.1)


        # Ulteriore bonus se la domanda principale (non varianti) ha un match molto forte,
        # indica che la entry è stata pensata primariamente per quel tipo di domanda.
        if score_domanda > 90 and score_domanda >= current_text_match_score: # score_domanda è il match con entry["domanda"]
            final_entry_score += 5

        # DEBUG: print(f"Entry ID {entry.get('id')}: Text Score: {current_text_match_score}, Specificity: {specificity_score}, Level: {level}, Query Generic: {query_is_potentially_generic}, Final Score: {final_entry_score}")

        if final_entry_score > highest_score:
            highest_score = final_entry_score
            best_match_entry = entry
        elif final_entry_score == highest_score and best_match_entry is not None:
            # Tie-breaking:
            # 1. Preferisci specificità più alta se la query non è generica
            # 2. Preferisci specificità più bassa (più generale) se la query è generica
            # 3. Preferisci match testuale più alto se gli altri fattori sono uguali

            current_specificity = entry.get("specificity_score", 50)
            best_specificity = best_match_entry.get("specificity_score", 50)

            prefer_current = False
            if query_is_potentially_generic:
                if current_specificity < best_specificity: # Più generale è meglio
                    prefer_current = True
                elif current_specificity == best_specificity and current_text_match_score > fuzz.WRatio(normalized_user_input, normalize_text_for_search(best_match_entry.get("domanda",""))):
                     prefer_current = True # Se stessa generalità, preferisci miglior match testuale
            else: # Query specifica
                if current_specificity > best_specificity: # Più specifico è meglio
                    prefer_current = True
                elif current_specificity == best_specificity and current_text_match_score > fuzz.WRatio(normalized_user_input, normalize_text_for_search(best_match_entry.get("domanda",""))):
                    prefer_current = True # Se stessa specificità, preferisci miglior match testuale

            if prefer_current:
                 best_match_entry = entry


    if best_match_entry:
        # print(f"DEBUG: Best match for '{user_input}': Entry ID {best_match_entry.get('id')}, Score: {highest_score}, Answer: {best_match_entry.get('risposta')[:60]}...")
        response_text = best_match_entry.get("risposta", "Risposta non trovata per questa voce.")
        followups = best_match_entry.get("followup_suggestions", [])
        if followups:
            response_text += "\n\nPotresti anche chiedermi:\n" + "\n".join([f"- {sugg}" for sugg in followups])
        return response_text

    # Messaggio "Non so" migliorato
    # print(f"DEBUG: No suitable match found for '{user_input}' with new logic. Highest score: {highest_score}")
    return "Mi dispiace, non ho trovato una risposta precisa nella mia attuale base di conoscenza. Prova a riformulare la tua domanda o a chiedere qualcosa di più specifico."


# --- Funzioni relative a CCU e simulazione (principalmente invariate per questo task, eccetto chiamate a KB) ---
def simulate_ccu_data_acquisition(num_records: int) -> pd.DataFrame:
    data = []
    current_time = datetime.now()
    wp_start = random.uniform(6000.0, 8000.0)
    wp_increment = random.uniform(-100.0, 100.0)
    mf_start = random.uniform(900.0, 1100.0)
    mf_increment = random.uniform(-20.0, 20.0)
    ANOMALY_PROBABILITY = 0.10
    anomaly_active_for = None
    anomaly_counter = 0
    for i in range(num_records):
        timestamp = current_time - timedelta(seconds=random.randint(0, 300))
        base_wp = wp_start + i * wp_increment
        base_mf = mf_start + i * mf_increment
        noise_wp = base_wp * random.uniform(-0.05, 0.05)
        current_wp = base_wp + noise_wp
        noise_mf = base_mf * random.uniform(-0.05, 0.05)
        current_mf = base_mf + noise_mf
        current_wp = max(0, min(current_wp, 18000))
        current_mf = max(0, min(current_mf, 2000))
        current_sensor_status = 'OK'
        if anomaly_active_for and anomaly_counter > 0:
            anomaly_type, _ = anomaly_active_for
            if anomaly_type == 'peak_pressure': current_wp = random.uniform(11000.0, 15000.0)
            elif anomaly_type == 'drop_pressure': current_wp = random.uniform(3000.0, 4500.0)
            elif anomaly_type == 'drop_flow': current_mf = random.uniform(300.0, 500.0)
            elif anomaly_type == 'high_flow': current_mf = random.uniform(1300.0, 1600.0)
            elif anomaly_type == 'sensor_issue': current_sensor_status = random.choice(['WARNING', 'ALARM'])
            anomaly_counter -= 1
            if anomaly_counter == 0: anomaly_active_for = None
        elif random.random() < ANOMALY_PROBABILITY:
            anomaly_duration = random.randint(1, 2)
            anomaly_type = random.choice(['peak_pressure', 'drop_pressure', 'drop_flow', 'high_flow', 'sensor_issue'])
            anomaly_active_for = (anomaly_type, anomaly_duration)
            anomaly_counter = anomaly_duration
            if anomaly_type == 'peak_pressure': current_wp = random.uniform(11000.0, 15000.0)
            elif anomaly_type == 'drop_pressure': current_wp = random.uniform(3000.0, 4500.0)
            elif anomaly_type == 'drop_flow': current_mf = random.uniform(300.0, 500.0)
            elif anomaly_type == 'high_flow': current_mf = random.uniform(1300.0, 1600.0)
            elif anomaly_type == 'sensor_issue': current_sensor_status = random.choice(['WARNING', 'ALARM'])
        record = {
            'timestamp': timestamp, 'well_pressure_psi': round(current_wp, 2),
            'mud_flow_rate_gpm': round(current_mf, 2),
            'bop_ram_position_mm': round(random.uniform(0.0, 250.0), 2),
            'sensor_status': current_sensor_status,
            'temperature_celsius': round(random.uniform(50.0, 150.0), 2)
        }
        data.append(record)
    df = pd.DataFrame(data)
    df = df.sort_values(by='timestamp').reset_index(drop=True)
    return df

def analyze_ccu_data(df: pd.DataFrame) -> dict:
    numerical_cols = ['well_pressure_psi', 'mud_flow_rate_gpm', 'bop_ram_position_mm', 'temperature_celsius']
    analysis_results = {}
    for col in numerical_cols:
        if col in df.columns:
            stats = df[col].agg(['mean', 'std', 'min', 'max']).to_dict()
            analysis_results[col] = {stat_name: round(stat_value, 2) if pd.notnull(stat_value) else None
                                     for stat_name, stat_value in stats.items()}
        else:
            analysis_results[col] = {"error": "Colonna non trovata nel DataFrame"}
    return analysis_results

def detect_simple_anomalies(df: pd.DataFrame, basic_stats: dict) -> list[dict]:
    anomalies = []
    STD_FACTOR = 2.5
    numerical_cols_for_std_dev_check = ['well_pressure_psi', 'mud_flow_rate_gpm', 'bop_ram_position_mm', 'temperature_celsius']
    for row in df.itertuples(index=False):
        ts = row.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        anomaly_record = None
        for col_name in numerical_cols_for_std_dev_check:
            if col_name not in basic_stats or 'mean' not in basic_stats[col_name] or 'std' not in basic_stats[col_name]:
                continue
            mean_val = basic_stats[col_name]['mean']
            std_val = basic_stats[col_name]['std']
            current_val = getattr(row, col_name)
            if std_val is not None and std_val > 0:
                lower_bound = mean_val - STD_FACTOR * std_val
                upper_bound = mean_val + STD_FACTOR * std_val
                msg_prefix = f"[{ts}] Valore {col_name.replace('_', ' ').capitalize()} anomalo (dev. std.): {current_val:.2f}"
                msg_details = f"(Media: {mean_val:.2f}, Std: {std_val:.2f}, Limiti: [{lower_bound:.2f}, {upper_bound:.2f}])"
                if current_val < lower_bound:
                    anomaly_type_key = f"{col_name}_dev_std_anomala_bassa"
                    anomaly_record = {'message': f"{msg_prefix} < Soglia Inf. {msg_details}", 'type': anomaly_type_key}
                    anomalies.append(anomaly_record)
                elif current_val > upper_bound:
                    anomaly_type_key = f"{col_name}_dev_std_anomala_alta"
                    anomaly_record = {'message': f"{msg_prefix} > Soglia Sup. {msg_details}", 'type': anomaly_type_key}
                    anomalies.append(anomaly_record)
        if row.sensor_status == 'WARNING':
            anomaly_record = {'message': f"[{ts}] Stato Sensore: WARNING", 'type': "sensor_warning"}
            anomalies.append(anomaly_record)
        elif row.sensor_status == 'ALARM':
            anomaly_record = {'message': f"[{ts}] Stato Sensore: ALARM", 'type': "sensor_alarm"}
            anomalies.append(anomaly_record)
    return anomalies

def generate_anomaly_report(anomalies_details: list[dict], knowledge_base: dict) -> str:
    if not anomalies_details:
        return "Report Anomalie: Nessuna anomalia significativa rilevata."
    report_parts = ["REPORT ANOMALIE RILEVATE:"]
    for detail in anomalies_details:
        report_parts.append(f"  - {detail['message']}")
    suggestions_found = []
    # Modificato per riflettere che knowledge_base è ora una lista di entries.
    # La logica specifica per "problem_solving_suggestions" dovrebbe essere rivista
    # se queste informazioni sono ora integrate nelle entries standard.
    # Per ora, questa parte potrebbe non funzionare come prima se "problem_solving_suggestions"
    # non è una entry dedicata o una categoria specifica.
    # Assumiamo per ora che non ci siano suggerimenti specifici di problem solving dalla KB in questo formato.
    # TODO: Rivedere la logica di recupero dei suggerimenti per anomalie se necessario.
    # problem_solving_kb = knowledge_base.get("problem_solving_suggestions", {}) # Vecchia logica
    # unique_anomaly_types = sorted(list(set(detail['type'] for detail in anomalies_details)))
    # for anomaly_type in unique_anomaly_types:
    #     suggestion_key = f"{anomaly_type}_suggerimento"
    #     # Questa ricerca non funzionerà più direttamente, serve un modo per cercare entries rilevanti
    #     # suggestion = problem_solving_kb.get(suggestion_key)
    #     suggestion = None # Placeholder
    #     if suggestion:
    #         display_anomaly_type = anomaly_type.replace('_', ' ').capitalize()
    #         suggestions_found.append(f"  - Riguardo '{display_anomaly_type}': {suggestion}")
    # if suggestions_found:
    #     report_parts.append("\n\nSuggerimenti per il Problem Solving (da KB):")
    #     report_parts.extend(suggestions_found)
    report_parts.append("\n\nSi consiglia verifica approfondita dei parametri segnalati.")
    return "\n".join(report_parts)

def assess_sensor_health(df: pd.DataFrame) -> dict:
    if df is None or df.empty or 'sensor_status' not in df.columns:
        return {'OK': 0, 'WARNING': 0, 'ALARM': 0, 'percent_warning': 0.0, 'percent_alarm': 0.0, 'overall_health': 'Indeterminato (dati non disponibili o colonna sensor_status mancante)'}
    counts = df['sensor_status'].value_counts()
    ok_count = counts.get('OK', 0)
    warning_count = counts.get('WARNING', 0)
    alarm_count = counts.get('ALARM', 0)
    total_records = len(df)
    if total_records == 0: return {'OK': 0, 'WARNING': 0, 'ALARM': 0, 'percent_warning': 0.0, 'percent_alarm': 0.0, 'overall_health': 'Indeterminato (nessun record)'}
    percent_warning = round((warning_count / total_records) * 100, 2)
    percent_alarm = round((alarm_count / total_records) * 100, 2)
    ALARM_IS_CRITICAL = True
    WARNING_ATTENTION_THRESHOLD_PERCENT = 20.0
    overall_health = 'Stabile'
    if ALARM_IS_CRITICAL and alarm_count > 0: overall_health = 'Critico'
    elif percent_warning >= WARNING_ATTENTION_THRESHOLD_PERCENT: overall_health = 'Attenzione'
    return {'OK': ok_count, 'WARNING': warning_count, 'ALARM': alarm_count, 'percent_warning': percent_warning, 'percent_alarm': percent_alarm, 'overall_health': overall_health}

def generate_overall_status_summary(anomalies_details: list[dict], sensor_health_assessment: dict) -> str:
    if sensor_health_assessment.get('overall_health') == 'Critico':
        return "STATO SISTEMA: CRITICO! (Salute sensori critica) Agire immediatamente."
    has_alarm_type_anomaly = any(detail.get('type') == 'sensor_alarm' for detail in anomalies_details if anomalies_details)
    if has_alarm_type_anomaly:
        return "STATO SISTEMA: CRITICO! (Rilevato ALARM specifico nei dati) Agire immediatamente."
    if sensor_health_assessment.get('overall_health') == 'Attenzione':
        return "STATO SISTEMA: ATTENZIONE. (Salute sensori richiede attenzione) Si raccomanda verifica."
    has_warning_type_anomaly = any(detail.get('type') == 'sensor_warning' for detail in anomalies_details if anomalies_details)
    if has_warning_type_anomaly:
        return "STATO SISTEMA: ATTENZIONE. (Rilevato WARNING specifico nei dati) Si raccomanda verifica."
    if anomalies_details and sensor_health_assessment.get('overall_health') == 'Stabile':
        return "STATO SISTEMA: ATTENZIONE. (Rilevate deviazioni nei dati operativi) Si raccomanda verifica."
    if sensor_health_assessment.get('overall_health') == 'Stabile' and not anomalies_details:
        return "STATO SISTEMA: OK. Operazioni nella norma."
    return "STATO SISTEMA: Indeterminato. Verificare i report dettagliati."

def save_ccu_data(df: pd.DataFrame, db_path: str = DB_PATH) -> bool:
    if df is None or df.empty:
        print("Nessun dato CCU da salvare.")
        return False
    try:
        data_dir = os.path.dirname(db_path)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        conn = sqlite3.connect(db_path)
        df.to_sql('ccu_readings', conn, if_exists='append', index=False)
        conn.close()
        return True
    except sqlite3.Error as e:
        print(f"Errore SQLite durante il salvataggio dei dati CCU: {e}")
        return False
    except Exception as e:
        print(f"Errore imprevisto durante il salvataggio dei dati CCU: {e}")
        return False

def load_ccu_data(db_path: str = DB_PATH) -> pd.DataFrame:
    if not os.path.exists(db_path):
        return pd.DataFrame()
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ccu_readings';")
        if cursor.fetchone() is None:
            conn.close()
            return pd.DataFrame()
        df = pd.read_sql_query("SELECT * FROM ccu_readings", conn)
        conn.close()
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    except sqlite3.Error as e:
        print(f"Errore SQLite durante il caricamento dei dati CCU: {e}")
        return pd.DataFrame()
    except Exception as e:
        print(f"Errore imprevisto durante il caricamento dei dati CCU: {e}")
        return pd.DataFrame()

def start_pascal_cli():
    knowledge_base = load_knowledge_base(KNOWLEDGE_BASE_PATH)
    if not knowledge_base:
        print("Avvio di P.A.S.C.A.L. non riuscito a causa di problemi con la base di conoscenza principale.")
        # Considerare se uscire o continuare con funzionalità limitate.
        # Per ora, se la KB non si carica, PASCAL avrà funzionalità molto limitate.
        # Le funzioni che dipendono dalla KB (come find_answer_for_query) dovrebbero gestire una KB vuota.
        print("Avvio di P.A.S.C.A.L. con funzionalità limitate a causa di problemi con la base di conoscenza principale.")

    print("Ciao! Sono P.A.S.C.A.L. il tuo assistente AI. Digita 'aiuto' per le mie capacità o 'esci' per terminare.")
    while True:
        user_input_original = input("> ").strip()
        if not user_input_original: continue
        if user_input_original.lower() == 'esci':
            print("Arrivederci!")
            break
        if user_input_original.lower() == 'aiuto':
            print("\nComandi disponibili:")
            print("  aiuto - Mostra questo messaggio di aiuto.")
            print("  esci  - Termina P.A.S.C.A.L.")
            print("  aggiungi conoscenza - Permette di inserire nuove informazioni nella base di conoscenza.")
            print("  simula dati ccu - Simula l'acquisizione e l'analisi di dati CCU.")
            print("  mostra dati storici ccu - Carica e analizza i dati CCU storici.")
            print("Puoi anche farmi domande dirette, ad esempio 'Cosa sai sull'energia?'.\n") # Esempio aggiornato
            continue

        user_input_lower = user_input_original.lower() # Mantengo per comandi specifici

        # La funzione 'aggiungi conoscenza' è stata rimossa perché la nuova struttura KB è più complessa
        # e richiede la creazione di oggetti JSON strutturati, non semplici coppie chiave-valore.
        # L'aggiunta di nuove voci dovrebbe avvenire tramite modifica diretta del file JSON
        # o tramite uno strumento dedicato (non parte di questo task).
        # if user_input_lower == 'aggiungi conoscenza':
        #     print("\n--- Aggiunta Nuova Conoscenza (Funzionalità Disabilitata) ---")
        #     print("L'aggiunta di conoscenza tramite interfaccia è temporaneamente disabilitata.")
        #     print("Modificare direttamente il file 'data/knowledge_base.json' per aggiungere nuove voci.")
        #     # ... (codice precedente commentato o rimosso) ...
        #     print("-----------------------------------\n")
        #     continue

        if user_input_lower == 'simula dati ccu':
            print("\n--- Simulazione Dati CCU ---")
            df_ccu = None # Inizializza per il blocco finally o per controllo
            analysis = None
            anomalies_details_list = []
            sensor_health_assessment = {}
            try:
                df_ccu = simulate_ccu_data_acquisition(num_records=10)
                print("Dati CCU simulati e acquisiti con successo!")
                print("\nPrime 5 righe dei dati CCU simulati:")
                print(df_ccu.head().to_string())

                analysis = analyze_ccu_data(df_ccu)
                print("\nAnalisi di base dei dati CCU:")
                for column_name, stats_dict in analysis.items():
                    print(f"\nStatistiche per {column_name}:")
                    if "error" in stats_dict: print(f"  - Errore: {stats_dict['error']}")
                    else:
                        for stat_name, stat_value in stats_dict.items():
                            value_str = f"{stat_value:.2f}" if stat_value is not None else "N/A"
                            print(f"  - {stat_name.capitalize()}: {value_str}")

                anomalies_details_list = detect_simple_anomalies(df_ccu, analysis)
                anomaly_report_str = generate_anomaly_report(anomalies_details_list, knowledge_base)
                print(f"\n{anomaly_report_str}")

                sensor_health_assessment = assess_sensor_health(df_ccu)
                print("\nValutazione Salute Sensori:")
                print(f"  - Conteggio OK: {sensor_health_assessment.get('OK',0)}")
                print(f"  - Conteggio WARNING: {sensor_health_assessment.get('WARNING',0)}")
                print(f"  - Conteggio ALARM: {sensor_health_assessment.get('ALARM',0)}")
                print(f"  - Percentuale WARNING: {sensor_health_assessment.get('percent_warning',0.0):.2f}%")
                print(f"  - Percentuale ALARM: {sensor_health_assessment.get('percent_alarm',0.0):.2f}%")
                print(f"  - Stato Generale Sensori: {sensor_health_assessment.get('overall_health','Indeterminato')}")

                overall_summary = generate_overall_status_summary(anomalies_details_list, sensor_health_assessment)
                print("\n\nRiepilogo Stato Sistema:")
                print(f"  {overall_summary}")

                if df_ccu is not None and not df_ccu.empty:
                    if save_ccu_data(df_ccu): print("\nDati CCU simulati salvati nel database per analisi futura.")
                    else: print("\nErrore durante il salvataggio dei dati CCU simulati nel database.")

            except Exception as e:
                print(f"Errore durante la simulazione, analisi o salvataggio dei dati CCU: {e}")
            print("----------------------------\n")
            continue

        if user_input_lower == 'mostra dati storici ccu':
            print("\n--- Dati Storici CCU ---")
            df_historical = load_ccu_data()
            if not df_historical.empty:
                print("Dati storici CCU caricati con successo.")
                print(f"Numero totale di record storici: {len(df_historical)}")
                print("\nPrime 5 righe dei dati storici CCU:")
                print(df_historical.head().to_string())
                historical_analysis = analyze_ccu_data(df_historical)
                print("\nAnalisi di base dei dati storici CCU:")
                for column_name, stats_dict in historical_analysis.items():
                    print(f"\nStatistiche per {column_name}:")
                    if "error" in stats_dict: print(f"  - Errore: {stats_dict['error']}")
                    else:
                        for stat_name, stat_value in stats_dict.items():
                            value_str = f"{stat_value:.2f}" if stat_value is not None else "N/A"
                            print(f"  - {stat_name.capitalize()}: {value_str}")
            else:
                print("Nessun dato storico CCU da mostrare o errore durante il caricamento.")
            print("------------------------\n")
            continue

        sub_question_strings = decompose_question(user_input_original)
        collected_answers = []
        for sub_query_string in sub_question_strings:
            if not sub_query_string.strip(): continue
            answer = find_answer_for_query(sub_query_string, knowledge_base)
            if answer and answer not in collected_answers: collected_answers.append(answer)

        if collected_answers: print("\n---\n".join(collected_answers))
        else: print("Sto ancora imparando. Per ora, posso solo gestire i comandi specifici o cercare alcune parole chiave nella mia conoscenza. Prova 'aiuto'.")

if __name__ == "__main__":
    start_pascal_cli()
