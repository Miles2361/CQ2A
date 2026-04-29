#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# =============================================================================
# Commande prise EnOcean - DO21-11B-E (RPS F6-02-01)
#
# Trame RPS calquée exactement sur le bouton physique observé :
#
#   ALLUMER  : data=['0xf6','0x50', ID_PRISE,'0x30']  optional=['0x0','0xff','0xff','0xff','0xff','0xff','0x0']
#   ETEINDRE : data=['0xf6','0x0',  ID_PRISE,'0x20']  optional=['0x0','0xff','0xff','0xff','0xff','0xff','0x0']
#   puis      data=['0xf6','0x0',  ID_PRISE,'0x20']  (relâchement, même trame)
#
# UTILISATION :
#   python3 prise_commande.py on
#   python3 prise_commande.py off
#   python3 prise_commande.py toggle
# =============================================================================

SERIAL_PORT = "/dev/serial0"
PRISE_ID    = "FE:FE:96:B8"

import sys
import time
import traceback
import enocean.utils

from enocean.consolelogger import init_logging
from enocean.communicators.serialcommunicator import SerialCommunicator
from enocean.protocol.packet import Packet
from enocean.protocol.constants import PACKET, RORG


def id_str_to_list(id_str):
    return [int(x, 16) for x in id_str.split(":")]


def envoyer_rps(communicator, sender_id_list, data_byte, status):
    """
    Construit une trame RPS identique au bouton physique :
      data     = [0xF6, data_byte, ID(4 octets), status]
      optional = [0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00]
                   subTelNum=0, dest=broadcast, dBm=0xFF, sec=0
    """
    data = [RORG.RPS, data_byte] + sender_id_list + [status]

    optional = [
        0x00,                       # subTelNum = 0
        0xFF, 0xFF, 0xFF, 0xFF,     # destination = broadcast
        0xFF,                       # dBm (non significatif à l'émission)
        0x00,                       # security level
    ]

    packet = Packet(
        packet_type=PACKET.RADIO_ERP1,
        data=data,
        optional=optional,
    )
    communicator.send(packet)
    time.sleep(0.05)


def allumer(communicator, sender_id_list):
    """Appui 0x50 / status 0x30  puis relâche 0x00 / status 0x20"""
    print("  → Appui   (0x50, status=0x30)")
    envoyer_rps(communicator, sender_id_list, 0x50, 0x30)
    time.sleep(0.16)
    print("  → Relâche (0x00, status=0x20)")
    envoyer_rps(communicator, sender_id_list, 0x00, 0x20)


def eteindre(communicator, sender_id_list):
    """Appui 0x00 / status 0x20 (bouton relâché = état OFF observé)"""
    print("  → Appui   (0x70, status=0x30)")
    envoyer_rps(communicator, sender_id_list, 0x70, 0x30)
    time.sleep(0.16)
    print("  → Relâche (0x00, status=0x20)")
    envoyer_rps(communicator, sender_id_list, 0x00, 0x20)


# =============================================================================
# MAIN
# =============================================================================

def usage():
    print("Usage : python3 prise_commande.py [on|off|toggle|pair]")
    sys.exit(1)

if len(sys.argv) < 2:
    usage()

commande = sys.argv[1].lower()
if commande not in ("on", "off", "toggle","pair"):
    usage()

init_logging()

communicator = SerialCommunicator(port=SERIAL_PORT)
communicator.start()
time.sleep(1)

print(f"====== Commande prise DO21-11B-E (RPS) ======")
print(f"Port      : {SERIAL_PORT}")
print(f"Prise ID  : {PRISE_ID}")

if not communicator.base_id:
    print("⚠  Impossible de lire le BaseID du TCM310.")
    communicator.stop()
    sys.exit(1)

print(f"BaseID    : {enocean.utils.to_hex_string(communicator.base_id)}")

sender_id_list = id_str_to_list(PRISE_ID)

ETAT_FILE = "/tmp/prise_etat.txt"

def lire_etat_local():
    try:
        with open(ETAT_FILE) as f:
            return f.read().strip()
    except FileNotFoundError:
        return "off"

def sauver_etat_local(etat):
    with open(ETAT_FILE, "w") as f:
        f.write(etat)

try:
    if commande == "on":
        print(f"\n→ Commande ON")
        allumer(communicator, sender_id_list)
        sauver_etat_local("on")

    elif commande == "off":
        print(f"\n→ Commande OFF")
        eteindre(communicator, sender_id_list)
        sauver_etat_local("off")

    elif commande == "toggle":
        etat_actuel = lire_etat_local()
        nouvel_etat = "off" if etat_actuel == "on" else "on"
        print(f"\n→ Toggle : {etat_actuel.upper()} → {nouvel_etat.upper()}")
        if nouvel_etat == "on":
            allumer(communicator, sender_id_list)
        else:
            eteindre(communicator, sender_id_list)
        sauver_etat_local(nouvel_etat)

    elif commande == "pair":
        print(f"\n→ Appairage en cours...")
        print(f"  (La prise doit être en mode appairage : LED clignote)")
        allumer(communicator, sender_id_list)
        print(f"  Trame envoyée. La LED doit s'arrêter de clignoter.")

    time.sleep(0.3)

except KeyboardInterrupt:
    print("\nInterruption.")
except Exception:
    traceback.print_exc()
finally:
    communicator.stop()
    print("Communication arrêtée.")
