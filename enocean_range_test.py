#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# =============================================================================
# TEST DE PORTÉE EnOcean - Analyse du RSSI en dBm
# Compatible NanoSense E4000 / P4000 et tout émetteur EnOcean ERP1
#
# Fonctionnement :
#   - Écoute tous les télégrammes radio reçus
#   - Affiche le RSSI en dBm pour chaque paquet
#   - Calcule les statistiques (min, max, moyenne, nb paquets)
#   - Indique une estimation qualitative de la portée
#   - Sauvegarde optionnelle en CSV pour analyse ultérieure
#
# Usage :
#   python3 enocean_range_test.py
#   python3 enocean_range_test.py --port /dev/ttyUSB0
#   python3 enocean_range_test.py --csv resultats.csv
#   python3 enocean_range_test.py --sender FF:D5:A8:0A   (filtrer une sonde)
#   python3 enocean_range_test.py --duree 60              (arrêt auto après 60s)
# =============================================================================

import argparse
import time
import traceback
import csv
import os
from datetime import datetime
from collections import defaultdict

import enocean.utils
from enocean.consolelogger import init_logging
from enocean.communicators.serialcommunicator import SerialCommunicator
from enocean.protocol.constants import PACKET


# =============================================================================
# INTERPRÉTATION QUALITATIVE DU RSSI
# Valeurs typiques EnOcean 868 MHz :
#   > -60 dBm  : Excellent  (très proche, quelques mètres)
#   -60 à -75  : Bon        (portée confortable)
#   -75 à -85  : Moyen      (limite acceptable, murs épais)
#   -85 à -95  : Faible     (limite de réception, risque de perte)
#   < -95 dBm  : Critique   (très probable perte de paquets)
# =============================================================================

SEUILS_RSSI = [
    (-60,  "🟢 EXCELLENT",  "Signal fort, excellente portée"),
    (-75,  "🟡 BON",        "Signal correct, portée confortable"),
    (-85,  "🟠 MOYEN",      "Portée limite, possible perte occasionnelle"),
    (-95,  "🔴 FAIBLE",     "Signal faible, pertes probables"),
    (-999, "⛔ CRITIQUE",   "Signal très faible, communication instable"),
]

def qualifier_rssi(dbm):
    """Retourne l'évaluation qualitative du RSSI."""
    for seuil, label, desc in SEUILS_RSSI:
        if dbm > seuil:
            return label, desc
    return "⛔ CRITIQUE", "Signal très faible"


def formater_barre(dbm, min_dbm=-100, max_dbm=-40, largeur=30):
    """Affiche une barre de niveau visuelle pour le RSSI."""
    ratio = max(0.0, min(1.0, (dbm - min_dbm) / (max_dbm - min_dbm)))
    rempli = int(ratio * largeur)
    barre = "█" * rempli + "░" * (largeur - rempli)
    return f"[{barre}] {dbm:>4} dBm"


# =============================================================================
# STATISTIQUES PAR ÉMETTEUR
# =============================================================================

class StatsEmetteur:
    def __init__(self, sender_id):
        self.sender_id  = sender_id
        self.nb_paquets = 0
        self.rssi_vals  = []
        self.premiere   = None
        self.derniere   = None

    def ajouter(self, rssi, ts):
        self.nb_paquets += 1
        self.rssi_vals.append(rssi)
        if self.premiere is None:
            self.premiere = ts
        self.derniere = ts

    @property
    def rssi_min(self):
        return min(self.rssi_vals) if self.rssi_vals else None

    @property
    def rssi_max(self):
        return max(self.rssi_vals) if self.rssi_vals else None

    @property
    def rssi_moy(self):
        return round(sum(self.rssi_vals) / len(self.rssi_vals), 1) if self.rssi_vals else None

    def afficher_resume(self):
        if not self.rssi_vals:
            return
        label, desc = qualifier_rssi(self.rssi_moy)
        print(f"\n  Émetteur : {self.sender_id}")
        print(f"  Paquets reçus    : {self.nb_paquets}")
        print(f"  RSSI minimum     : {self.rssi_min} dBm")
        print(f"  RSSI maximum     : {self.rssi_max} dBm")
        print(f"  RSSI moyen       : {self.rssi_moy} dBm  →  {label}")
        print(f"  Évaluation       : {desc}")
        print(f"  Période          : {self.premiere.strftime('%H:%M:%S')} → {self.derniere.strftime('%H:%M:%S')}")


# =============================================================================
# ARGUMENTS EN LIGNE DE COMMANDE
# =============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Test de portée EnOcean - Analyse RSSI en dBm"
    )
    parser.add_argument(
        "--port",   default="/dev/serial0",
        help="Port série du dongle EnOcean (défaut: /dev/serial0)"
    )
    parser.add_argument(
        "--sender", default=None,
        help="Filtrer un émetteur spécifique (ex: FF:D5:A8:0A). Par défaut tous."
    )
    parser.add_argument(
        "--csv",    default=None,
        help="Fichier CSV de sortie pour enregistrer les mesures"
    )
    parser.add_argument(
        "--duree",  type=int, default=0,
        help="Durée du test en secondes (0 = illimité, CTRL+C pour arrêter)"
    )
    parser.add_argument(
        "--intervalle", type=float, default=0.05,
        help="Intervalle de scrutation en secondes (défaut: 0.05)"
    )
    return parser.parse_args()


# =============================================================================
# BOUCLE PRINCIPALE
# =============================================================================

def main():
    args    = parse_args()
    stats   = defaultdict(lambda: None)   # sender_id → StatsEmetteur
    csv_fh  = None
    csv_writer = None

    # --- Préparation CSV ---
    if args.csv:
        nouveau = not os.path.exists(args.csv)
        csv_fh  = open(args.csv, "a", newline="", encoding="utf-8")
        csv_writer = csv.writer(csv_fh)
        if nouveau:
            csv_writer.writerow(["horodatage", "sender", "rorg", "rssi_dbm", "qualite"])
        print(f"  → Enregistrement CSV : {args.csv}")

    # --- Initialisation EnOcean ---
    init_logging()
    communicator = SerialCommunicator(port=args.port)
    communicator.start()
    time.sleep(1)

    print("\n" + "=" * 55)
    print("   TEST DE PORTÉE ENOCEAN — Analyse RSSI")
    print("=" * 55)
    print(f"  Port série   : {args.port}")
    if communicator.base_id:
        print(f"  BaseID       : {enocean.utils.to_hex_string(communicator.base_id)}")
    if args.sender:
        print(f"  Filtre sonde : {args.sender.upper()}")
    if args.duree:
        print(f"  Durée test   : {args.duree} s")
    else:
        print("  Durée test   : illimitée (CTRL+C pour arrêter)")
    print("-" * 55)
    print("  Échelle RSSI :")
    for seuil, label, desc in SEUILS_RSSI:
        print(f"    {label:<18} {desc}")
    print("=" * 55)
    print("  En attente de télégrammes...\n")

    ts_debut = time.time()
    nb_total = 0

    try:
        while True:

            # Vérification durée
            if args.duree and (time.time() - ts_debut) >= args.duree:
                print(f"\n[TEST] Durée de {args.duree}s écoulée, arrêt automatique.")
                break

            while not communicator.receive.empty():
                try:
                    packet = communicator.receive.get()

                    if packet.packet_type != PACKET.RADIO_ERP1:
                        continue

                    # --- Récupération sender ---
                    sender = "INCONNU"
                    try:
                        sender = enocean.utils.to_hex_string(packet.sender).upper()
                    except Exception:
                        pass

                    # --- Filtrage optionnel ---
                    if args.sender and sender != args.sender.upper():
                        continue

                    # --- Récupération RSSI ---
                    rssi = None
                    try:
                        rssi = packet.dBm
                    except Exception:
                        pass

                    if rssi is None:
                        print(f"  [{sender}] RSSI non disponible pour ce paquet.")
                        continue

                    # --- RORG ---
                    rorg_str = "N/A"
                    try:
                        rorg_str = hex(packet.rorg)
                    except Exception:
                        pass

                    # --- Horodatage ---
                    ts_now = datetime.now()
                    nb_total += 1

                    # --- Mise à jour stats ---
                    if stats[sender] is None:
                        stats[sender] = StatsEmetteur(sender)
                    stats[sender].ajouter(rssi, ts_now)

                    # --- Qualification ---
                    label, desc = qualifier_rssi(rssi)
                    barre = formater_barre(rssi)

                    # --- Affichage ---
                    print(f"  [{ts_now.strftime('%H:%M:%S')}] {sender}  RORG={rorg_str}")
                    print(f"    RSSI  : {barre}")
                    print(f"    Qualité : {label}  — {desc}")
                    moy = stats[sender].rssi_moy
                    if stats[sender].nb_paquets > 1:
                        lm, _ = qualifier_rssi(moy)
                        print(f"    Moyenne : {moy} dBm ({lm})  "
                              f"| Min={stats[sender].rssi_min}  "
                              f"Max={stats[sender].rssi_max}  "
                              f"N={stats[sender].nb_paquets}")
                    print()

                    # --- CSV ---
                    if csv_writer:
                        csv_writer.writerow([
                            ts_now.strftime("%Y-%m-%d %H:%M:%S"),
                            sender, rorg_str, rssi, label
                        ])
                        csv_fh.flush()

                except Exception:
                    traceback.print_exc()

            time.sleep(args.intervalle)

    except KeyboardInterrupt:
        print("\n[TEST] Arrêt demandé par l'utilisateur.")

    finally:
        communicator.stop()
        if csv_fh:
            csv_fh.close()

        # -------------------------------------------------------
        # RÉSUMÉ FINAL
        # -------------------------------------------------------
        print("\n" + "=" * 55)
        print("   RÉSUMÉ DU TEST DE PORTÉE")
        print("=" * 55)
        duree_reelle = round(time.time() - ts_debut, 1)
        print(f"  Durée totale   : {duree_reelle} s")
        print(f"  Paquets totaux : {nb_total}")

        if not stats or all(v is None for v in stats.values()):
            print("  Aucune donnée reçue.")
        else:
            for s in stats.values():
                if s is not None:
                    s.afficher_resume()

        print("=" * 55)
        print("  Communication EnOcean arrêtée.")


if __name__ == "__main__":
    main()
