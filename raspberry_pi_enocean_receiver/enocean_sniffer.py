#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# =============================================================================
# Sniffer EnOcean - Affichage données brutes
# Aucune insertion en base - debug uniquement
# =============================================================================

SERIAL_PORT = "/dev/serial0"

import time
import traceback
import enocean.utils

from enocean.consolelogger import init_logging
from enocean.communicators.serialcommunicator import SerialCommunicator
from enocean.protocol.constants import PACKET


init_logging()

communicator = SerialCommunicator(port=SERIAL_PORT)
communicator.start()
time.sleep(1)

print("\n====== SNIFFER ENOCEAN - DONNÉES BRUTES ======")
print(f"Port : {SERIAL_PORT}")

if communicator.base_id:
    print(f"BaseID : {enocean.utils.to_hex_string(communicator.base_id)}")

print("En attente de télégrammes...\n")

try:
    while True:

        while not communicator.receive.empty():
            try:
                packet = communicator.receive.get()

                if packet.packet_type == PACKET.RADIO_ERP1:

                    sender = "inconnu"
                    try:
                        sender = enocean.utils.to_hex_string(packet.sender)
                    except:
                        pass

                    rorg = "inconnu"
                    try:
                        rorg = hex(packet.rorg)
                    except:
                        pass

                    data = packet.data

                    print("------- TÉLÉGRAMME BRUT -------")
                    print(f"  Sender   : {sender}")
                    print(f"  RORG     : {rorg}")
                    print(f"  Data hex : {[hex(b) for b in data]}")
                    print(f"  Data dec : {list(data)}")
                    print(f"  Status   : {packet.status}")

                    try:
                        print(f"  RSSI     : {packet.dBm} dBm")
                    except:
                        pass

                    # Détail octet par octet si 4BS (0xA5)
                    if packet.rorg == 0xA5 and len(data) >= 5:
                        db3, db2, db1, db0 = data[1], data[2], data[3], data[4]
                        lrn = (db0 >> 3) & 0x01
                        print(f"  --- Détail 4BS ---")
                        print(f"  DB3 (brut) : {db3}  ({hex(db3)})")
                        print(f"  DB2 (brut) : {db2}  ({hex(db2)})")
                        print(f"  DB1 (brut) : {db1}  ({hex(db1)})")
                        print(f"  DB0 (brut) : {db0}  ({hex(db0)})")
                        print(f"  LRN bit    : {lrn}  ({'données' if lrn == 1 else 'appairage'})")

                    print("-------------------------------\n")

                else:
                    print(f"Autre paquet (type={packet.packet_type}) : {packet}\n")

            except Exception:
                traceback.print_exc()

        time.sleep(0.05)

except KeyboardInterrupt:
    print("\nArrêt utilisateur")

finally:
    communicator.stop()
    print("Communication arrêtée.")
