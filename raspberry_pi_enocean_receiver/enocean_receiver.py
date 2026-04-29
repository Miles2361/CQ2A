#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# =============================================================================
# Récepteur EnOcean - NanoSense E4000 / P4000
# Décodage EEP A5-09-04 (CO2, Humidité, Température)
#          EEP A5-09-05 (COV)
#          EEP A5-09-07 (Particules fines PM1, PM2.5, PM10)
# Envoi des données via API HTTP → data.php
# Contrôle automatique du ventilateur selon les seuils de qualité d'air
# =============================================================================

SERIAL_PORT = "/dev/serial0"

# --- Configuration API ---
API_URL     = "http://cq2a-2026.lycee-lgm.fr/API/data.php"
API_TIMEOUT = 5   # secondes

# --- Configuration des sondes ---
# EEP connus : "A5-09-04" (CO2+Hum+Temp), "A5-09-05" (COV), "A5-09-07" (PM)
SONDES = {
    "FF:D5:A8:0A": {"nom": "E4000",     "eep": "A5-09-04"},  # CO2 + Température + Humidité
    "FF:D5:A8:0F": {"nom": "E4000_COV", "eep": "A5-09-05"},  # COV uniquement
    "FF:D5:A8:14": {"nom": "P4000",     "eep": "A5-09-07"},  # Particules fines PM1/PM2.5/PM10
}

# Timeout en secondes : si une sonde ne répond pas, on envoie quand même
BUFFER_TIMEOUT = 60

# =============================================================================
# SEUILS DE QUALITÉ D'AIR - contrôle automatique du ventilateur
#
# ON  : le ventilateur s'allume si AU MOINS UN seuil "danger" est dépassé
# OFF : le ventilateur s'éteint uniquement quand TOUS les seuils "sécurité"
#       sont repassés en dessous (hysteresis pour éviter les oscillations)
#
# Valeurs de référence :
#   CO2  : < 1000 ppm  (bon), 1000-2000 ppm (moyen), > 2000 ppm (dangereux)
#   COV  : < 50 ppm    (bon), > 100 ppm (dangereux)   [équiv. formaldéhyde]
#   PM2.5: < 25 µg/m³  (OMS), > 50 µg/m³ (dangereux)
#   PM10 : < 50 µg/m³  (OMS), > 100 µg/m³ (dangereux)
# =============================================================================

SEUILS = {
    # Valeurs au-dessus desquelles le ventilateur s'ALLUME
    "danger": {
        "co2":   1500,   # ppm
        "cov":   50,     # ppm équiv. formaldéhyde
        "pm2_5": 25,     # µg/m³
        "pm10":  50,     # µg/m³
    },
    # Valeurs en dessous desquelles le ventilateur s'ÉTEINT (hysteresis ~20%)
    "securite": {
        "co2":   1200,   # ppm
        "cov":   35,     # ppm
        "pm2_5": 15,     # µg/m³
        "pm10":  35,     # µg/m³
    },
}

# Chemin vers le script de commande de la prise/ventilateur
PRISE_SCRIPT = "/home/pi/CQ2A/raspberry_pi_transmitter/prise_commande.py"

import time
import traceback
import urllib.request
import urllib.error
import json
import subprocess
from datetime import datetime
import enocean.utils

from enocean.consolelogger import init_logging
from enocean.communicators.serialcommunicator import SerialCommunicator
from enocean.protocol.constants import PACKET


# =============================================================================
# CONTRÔLE AUTOMATIQUE DU VENTILATEUR
# =============================================================================

# État courant du ventilateur (évite les commandes redondantes)
_ventilateur_actif = False

def commander_ventilateur(action):
    """
    Lance prise_commande.py avec l'action 'on' ou 'off'.
    Retourne True si la commande a réussi.
    """
    global _ventilateur_actif
    try:
        result = subprocess.run(
            ["python3", PRISE_SCRIPT, action],
            timeout=10,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            _ventilateur_actif = (action == "on")
            print(f"  [VENTILATEUR] Commande '{action.upper()}' envoyée avec succès.")
            return True
        else:
            print(f"  [VENTILATEUR] Erreur commande '{action}' (code {result.returncode}): {result.stderr.strip()}")
    except subprocess.TimeoutExpired:
        print(f"  [VENTILATEUR] Timeout lors de la commande '{action}'.")
    except Exception as e:
        print(f"  [VENTILATEUR] Exception : {e}")
    return False


def gerer_ventilateur(mesures):
    """
    Vérifie les mesures par rapport aux seuils et commande le ventilateur.

    Logique d'hysteresis :
      - S'il est éteint  → l'allumer si AU MOINS UN seuil "danger" est dépassé
      - S'il est allumé  → l'éteindre uniquement si TOUS les seuils "securite" sont OK
    """
    global _ventilateur_actif

    # Construire la liste des dépassements de seuil "danger"
    depassements = []
    for capteur, seuil in SEUILS["danger"].items():
        valeur = mesures.get(capteur)
        if valeur is not None and valeur > seuil:
            depassements.append(f"{capteur}={valeur} > {seuil}")

    # Construire la liste des capteurs encore au-dessus du seuil "sécurité"
    encore_eleves = []
    for capteur, seuil in SEUILS["securite"].items():
        valeur = mesures.get(capteur)
        if valeur is not None and valeur > seuil:
            encore_eleves.append(f"{capteur}={valeur} > {seuil}")

    if not _ventilateur_actif:
        # Ventilateur éteint → l'allumer si au moins un seuil danger est dépassé
        if depassements:
            print(f"  [VENTILATEUR] ⚠ Seuils dépassés : {', '.join(depassements)}")
            print(f"  [VENTILATEUR] → Activation automatique du ventilateur.")
            commander_ventilateur("on")
        else:
            print(f"  [VENTILATEUR] Qualité d'air OK, ventilateur inactif.")
    else:
        # Ventilateur allumé → l'éteindre seulement si tout est revenu sous sécurité
        if encore_eleves:
            print(f"  [VENTILATEUR] Encore élevé : {', '.join(encore_eleves)} → ventilateur maintenu ON.")
        else:
            print(f"  [VENTILATEUR] ✓ Tous les seuils sont repassés sous la limite de sécurité.")
            print(f"  [VENTILATEUR] → Désactivation automatique du ventilateur.")
            commander_ventilateur("off")


# =============================================================================
# ENVOI API HTTP
# =============================================================================

def envoyer_data(mesures):
    """
    Envoie les mesures à l'API via POST HTTP.
    Correspond exactement aux champs attendus par data.php.
    """
    payload = {
        "Temps":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Temperature": mesures.get("temperature"),
        "humidite":    mesures.get("humidite"),
        "CO2":         mesures.get("co2"),
        "COV":         mesures.get("cov"),
        "PM10":        mesures.get("pm10"),
        "PM2_5":       mesures.get("pm2_5"),
        "PM1":         mesures.get("pm1"),
    }

    # Supprimer les champs None pour ne pas envoyer de nulls inutiles
    payload = {k: v for k, v in payload.items() if v is not None or k == "Temps"}

    data    = json.dumps(payload).encode("utf-8")
    req     = urllib.request.Request(
        API_URL,
        data    = data,
        headers = {"Content-Type": "application/json"},
        method  = "POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=API_TIMEOUT) as response:
            body = response.read().decode("utf-8")
            resp = json.loads(body)
            print(f"  → API OK ({response.status}) : {resp.get('message', '')} | Id_DATA={resp.get('Id_DATA', '?')}")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"  → ERREUR API HTTP {e.code} : {body}")
    except urllib.error.URLError as e:
        print(f"  → ERREUR API connexion : {e.reason}")
    except Exception as e:
        print(f"  → ERREUR API inattendue : {e}")
        traceback.print_exc()
    return False


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
    return {
        "humidite":    round(data[1] / 250.0 * 100.0, 1),
        "co2":         round(data[2] * 10.0, 0),
        "temperature": round(data[3] / 255.0 * 51.0, 1),
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
# Accumule les mesures de toutes les sondes et envoie une seule ligne
# à l'API dès que toutes les sondes ont répondu, ou après BUFFER_TIMEOUT s.
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
buffer_recu = set()
buffer_ts   = None

def reset_buffer():
    global buffer, buffer_recu, buffer_ts
    buffer      = {k: None for k in buffer}
    buffer_recu = set()
    buffer_ts   = None

def sondes_actives():
    return set(SONDES.keys())


# =============================================================================
# TRAITEMENT D'UN PAQUET
# =============================================================================

def traiter_paquet(packet):
    global buffer, buffer_recu, buffer_ts

    sender = "inconnu"
    try:
        sender = enocean.utils.to_hex_string(packet.sender).upper()
    except:
        pass

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

    if (data[4] >> 3) & 0x01 == 0:
        print("  → Télégramme d'appairage (LRN), ignoré.")
        return

    print(f"  EEP fixe : {eep}")

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

    # Mise à jour du buffer
    if buffer_ts is None:
        buffer_ts = time.time()

    buffer.update(mesures)
    buffer_recu.add(sender)

    manquantes = sondes_actives() - buffer_recu
    noms_manquants = [SONDES[s]["nom"] for s in manquantes]
    print(f"  → Buffer : {len(buffer_recu)}/{len(sondes_actives())} sondes reçues")
    if noms_manquants:
        print(f"  → En attente de : {', '.join(noms_manquants)}")

    # Envoi si toutes les sondes ont répondu
    if buffer_recu >= sondes_actives():
        print(f"  → Toutes les sondes reçues, envoi à l'API...")
        envoyer_data(buffer)
        gerer_ventilateur(buffer)   # ← Contrôle automatique du ventilateur
        reset_buffer()

    print(f"--------------------------")


def verifier_timeout_buffer():
    """Envoie et vide le buffer si le timeout est dépassé."""
    global buffer_ts
    if buffer_ts is not None and (time.time() - buffer_ts) > BUFFER_TIMEOUT:
        manquantes = sondes_actives() - buffer_recu
        noms = [SONDES[s]["nom"] for s in manquantes]
        print(f"\n[TIMEOUT] Sondes non reçues : {', '.join(noms)} → envoi partiel à l'API")
        envoyer_data(buffer)
        gerer_ventilateur(buffer)   # ← Contrôle automatique du ventilateur
        reset_buffer()


# =============================================================================
# INITIALISATION ENOCEAN
# =============================================================================

init_logging()

communicator = SerialCommunicator(port=SERIAL_PORT)
communicator.start()
time.sleep(1)

print("\n====== RÉCEPTEUR ENOCEAN - E4000 / P4000 ======")
print(f"Port série : {SERIAL_PORT}")
print(f"API URL    : {API_URL}")

if communicator.base_id:
    print(f"BaseID     : {enocean.utils.to_hex_string(communicator.base_id)}")

# Test de connectivité API au démarrage
print(f"\nTest connexion API...")
try:
    req = urllib.request.Request(API_URL, method="GET")
    with urllib.request.urlopen(req, timeout=API_TIMEOUT) as r:
        print(f"API accessible (HTTP {r.status})")
except Exception as e:
    print(f"⚠ API non accessible : {e}")
    print("Le script continue, les données seront envoyées dès que l'API répond.")

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
                    traiter_paquet(packet)
                else:
                    print(f"Autre paquet : {packet}")

            except Exception:
                traceback.print_exc()

        verifier_timeout_buffer()
        time.sleep(0.05)

except KeyboardInterrupt:
    print("\nArrêt utilisateur")

finally:
    communicator.stop()
    print("Communication EnOcean arrêtée.")
