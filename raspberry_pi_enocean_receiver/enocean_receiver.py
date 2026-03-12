#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# =============================================================================
# Récepteur EnOcean - NanoSense E4000 / P4000
# Décodage EEP A5-09-04 (CO2, Humidité, Température)
#          EEP A5-09-05 (COV)
#          EEP A5-09-07 (Particules fines PM1, PM2.5, PM10)
# Insertion dans la table DATA de la base CQ2A
# =============================================================================

SERIAL_PORT = "/dev/serial0"

# --- Configuration MariaDB ---
DB_HOST     = "172.16.116.52"
DB_PORT     = 3306
DB_NAME     = "CQ2A"
DB_USER     = "root"
DB_PASSWORD = "eclipse"

# --- Configuration des sondes ---
# Associer chaque adresse EnOcean à son nom et son EEP fixe
# EEP connus : "A5-09-04" (CO2+Hum+Temp), "A5-09-05" (COV), "A5-09-07" (PM)
SONDES = {
    "FF:D5:A8:0A": {"nom": "E4000",  "eep": "A5-09-04"},  # CO2 + Température + Humidité
    "FF:D5:A8:0F": {"nom": "E4000_COV", "eep": "A5-09-05"},  # COV uniquement
    "FF:D5:A8:14": {"nom": "P4000",  "eep": "A5-09-07"},  # Particules fines PM1/PM2.5/PM10
}

# Timeout en secondes : si une sonde ne répond pas dans ce délai,
# on insère quand même avec ses champs à NULL
BUFFER_TIMEOUT = 60

import time
import traceback
from datetime import datetime
import enocean.utils
import mariadb

from enocean.consolelogger import init_logging
from enocean.communicators.serialcommunicator import SerialCommunicator
from enocean.protocol.constants import PACKET


# =============================================================================
# CONNEXION BASE DE DONNÉES
# =============================================================================

def connect_db():
    """Crée et retourne une connexion MariaDB."""
    conn = mariadb.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        autocommit=True
    )
    return conn


# =============================================================================
# DÉCODAGE EEP
# =============================================================================

def decode_A5_09_04(data):
    """
    EEP A5-09-04 : CO2 + Humidité + Température
    DB3 (index 1) : Humidité    → brut / 250 * 100  → % RH
    DB2 (index 2) : CO2         → brut * 10          → ppm
    DB1 (index 3) : Température → brut / 255 * 51    → °C
    """
    humidite    = round(data[1] / 250.0 * 100.0, 1)
    co2         = round(data[2] * 10.0, 0)
    temperature = round(data[3] / 255.0 * 51.0, 1)

    return {
        "temperature": temperature,
        "humidite":    humidite,
        "co2":         co2,
    }


def decode_A5_09_05(data):
    """
    EEP A5-09-05 : COV
    DB2 (index 2) : COV → brut (0-255) en ppm équiv. formaldéhyde
    """
    return {
        "cov": round(float(data[2]), 2),
    }


def decode_A5_09_07(data):
    """
    EEP A5-09-07 : Particules fines (P4000 relayée par E4000)
    DB3 (index 1) : PM1   → brut en µg/m³
    DB2 (index 2) : PM2.5 → brut en µg/m³
    DB1 (index 3) : PM10  → brut en µg/m³
    """
    return {
        "pm1":   float(data[1]),
        "pm2_5": float(data[2]),
        "pm10":  float(data[3]),
    }





# =============================================================================
# BUFFER GLOBAL
# On accumule les mesures de toutes les sondes et on insère une seule ligne
# dans DATA dès que toutes les sondes actives ont envoyé leurs données,
# ou après BUFFER_TIMEOUT secondes.
# =============================================================================

buffer = {
    "temperature": None,
    "humidite":    None,
    "co2":         None,
    "cov":         None,
    "pm1":         None,
    "pm2_5":       None,
    "pm10":        None,
}
buffer_recu = set()       # sondes ayant déjà envoyé dans ce cycle
buffer_ts   = None        # timestamp du premier télégramme du cycle

def reset_buffer():
    global buffer, buffer_recu, buffer_ts
    buffer = {k: None for k in buffer}
    buffer_recu = set()
    buffer_ts   = None

def sondes_actives():
    """Retourne la liste des adresses de sondes configurées."""
    return set(SONDES.keys())

def inserer_data(conn, mesures):
    """Insère une ligne complète dans la table DATA."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO DATA
            (Temps, Temperature, humidite, CO2, COV, PM10, PM2_5, PM1)
        VALUES
            (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now(),
        mesures.get("temperature"),
        mesures.get("humidite"),
        mesures.get("co2"),
        mesures.get("cov"),
        mesures.get("pm10"),
        mesures.get("pm2_5"),
        mesures.get("pm1"),
    ))
    cursor.close()


# =============================================================================
# TRAITEMENT D'UN PAQUET
# =============================================================================

def traiter_paquet(conn, packet):
    """Décode le paquet, met à jour le buffer et insère quand toutes les sondes ont répondu."""
    global buffer, buffer_recu, buffer_ts

    sender = "inconnu"
    try:
        sender = enocean.utils.to_hex_string(packet.sender)
    except:
        pass

    # Ignorer les senders non configurés
    if sender not in SONDES:
        print(f"  → Sender {sender} non configuré, ignoré.")
        return

    config    = SONDES[sender]
    sonde_nom = config["nom"]
    eep       = config["eep"]

    rorg = None
    try:
        rorg = packet.rorg
    except:
        pass

    rssi = None
    try:
        rssi = packet.dBm
    except:
        pass

    data = packet.data

    print(f"\n------- TÉLÉGRAMME -------")
    print(f"  Sonde   : {sonde_nom} ({sender})")
    print(f"  RORG    : {hex(rorg) if rorg is not None else 'N/A'}")
    print(f"  Data    : {[hex(b) for b in data]}")
    print(f"  RSSI    : {rssi} dBm" if rssi else "  RSSI   : N/A")

    if rorg != 0xA5:
        print("  → Télégramme non 4BS, ignoré.")
        return

    if len(data) < 5:
        print("  → Trame trop courte, ignorée.")
        return

    lrn_bit = (data[4] >> 3) & 0x01
    if lrn_bit == 0:
        print("  → Télégramme d'appairage (LRN), ignoré.")
        return

    print(f"  EEP fixe    : {eep}")

    # Décodage selon l'EEP fixe de la sonde
    if eep == "A5-09-04":
        mesures = decode_A5_09_04(data)
        print(f"  Température : {mesures['temperature']} °C")
        print(f"  Humidité    : {mesures['humidite']} % RH")
        print(f"  CO2         : {mesures['co2']} ppm")

    elif eep == "A5-09-05":
        mesures = decode_A5_09_05(data)
        print(f"  COV         : {mesures['cov']} ppm éq. formaldéhyde")

    elif eep == "A5-09-07":
        mesures = decode_A5_09_07(data)
        print(f"  PM1         : {mesures['pm1']} µg/m³")
        print(f"  PM2.5       : {mesures['pm2_5']} µg/m³")
        print(f"  PM10        : {mesures['pm10']} µg/m³")

    else:
        print(f"  → EEP {eep} non géré, ignoré.")
        return

    # Mise à jour du buffer global
    if buffer_ts is None:
        buffer_ts = time.time()

    buffer.update(mesures)
    buffer_recu.add(sender)
    print(f"  → Buffer mis à jour ({len(buffer_recu)}/{len(sondes_actives())} sondes reçues)")

    # Insertion si toutes les sondes ont répondu
    if buffer_recu >= sondes_actives():
        inserer_data(conn, buffer)
        print(f"  → Toutes les sondes reçues : inséré dans DATA (CQ2A)")
        reset_buffer()

    print(f"--------------------------")


def verifier_timeout_buffer(conn):
    """Insère et vide le buffer si le timeout est dépassé."""
    global buffer_ts
    if buffer_ts is not None and (time.time() - buffer_ts) > BUFFER_TIMEOUT:
        sondes_manquantes = sondes_actives() - buffer_recu
        print(f"\n[TIMEOUT] Sondes non reçues : {sondes_manquantes} → insertion partielle")
        inserer_data(conn, buffer)
        reset_buffer()


# =============================================================================
# INITIALISATION ENOCEAN
# =============================================================================

init_logging()

communicator = SerialCommunicator(port=SERIAL_PORT)
communicator.start()
time.sleep(1)

print("\n====== RÉCEPTEUR ENOCEAN - E4000 / P4000 ======")
print(f"Port série  : {SERIAL_PORT}")

if communicator.base_id:
    print(f"BaseID      : {enocean.utils.to_hex_string(communicator.base_id)}")

print(f"\nConnexion MariaDB : {DB_USER}@{DB_HOST}/{DB_NAME} ...")
try:
    db_conn = connect_db()
    print("Connexion OK.")
except Exception as e:
    print(f"ERREUR connexion DB : {e}")
    communicator.stop()
    raise

print("\nEn attente de télégrammes...\n")


# =============================================================================
# BOUCLE PRINCIPALE
# =============================================================================

try:
    while True:

        while not communicator.receive.empty():
            try:
                packet = communicator.receive.get()

                if packet.packet_type == PACKET.RADIO_ERP1:
                    traiter_paquet(db_conn, packet)
                else:
                    print(f"Autre paquet : {packet}")

            except Exception:
                traceback.print_exc()

        # Reconnexion DB si besoin
        try:
            db_conn.cursor().execute("SELECT 1")
        except Exception as e:
            print(f"[DB] Reconnexion : {e}")
            try:
                db_conn = connect_db()
            except Exception:
                pass

        verifier_timeout_buffer(db_conn)
        time.sleep(0.05)

except KeyboardInterrupt:
    print("\nArrêt utilisateur")

finally:
    communicator.stop()
    print("Communication EnOcean arrêtée.")
    try:
        db_conn.close()
        print("Connexion DB fermée.")
    except:
        pass
