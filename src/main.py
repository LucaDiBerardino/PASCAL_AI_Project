def start_pascal_cli():
    """
    Avvia l'interfaccia a riga di comando (CLI) per P.A.S.C.A.L.
    """
    print("Ciao! Sono P.A.S.C.A.L. il tuo assistente AI. Digita 'aiuto' per le mie capacità o 'esci' per terminare.")

    while True:
        user_input = input("> ").strip()

        if user_input.lower() == 'esci':
            print("Arrivederci!")
            break
        elif user_input.lower() == 'aiuto':
            print("Comandi disponibili:")
            print("  aiuto - Mostra questo messaggio di aiuto.")
            print("  esci  - Termina P.A.S.C.A.L.")
        else:
            print("Sto ancora imparando. Per ora, posso solo gestire 'esci' o 'aiuto'. Prova a digitare 'aiuto' per vedere i comandi disponibili.")

if __name__ == "__main__":
    start_pascal_cli()
