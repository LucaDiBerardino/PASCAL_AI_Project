# Documentazione API di P.A.S.C.A.L.

Versione API: 0.1.0

Questa è la documentazione per l'interfaccia di programmazione (API) di P.A.S.C.A.L. (Personal Assistant for Scientific and Computational ALgorithms).
L'API permette di interrogare la knowledge base del sistema tramite semplici richieste HTTP.

## Endpoint di Base

### GET /

Questo è un endpoint di base usato per verificare che il server API sia attivo e funzionante.

* **Metodo:** `GET`
* **URL:** `/`
* **Parametri:** Nessuno.
* **Risposta di Successo (Codice 200):**
    ```json
    {
      "message": "Benvenuto nell'API di P.A.S.C.A.L."
    }
    ```

## Endpoint di Ricerca

### GET /search

Questo è l'endpoint principale per eseguire una ricerca nella knowledge base di P.A.S.C.A.L.

* **Metodo:** `GET`
* **URL:** `/search`
* **Parametri Query:**
    * `q` (string, **obbligatorio**): La domanda o la stringa di testo da cercare.
    * `limit` (integer, *opzionale*, default: 5): Il numero massimo di risultati da restituire.
* **Esempio di Chiamata:**
    `/search?q=Cos'è+l'API+Spec+Q1&limit=3`
* **Risposta di Successo (Codice 200):**
    Restituisce una lista di risultati. Ogni risultato è una tupla (rappresentata in JSON come una lista di due elementi) contenente:
    1.  Un oggetto JSON con i dettagli della voce trovata (es. id, domanda, risposta, etc.).
    2.  Un numero (float) che rappresenta il punteggio di confidenza (da 0 a 100).

    **Esempio di Risposta:**
    ```json
    [
      [
        {
          "id": 57,
          "question": "Cosa è l'API Spec Q1 e come si implementa?",
          "answer": "L'API Spec Q1 è uno standard di sistema di gestione della qualità...",
          "specificity_level": "intermediate",
          "category": "api_quality"
        },
        100.0
      ]
    ]
    ```
