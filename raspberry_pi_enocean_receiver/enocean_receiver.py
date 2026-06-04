'''
Titre : CQ2A/raspberry_pi_enocean_receiver/enocean_receiver.py
Nom : Hammouda
Prénom : Rayan
Date : 21/05/2026
'''

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

# ID émetteur EnOcean utilisé pour commander la prise du ventilateur
PRISE_ID = "FE:FE:96:B8"

import time
import traceback
import urllib.request
import urllib.error
import json
from datetime import datetime
import enocean.utils

# Délai minimum (secondes) entre deux commandes ventilateur pour éviter le softlock
VENTILATEUR_COOLDOWN = 15

from enocean.consolelogger import init_logging
from enocean.communicators.serialcommunicator import SerialCommunicator
from enocean.protocol.packet import Packet
from enocean.protocol.constants import PACKET, RORG


# =============================================================================
# CONTRÔLE AUTOMATIQUE DU VENTILATEUR
# =============================================================================

# État courant du ventilateur (évite les commandes redondantes)
_ventilateur_actif    = False
_ventilateur_last_cmd = 0.0    # Timestamp de la dernière commande (anti-softlock)


def _recolter_proc_ventilateur():
    """
    Conservé pour compatibilité avec la boucle principale.
    Le contrôle ventilateur n'utilise plus de sous-processus pour éviter
    tout conflit d'accès au port série.
    """
    return


def _id_str_to_list(id_str):
    return [int(x, 16) for x in id_str.split(":")]


def _envoyer_rps_direct(communicator, sender_id_list, data_byte, status):
    data = [RORG.RPS, data_byte] + sender_id_list + [status]
    optional = [0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00]
    packet = Packet(packet_type=PACKET.RADIO_ERP1, data=data, optional=optional)
    communicator.send(packet)
    time.sleep(0.05)


def _commander_prise_direct(action):
    """
    Commande ON/OFF via le communicator déjà ouvert.
    Evite le softlock causé par un second accès concurrent à /dev/serial0.
    """
    global communicator

    if communicator is None:
        print("  [VENTILATEUR] Communicator indisponible.")
        return False

    sender_id_list = _id_str_to_list(PRISE_ID)
    try:
        if action == "on":
            _envoyer_rps_direct(communicator, sender_id_list, 0x50, 0x30)
            time.sleep(0.16)
            _envoyer_rps_direct(communicator, sender_id_list, 0x00, 0x20)
        elif action == "off":
            _envoyer_rps_direct(communicator, sender_id_list, 0x70, 0x30)
            time.sleep(0.16)
            _envoyer_rps_direct(communicator, sender_id_list, 0x00, 0x20)
        else:
            print(f"  [VENTILATEUR] Action inconnue : {action}")
            return False
        return True
    except Exception as e:
        print(f"  [VENTILATEUR] Erreur envoi trame {action}: {e}")
        return False


def commander_ventilateur(action):
    """
    Envoie la commande ON/OFF en direct depuis ce process.
    Evite le double accès série causé par le lancement d'un second script.
    """
    global _ventilateur_actif, _ventilateur_last_cmd

    if action not in ("on", "off"):
        print(f"  [VENTILATEUR] Action invalide : {action}")
        return False

    # Si l'état est déjà celui demandé, ne rien faire (anti-trame redondante).
    if (_ventilateur_actif and action == "on") or (not _ventilateur_actif and action == "off"):
        print(f"  [VENTILATEUR] État déjà {'ON' if _ventilateur_actif else 'OFF'} → commande '{action}' ignorée.")
        return False

    # Respecter le cooldown inter-commandes
    now = time.time()
    elapsed = now - _ventilateur_last_cmd
    if elapsed < VENTILATEUR_COOLDOWN:
        print(f"  [VENTILATEUR] ⚠ Commande '{action}' ignorée : cooldown ({elapsed:.1f}s / {VENTILATEUR_COOLDOWN}s).")
        return False

    ok = _commander_prise_direct(action)
    if ok:
        _ventilateur_actif = (action == "on")
        _ventilateur_last_cmd = now
        print(f"  [VENTILATEUR] Commande '{action.upper()}' envoyée.")
        return True
    print(f"  [VENTILATEUR] Échec commande '{action.upper()}'.")
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
# CALCUL AQI (version simple 0-100)
# =============================================================================

def score(valeur, limites):
    """Transforme une valeur brute en score (0 à 100)."""
    if valeur is None:
        return None

    for maximum, score_associe in limites.items():
        if valeur <= maximum:
            return score_associe
    return 0


def compute_aqi(mesures: dict):
    """
    AQI simple (0 à 100) :
    - base = pire score entre PM1 / PM2.5 / PM10 / CO2 / COV
    - malus confort selon température et humidité
    """
    scores = []

    s_pm1 = score(mesures.get("pm1"),   {10: 100, 20: 80, 35: 60, 50: 40, 75: 20})
    s_pm25 = score(mesures.get("pm2_5"), {10: 100, 25: 80, 45: 60, 65: 40, 150: 20})
    s_pm10 = score(mesures.get("pm10"),  {20: 100, 50: 80, 80: 60, 100: 40, 200: 20})
    s_co2 = score(mesures.get("co2"),   {600: 100, 1000: 80, 1500: 60, 2000: 40, 5000: 20})
    s_cov = score(mesures.get("cov"),   {50: 100, 150: 80, 300: 60, 500: 40, 1000: 20})

    for s in (s_pm1, s_pm25, s_pm10, s_co2, s_cov):
        if s is not None:
            scores.append(s)

    if not scores:
        return None

    base = min(scores)

    temp = mesures.get("temperature")
    if temp is None:
        temp_penalty = 0
    elif 19 <= temp <= 25:
        temp_penalty = 0
    elif 17 <= temp <= 27:
        temp_penalty = -3
    else:
        temp_penalty = -5

    humi = mesures.get("humidite")
    if humi is None:
        humi_penalty = 0
    elif 40 <= humi <= 60:
        humi_penalty = 0
    elif 30 <= humi <= 70:
        humi_penalty = -3
    else:
        humi_penalty = -5

    aqi = max(0, min(100, base + temp_penalty + humi_penalty))
    print(f"  AQI calculé : {aqi}")
    return float(aqi)


# =============================================================================
# FALLBACK : VALEURS PRÉCÉDENTES
#
# Deux niveaux de repli pour garantir un AQI même en cas de sonde muette :
#
#   1. Cache mémoire (_cache_mesures) : mis à jour à chaque réception réelle.
#      Gratuit, instantané, prioritaire.
#
#   2. API GET (dernier enregistrement en base) : interrogée au démarrage
#      pour pré-remplir le cache, et en secours si le cache est vide
#      (ex : premier démarrage du script sans aucune mesure reçue encore).
#
# Les valeurs de repli sont loguées avec la mention "[REPLI]" pour traçabilité.
# Elles ne remplacent jamais une vraie mesure reçue dans ce cycle.
# =============================================================================

# Champs pouvant bénéficier d'un repli (clés du buffer interne)
_CHAMPS_REPLI = ("temperature", "humidite", "co2", "cov", "pm1", "pm2_5", "pm10")

# Correspondance clé buffer → clé JSON renvoyée par l'API GET
_CLE_API = {
    "temperature": "Temperature",
    "humidite":    "humidite",
    "co2":         "CO2",
    "cov":         "COV",
    "pm1":         "PM1",
    "pm2_5":       "PM2_5",
    "pm10":        "PM10",
}

# Cache mémoire : conserve la dernière vraie valeur reçue pour chaque champ
_cache_mesures = {k: None for k in _CHAMPS_REPLI}


def _mettre_a_jour_cache(mesures):
    """
    Après chaque réception réelle, on mémorise les valeurs non-None
    afin de les réutiliser comme repli lors du prochain cycle.
    """
    for champ in _CHAMPS_REPLI:
        val = mesures.get(champ)
        if val is not None:
            _cache_mesures[champ] = val


def _recuperer_derniere_mesure_api():
    """
    Interroge l'API (GET data.php) pour récupérer la dernière ligne en base.
    Appelée uniquement au démarrage pour pré-remplir le cache.
    Retourne un dict {champ_buffer: valeur} ou {} en cas d'erreur.
    """
    try:
        req = urllib.request.Request(API_URL, method="GET")
        with urllib.request.urlopen(req, timeout=API_TIMEOUT) as r:
            body = r.read().decode("utf-8")
            data = json.loads(body)

            # La réponse GET est {"total":N, "limit":N, "offset":N, "data":[...]}
            # On extrait la liste "data" ; ordre DESC -> le plus recent est en [0]
            if isinstance(data, dict) and "data" in data:
                rows = data["data"]
                if not rows:
                    return {}
                data = rows[0]
            elif isinstance(data, list):
                if not data:
                    return {}
                data = data[0]

            result = {}
            for champ, cle_api in _CLE_API.items():
                val = data.get(cle_api)
                if val is not None:
                    try:
                        result[champ] = float(val)
                    except (ValueError, TypeError):
                        pass
            return result
    except Exception as e:
        print(f"  [REPLI] Impossible de récupérer la dernière mesure API : {e}")
        return {}


def appliquer_repli(mesures):
    """
    Complète les champs None du buffer courant avec :
      1. le cache mémoire (valeur reçue lors d'un cycle précédent)
      2. sinon, la dernière valeur en base (déjà chargée dans le cache au
         démarrage via _recuperer_derniere_mesure_api)
    Retourne une COPIE du dict mesures complétée, sans modifier l'original.
    """
    completes = dict(mesures)
    replis    = []

    for champ in _CHAMPS_REPLI:
        if completes.get(champ) is None:
            val_repli = _cache_mesures.get(champ)
            if val_repli is not None:
                completes[champ] = val_repli
                replis.append(f"{champ}={val_repli} [REPLI]")

    if replis:
        print(f"  [REPLI] Valeurs substituées : {', '.join(replis)}")
    else:
        print(f"  [REPLI] Toutes les valeurs sont fraîches, aucun repli nécessaire.")

    return completes


# =============================================================================
# ENVOI API HTTP
# =============================================================================

def envoyer_data(mesures):
    """
    Envoie les mesures à l'API via POST HTTP.
    Correspond exactement aux champs attendus par data.php.

    Avant l'envoi :
      - Les valeurs manquantes (None) sont comblées par les dernières valeurs
        connues (cache mémoire ou dernier enregistrement API).
      - Le cache est mis à jour avec les valeurs fraîches reçues dans ce cycle.
      - L'AQI est calculé sur le jeu de données complété.

    CORRECTIF AQI : l'AQI est calculé APRÈS appliquer_repli (sur mesures_completes)
    et toujours inclus dans le payload même s'il vaut 0. Le filtre None ne supprime
    plus l'AQI : on conserve explicitement "AQI" dans le payload si compute_aqi
    renvoie une valeur (float), y compris 0.0 qui est falsy en Python mais valide.
    """
    # 1. Mémoriser les valeurs fraîches reçues dans ce cycle
    _mettre_a_jour_cache(mesures)

    # 2. Compléter les valeurs manquantes par les valeurs précédentes
    mesures_completes = appliquer_repli(mesures)

    # 3. Calculer l'AQI sur le jeu complet (mesures_completes contient déjà les replis)
    aqi = compute_aqi(mesures_completes)
    if aqi is None:
        # Dernier recours : tenter avec le cache seul
        aqi = compute_aqi(_cache_mesures)

    # CORRECTIF AQI : stocker l'AQI dans mesures_completes pour que
    # _envoyer_et_gerer puisse le transmettre tel quel (et pour cohérence des logs).
    if aqi is not None:
        mesures_completes["aqi"] = aqi

    payload = {
        "Temps":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Temperature": mesures_completes.get("temperature"),
        "humidite":    mesures_completes.get("humidite"),
        "CO2":         mesures_completes.get("co2"),
        "COV":         mesures_completes.get("cov"),
        "PM10":        mesures_completes.get("pm10"),
        "PM2_5":       mesures_completes.get("pm2_5"),
        "PM1":         mesures_completes.get("pm1"),
        # CORRECTIF AQI : on construit l'entrée AQI séparément pour ne pas
        # la supprimer par le filtre générique "v is not None" qui éliminait
        # aussi les valeurs 0.0 (falsy). Le champ n'est omis que si vraiment None.
        "AQI":         aqi,
    }

    # Supprimer les champs None uniquement — on ne filtre plus sur falsiness
    # pour ne pas éliminer des valeurs légitimes comme 0.0 (AQI parfait).
    payload = {k: v for k, v in payload.items() if v is not None}
    # "Temps" ne peut pas être None (datetime.now() est toujours défini),
    # donc pas besoin de cas particulier pour lui.

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
            return True, mesures_completes
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"  → ERREUR API HTTP {e.code} : {body}")
    except urllib.error.URLError as e:
        print(f"  → ERREUR API connexion : {e.reason}")
    except Exception as e:
        print(f"  → ERREUR API inattendue : {e}")
        traceback.print_exc()
    return False, mesures_completes


def _envoyer_et_gerer(buffer_snapshot):
    """
    Wrapper qui enchaîne envoyer_data + gerer_ventilateur en passant
    les mesures COMPLÈTES (après repli) au ventilateur.
    """
    ok, mesures_completes = envoyer_data(buffer_snapshot)
    gerer_ventilateur(mesures_completes)


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
        _envoyer_et_gerer(buffer)
        reset_buffer()

    print(f"--------------------------")


def verifier_timeout_buffer():
    """Envoie et vide le buffer si le timeout est dépassé."""
    global buffer_ts
    if buffer_ts is not None and (time.time() - buffer_ts) > BUFFER_TIMEOUT:
        manquantes = sondes_actives() - buffer_recu
        noms = [SONDES[s]["nom"] for s in manquantes]
        print(f"\n[TIMEOUT] Sondes non reçues : {', '.join(noms)} → envoi partiel à l'API")
        _envoyer_et_gerer(buffer)
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

# Test de connectivité API au démarrage + pré-chargement du cache de repli
print(f"\nTest connexion API...")
try:
    derniere = _recuperer_derniere_mesure_api()
    if derniere:
        _cache_mesures.update(derniere)
        champs_charges = [f"{k}={v}" for k, v in derniere.items()]
        print(f"API accessible — cache repli pré-chargé : {', '.join(champs_charges)}")
    else:
        print(f"API accessible mais aucune donnée précédente trouvée.")
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
        _recolter_proc_ventilateur()   # Libère le verrou si la commande ventilateur est terminée
        time.sleep(0.05)

except KeyboardInterrupt:
    print("\nArrêt utilisateur")

finally:
    communicator.stop()
    print("Communication EnOcean arrêtée.")
