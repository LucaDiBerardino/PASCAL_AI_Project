import json
import os
import re
import pandas as pd
from datetime import datetime, timedelta
import random
import math
import sqlite3
import sys

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
    if not user_keywords_text.strip(): return None
    user_keywords = set(user_keywords_text.split())
    if not user_keywords: return None
    best_match_score = 0
    best_answer_strat3 = None
    for category_content in knowledge_base.values():
        for kb_key, kb_answer in category_content.items():
            kb_key_keywords = set(kb_key.split('_'))
            common_keywords = user_keywords.intersection(kb_key_keywords)
            score = len(common_keywords)
            if common_keywords == user_keywords and score > 0: score += len(user_keywords)
            elif common_keywords == kb_key_keywords and score > 0: score += len(kb_key_keywords)
            if score > best_match_score:
                best_match_score = score
                best_answer_strat3 = kb_answer
    if best_match_score > 0: return best_answer_strat3
    return None

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

def detect_trends(df: pd.DataFrame, window_size: int = 5, threshold_change_percent: float = 0.02) -> list[dict]:
    """
    Rileva trend significativi e costanti nelle colonne specificate di un DataFrame.
    Restituisce una lista di dizionari, ognuno rappresentante un'anomalia di tendenza.
    """
    trend_anomalies = []
    cols_to_analyze = {
        'well_pressure_psi': 'Pressione Pozzo',
        'mud_flow_rate_gpm': 'Portata Fango',
        'temperature_celsius': 'Temperatura'
    }

    if df is None or len(df) < window_size:
        return trend_anomalies

    # Considera solo gli ultimi 'window_size' record per l'analisi di tendenza
    df_window = df.tail(window_size)

    for col_key, col_name in cols_to_analyze.items():
        if col_key not in df_window.columns:
            continue

        series = df_window[col_key].tolist()

        first_val = series[0]
        last_val = series[-1]

        if first_val == 0:  # Evita divisione per zero
            continue

        percent_change = ((last_val - first_val) / abs(first_val))
        abs_percent_change = abs(percent_change)

        if abs_percent_change < threshold_change_percent:
            continue

        # Verifica la costanza del trend
        is_increasing_trend = all(series[i] <= series[i+1] for i in range(len(series)-1))
        is_decreasing_trend = all(series[i] >= series[i+1] for i in range(len(series)-1))

        # Per considerare un trend valido, deve essere strettamente crescente o decrescente
        # Oltre una certa soglia, non solo uguale per tutta la finestra.
        # E il cambiamento generale deve essere significativo.

        trend_type_suffix = ""
        trend_description = ""

        if percent_change > 0 and is_increasing_trend: # Aumento
            trend_description = f"Trend di {col_name} in AUMENTO: {percent_change*100:.2f}% su ultimi {window_size} record."
            trend_type_suffix = "_trend_aumento"
        elif percent_change < 0 and is_decreasing_trend: # Diminuzione
            trend_description = f"Trend di {col_name} in DIMINUZIONE: {abs(percent_change)*100:.2f}% su ultimi {window_size} record."
            trend_type_suffix = "_trend_diminuzione"

        if trend_description:
            anomaly_type_key = f"{col_key}{trend_type_suffix}"
            trend_anomalies.append({'message': trend_description, 'type': anomaly_type_key})

    return trend_anomalies

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

    # Gestione input da riga di comando
    if len(sys.argv) > 1:
        command_line_input = " ".join(sys.argv[1:])
        process_pascal_command(command_line_input, knowledge_base)
        return # Esce dopo aver eseguito il comando singolo

    print("Ciao! Sono P.A.S.C.A.L. il tuo assistente AI. Digita 'aiuto' per le mie capacità o 'esci' per terminare.")
    while True:
        user_input_original = input("> ").strip()
        if not user_input_original: continue
        if user_input_original.lower() == 'esci':
            print("Arrivederci!")
            break
        process_pascal_command(user_input_original, knowledge_base)

def process_pascal_command(user_input_original: str, knowledge_base: dict):
    """Elabora un singolo comando o query per P.A.S.C.A.L."""
    if user_input_original.lower() == 'aiuto':
        print("\nComandi disponibili:")
        print("  aiuto - Mostra questo messaggio di aiuto.")
        print("  esci  - Termina P.A.S.C.A.L. (solo in modalità interattiva).")
        print("  aggiungi conoscenza - Permette di inserire nuove informazioni nella base di conoscenza.")
        print("  simula dati ccu - Simula l'acquisizione e l'analisi di dati CCU.")
        print("  mostra dati storici ccu - Carica e analizza i dati CCU storici.")
        print("Puoi anche farmi domande dirette, ad esempio 'chi ha dipinto la gioconda'.\n")
        return

    user_input_lower = user_input_original.lower()

    if user_input_lower == 'aggiungi conoscenza':
        print("\n--- Aggiunta Nuova Conoscenza ---")
        if not knowledge_base: print("Attenzione: la base di conoscenza sembra essere vuota o non caricata.")
        # Questa parte richiede input interattivo, quindi potrebbe non funzionare bene se chiamata da riga di comando
        # senza ulteriori modifiche per gestire input non interattivi per 'aggiungi conoscenza'.
        # Per lo scopo di questa richiesta, assumiamo che 'aggiungi conoscenza' sia usato interattivamente.
        print(f"Categorie esistenti: {get_categories(knowledge_base)}")
        category_input = input("Inserisci la categoria: ").strip()
        if not category_input: print("Categoria non valida. Annullamento."); return
        key_input = input("Inserisci la domanda o la chiave: ").strip()
        if not key_input: print("Chiave/domanda non valida. Annullamento."); return
        value_input = input("Inserisci la risposta o il valore: ").strip()
        if not value_input: print("Valore/risposta non valido. Annullamento."); return
        if add_knowledge(category_input, key_input, value_input):
            print("Conoscenza aggiunta con successo!")
            # Ricarica la KB per la sessione corrente se necessario, o assicurati che la modifica sia globale.
            # Per semplicità, qui non la ricarichiamo esplicitamente assumendo che `add_knowledge` aggiorna il file
            # e la prossima esecuzione/istanza la caricherà.
        else: print("Errore durante l'aggiunta della conoscenza.")
        print("-----------------------------------\n")
        return

    if user_input_lower == 'simula dati ccu':
        print("\n--- Simulazione Dati CCU ---")
        df_ccu = None
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

            # Rileva anche le anomalie di tendenza
            trend_anomalies_list = detect_trends(df_ccu, window_size=5, threshold_change_percent=0.02)

            # Unisci le due liste di anomalie
            # Nota: anomalies_details_list contiene dizionari, trend_anomalies_list è stata modificata per contenere dizionari
            # quindi possono essere semplicemente concatenate.
            if trend_anomalies_list:
                anomalies_details_list.extend(trend_anomalies_list)

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
        return

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
        return

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
