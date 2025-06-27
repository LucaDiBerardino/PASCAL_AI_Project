import json
import os
import re
import pandas as pd
from datetime import datetime, timedelta
import random
import math
import sqlite3

KNOWLEDGE_BASE_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'knowledge_base.json')
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'ccu_data.db')

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
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'\s+', '_', text)
    text = text.strip('_')
    return text

def normalize_text_for_keyword_search(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
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
    return list(knowledge_base.keys())

def find_answer_for_query(query_text: str, knowledge_base: dict) -> str | None:
    found_answer_text = None
    normalized_for_exact = normalize_input_for_exact_match(query_text)
    for category_content in knowledge_base.values():
        if normalized_for_exact in category_content:
            return category_content[normalized_for_exact]

    best_match_key_strat2 = None
    min_len_key_strat2 = float('inf')
    for category_content in knowledge_base.values():
        for kb_key, kb_answer in category_content.items():
            if normalized_for_exact in kb_key:
                if len(kb_key) < min_len_key_strat2:
                    min_len_key_strat2 = len(kb_key)
                    best_match_key_strat2 = kb_answer
    if best_match_key_strat2:
        return best_match_key_strat2

    user_keywords_text = normalize_text_for_keyword_search(query_text)
    user_keywords_text = normalize_text_for_keyword_search(query_text)
    if not user_keywords_text.strip(): return None

    original_user_words = user_keywords_text.split()
    user_keywords_set = set(original_user_words)
    if not user_keywords_set: return None

    # Definisci pesi per parole chiave specifiche (termini tecnici, nomi propri, ecc.)
    # Questi potrebbero essere espansi o caricati da una configurazione esterna in futuro.
    # Normalizzare le chiavi qui per coerenza con il lookup.
    specific_keyword_weights = {
        normalize_input_for_exact_match(k): v for k, v in {
            # Termini tecnici PASCAL/O&G
            "bop": 3, "blowout preventer": 3, "pressione": 2.5, "pozzo": 2.5, "fango": 2.5,
            "portata": 2.5, "sensore": 2.5, "anomalia": 2.5, "trend": 2.5, "api 53": 3,
            "kick": 3, "lost circulation": 3, "well control": 3, "drilling": 2, "offshore": 2,
            "sottomarino": 2, "formazione": 2, "fluido di perforazione": 2,
            "ccu": 2, "simula": 1.5, "dati": 1.5, "storici": 1.5, "analisi": 1.5, "report": 1.5,
            "salute": 1.5, "stato": 1.5, "sistema": 1.5, "complessivo": 1.5,
            "warning": 2, "alarm": 3, "critico": 3, "stabile": 2, "attenzione": 2,
            # Termini Ingegneria/Elettronica
            "ohm": 3, "legge di ohm": 3.5, "transistore": 3, "corrente": 2, "voltmetro": 2,
            "tensione": 2, "resistenza": 2, "amplificare": 2, "commutare": 2,
            "semiconduttore": 2, "alternata": 2, "continua": 2,
            # Termini Cultura Generale (alcuni esempi, potrebbero essere molti di più)
            "gioconda": 2, "leonardo da vinci": 2.5, "einstein": 2, "relativita": 3,
            "fotosintesi": 2, "dna": 2, "divina commedia": 2, "dante alighieri": 2.5,
            "australia": 1, "capitale": 1.5, "seconda guerra mondiale": 2.5,
            "notte stellata": 2, "van gogh": 2.5, "pianeta": 1, "giove": 2, "sistema solare": 1.5,
            "teorema di pitagora": 2.5,
            # Termini per PASCAL stesso
            "pascal": 3, "capacita": 1.5, "aiuto": 1,
            # Termini generici con peso ridotto o neutro se non specificati diversamente
            "energia": 1.0, # Dare un peso base, ma non troppo alto per evitare override
            "definizione": 1.0, "concetto": 1.0, "generale": 0.5,
            "cosa": 0.1, "come": 0.1, "quando": 0.1, "perche": 0.1, "chi": 0.1, "spiega": 0.1, "dimmi": 0.1,
            "e": 0, "di": 0, "la": 0, "il": 0, "un": 0, "una": 0, "del": 0, "su":0.1, "sai":0.1
        }.items()
    }

    # Pesi per la posizione (le prime parole sono più importanti)
    POSITION_WEIGHT_FACTOR = 0.2
    MAX_POSITION_BONUS_WORDS = 3

    best_overall_score = 0.0
    best_answer_strat3 = None

    # print(f"DEBUG: Query: '{query_text}', User Keywords: {user_keywords_set}")

    for category_name, category_content in knowledge_base.items():
        for kb_key, kb_answer in category_content.items():
            kb_key_words_set = set(kb_key.split('_'))
            common_keywords = user_keywords_set.intersection(kb_key_words_set)

            if not common_keywords:
                continue

            current_key_score = 0.0

            # 1. Punteggio base: Numero di parole chiave comuni.
            #    Ogni parola comune contribuisce con un punteggio base (es. 1) più il suo peso specifico.
            base_common_score = 0
            for kw in common_keywords:
                base_common_score += 1 + specific_keyword_weights.get(kw, 0) # kw è già normalizzata perché viene da user_keywords_set (che deriva da testo normalizzato) o kb_key_words_set (che sono già normali)
            current_key_score += base_common_score

            # 2. Bonus per posizione delle parole chiave comuni nella domanda utente originale.
            #    Dà priorità a match che rispettano l'ordine iniziale delle parole dell'utente.
            for i, user_word_original_case in enumerate(original_user_words[:MAX_POSITION_BONUS_WORDS]):
                normalized_user_word_for_check = normalize_text_for_keyword_search(user_word_original_case)
                if normalized_user_word_for_check in common_keywords:
                    # Il bonus di posizione si aggiunge al punteggio già accumulato dalle parole.
                    # Si potrebbe anche pensare a un fattore moltiplicativo se la parola pesata è all'inizio.
                    current_key_score += (MAX_POSITION_BONUS_WORDS - i) * POSITION_WEIGHT_FACTOR * (1 + specific_keyword_weights.get(normalized_user_word_for_check, 0))


            # 3. Bonus/Malus per specificità e generalità della query e della chiave KB
            #    Se la query è molto breve (es. 1-2 parole) e generica, e la chiave KB è molto specifica e lunga,
            #    potrebbe essere un match casuale.
            #    Se la chiave KB contiene "definizione", "generale", "concetto" e la query è breve, potrebbe essere un buon match.
            query_is_short_and_general = len(user_keywords_set) <= 2 and any(kw in user_keywords_set for kw in ["cosa", "cos_e", "significa", "definizione"])
            key_is_definitional = any(dkw in kb_key_words_set for dkw in ["definizione", "concetto", "generale"])

            if query_is_short_and_general and key_is_definitional:
                current_key_score *= 1.3 # Favorisce definizioni generali per query generiche

            # 4. Bonus per completezza del match.
            #    Si applicano moltiplicatori per dare forte preferenza a match più completi.
            if common_keywords == user_keywords_set == kb_key_words_set: # Match perfetto di tutti i termini
                 current_key_score *= 2.0
            elif common_keywords == user_keywords_set:
                current_key_score *= 1.6 # Tutte le parole utente sono nella chiave KB (la chiave KB potrebbe essere più ampia)
            elif common_keywords == kb_key_words_set:
                current_key_score *= 1.3 # Tutte le parole della chiave KB sono nella domanda utente (la domanda utente potrebbe essere più ampia)

            # print(f"DEBUG: KB Key '{kb_key}' (Cat: {category_name}), Common: {common_keywords}, Score: {current_key_score:.2f}")

            if current_key_score > best_overall_score:
                best_overall_score = current_key_score
                best_answer_strat3 = kb_answer
            elif current_key_score == best_overall_score and best_answer_strat3 is not None:
                # Tie-breaking: preferisci la chiave KB più corta se i punteggi sono identici,
                # assumendo che una chiave più corta sia più mirata.
                # O una risposta più corta. Per ora, manteniamo la prima trovata.
                pass

    # if best_answer_strat3:
    #    print(f"DEBUG: Final Best Match for '{query_text}': Score {best_overall_score:.2f}, Answer: '{best_answer_strat3[:60]}...'")
    # else:
    #    print(f"DEBUG: No keyword match for '{query_text}'")

    if best_overall_score > 0: return best_answer_strat3
    return None

# --- Funzioni relative a CCU e simulazione (invariate per questo task) ---
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
    problem_solving_kb = knowledge_base.get("problem_solving_suggestions", {})
    unique_anomaly_types = sorted(list(set(detail['type'] for detail in anomalies_details)))
    for anomaly_type in unique_anomaly_types:
        suggestion_key = f"{anomaly_type}_suggerimento"
        suggestion = problem_solving_kb.get(suggestion_key)
        if suggestion:
            display_anomaly_type = anomaly_type.replace('_', ' ').capitalize()
            suggestions_found.append(f"  - Riguardo '{display_anomaly_type}': {suggestion}")
    if suggestions_found:
        report_parts.append("\n\nSuggerimenti per il Problem Solving:")
        report_parts.extend(suggestions_found)
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
        # Considerare se uscire o continuare con funzionalità limitate
        # return
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
            print("Puoi anche farmi domande dirette, ad esempio 'chi ha dipinto la gioconda'.\n")
            continue

        user_input_lower = user_input_original.lower()

        if user_input_lower == 'aggiungi conoscenza':
            print("\n--- Aggiunta Nuova Conoscenza ---")
            if not knowledge_base: print("Attenzione: la base di conoscenza sembra essere vuota o non caricata.")
            print(f"Categorie esistenti: {get_categories(knowledge_base)}")
            category_input = input("Inserisci la categoria: ").strip()
            if not category_input: print("Categoria non valida. Annullamento."); continue
            key_input = input("Inserisci la domanda o la chiave: ").strip()
            if not key_input: print("Chiave/domanda non valida. Annullamento."); continue
            value_input = input("Inserisci la risposta o il valore: ").strip()
            if not value_input: print("Valore/risposta non valido. Annullamento."); continue
            if add_knowledge(category_input, key_input, value_input):
                print("Conoscenza aggiunta con successo!")
                knowledge_base = load_knowledge_base(KNOWLEDGE_BASE_PATH)
                if not knowledge_base: print("Attenzione: problemi durante il ricaricamento della KB aggiornata.")
            else: print("Errore durante l'aggiunta della conoscenza.")
            print("-----------------------------------\n")
            continue

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
