#!/usr/bin/env python
# -*- encoding: utf-8 -*-

# =======================
# ======= CONFIG ========
# =======================

SERIAL_PORT = "/dev/ttyUSB0"  # Linux → décommente si Linux

SEND_EXAMPLE_PACKET = False    # True si tu veux envoyer un paquet test

# =======================

from enocean.consolelogger import init_logging
import enocean.utils
from enocean.communicators.serialcommunicator import SerialCommunicator
from enocean.protocol.packet import RadioPacket
from enocean.protocol.constants import PACKET, RORG
import sys
import traceback

try:
    import queue
except ImportError:
    import Queue as queue


def assemble_radio_packet(transmitter_id):
    return RadioPacket.create(
        rorg=RORG.BS4,
        rorg_func=0x20,
        rorg_type=0x01,
        sender=transmitter_id,
        CV=50,
        TMP=21.5,
        ES='true'
    )


# =======================
# ===== INITIALISATION ==
# =======================

init_logging()

communicator = SerialCommunicator(
    port=SERIAL_PORT,
)

communicator.start()

print("Port utilisé :", SERIAL_PORT)

if communicator.base_id:
    print("Base ID du module :", enocean.utils.to_hex_string(communicator.base_id))

    if SEND_EXAMPLE_PACKET:
        print("Envoi d'un paquet exemple...")
        communicator.send(assemble_radio_packet(communicator.base_id))


# =======================
# ===== BOUCLE RECEPTION
# =======================

print("En attente de trames radio... (CTRL+C pour quitter)")

while communicator.is_alive():
    try:
        packet = communicator.receive.get(block=True, timeout=1)

        if packet.packet_type == PACKET.RADIO_ERP1:

            print("\n--- Nouvelle trame reçue ---")
            print("Sender:", enocean.utils.to_hex_string(packet.sender))
            print("RORG:", packet.rorg)

            # ===== VLD =====
            if packet.rorg == RORG.VLD:
                packet.select_eep(0x05, 0x00)
                packet.parse_eep()
                for k in packet.parsed:
                    print(f"{k}: {packet.parsed[k]}")

            # ===== BS4 =====
            elif packet.rorg == RORG.BS4:
                for k in packet.parse_eep(0x02, 0x05):
                    print(f"{k}: {packet.parsed[k]}")

            # ===== BS1 =====
            elif packet.rorg == RORG.BS1:
                packet.select_eep(0x00, 0x01)
                packet.parse_eep()
                for k in packet.parsed:
                    print(f"{k}: {packet.parsed[k]}")

            # ===== RPS (interrupteurs F6-02-02) =====
            elif packet.rorg == RORG.RPS:
                for k in packet.parse_eep(0x02, 0x02):
                    print(f"{k}: {packet.parsed[k]}")

    except queue.Empty:
        continue

    except KeyboardInterrupt:
        print("\nArrêt demandé par l'utilisateur.")
        break

    except Exception:
        traceback.print_exc(file=sys.stdout)
        break


if communicator.is_alive():
    communicator.stop()
    print("Communication arrêtée.")