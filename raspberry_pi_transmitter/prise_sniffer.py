#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# =============================================================================
# Sniffer EnOcean - Identification de la prise DO21-11B-E
# EEP D2-01-0B (VLD)
#
# UTILISATION :
#   1. Lancez ce script
#   2. Appuyez sur le bouton de la prise pour la faire émettre
#   3. Notez le "Sender ID" affiché → c'est l'ID à copier dans prise_commande.py
# =============================================================================

SERIAL_PORT = "/dev/serial0"

import time
import traceback
import enocean.utils

from enocean.consolelogger import init_logging
from enocean.communicators.serialcommunicator import SerialCommunicator
from enocean.protocol.constants import PACKET, RORG

init_logging()

communicator = SerialCommunicator(port=SERIAL_PORT)
communicator.start()
time.sleep(1)

print("====== SNIFFER - Identification prise DO21-11B-E ======")
print(f"Port : {SERIAL_PORT}")

if communicator.base_id:
    print(f"BaseID TCM310 : {enocean.utils.to_hex_string(communicator.base_id)}")

print()
print(">>> Appuyez sur le bouton physique de la prise pour qu'elle émette <<<")
print(">>> L'ID sera affiché ci-dessous. CTRL+C pour quitter.             <<<")
print()

ids_vus = set()

try:
    while True:
        while not communicator.receive.empty():
            try:
                packet = communicator.receive.get()

                if packet.packet_type != PACKET.RADIO_ERP1:
                    continue

                sender = enocean.utils.to_hex_string(packet.sender).upper()

                rorg = "?"
                try:
                    rorg = hex(packet.rorg)
                except Exception:
                    pass

                rssi = "N/A"
                try:
                    rssi = f"{packet.dBm} dBm"
                except Exception:
                    pass

                # Affichage compact de chaque trame reçue
                print(f"  Sender : {sender}  |  RORG : {rorg}  |  RSSI : {rssi}  |  Data : {[hex(b) for b in packet.data]}")

                # Mise en évidence si c'est un VLD (D2-xx → rorg 0xD2)
                if packet.rorg == RORG.VLD and sender not in ids_vus:
                    ids_vus.add(sender)
                    print()
                    print(f"  ★  Prise VLD (D2) détectée ! Sender ID = {sender}")
                    print(f"  ★  Copiez cet ID dans prise_commande.py → PRISE_ID = \"{sender}\"")
                    print()

            except Exception:
                traceback.print_exc()

        time.sleep(0.05)

except KeyboardInterrupt:
    print("\nArrêt utilisateur.")

finally:
    communicator.stop()
    print("Communication arrêtée.")
