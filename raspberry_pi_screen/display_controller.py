#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# =============================================================================
# CQ2A — Contrôleur d'écran Raspberry Pi
# Optimisé pour LCD19WV — 1440×900 (16:10)
#
# Sources API :
#   1. GET /raspberry_pi.php  → config écran  (table raspberry_pi)
#   2. GET /data.php          → mesures       (table DATA)
#
# Dépendances :
#   pip install pygame requests
#
# Lancement :
#   DISPLAY=:0 python3 display_controller.py
# =============================================================================

import sys
import time
import math
import socket
import logging
import requests
import threading
from datetime import datetime

import pygame

# =============================================================================
# ── CONFIGURATION ─────────────────────────────────────────────────────────────
# =============================================================================

API_BASE_URL     = "http://cq2a-2026.lycee-lgm.fr/API/"
REFRESH_INTERVAL = 30          # secondes entre chaque appel API
SCREEN_WIDTH     = 1440        # résolution native LCD19WV
SCREEN_HEIGHT    = 900
FULLSCREEN       = True        # mettre False pour déboguer en fenêtré

# Seuils de colorisation (vert / orange / rouge)
THRESHOLDS = {
    "AQI":         {"ok": 50,   "warn": 100},
    "CO2":         {"ok": 800,  "warn": 1200},
    "COV":         {"ok": 0.5,  "warn": 1.0},
    "PM10":        {"ok": 20,   "warn": 50},
    "PM2_5":       {"ok": 12,   "warn": 35},
    "PM1":         {"ok": 10,   "warn": 25},
    "Temperature": {"ok": 26,   "warn": 30},
    "humidite":    {"ok": 60,   "warn": 75},
}

# =============================================================================
# ── PALETTE ───────────────────────────────────────────────────────────────────
# =============================================================================

BG_DARK        = (8,   12,  20)
BG_CARD        = (14,  22,  36)
ACCENT_BLUE    = (0,   140, 255)
ACCENT_CYAN    = (0,   200, 190)
COLOR_OK       = (40,  200, 120)
COLOR_WARN     = (255, 185,  30)
COLOR_ALERT    = (255,  60,  60)
COLOR_UNKNOWN  = (70,   90, 120)
TEXT_PRIMARY   = (230, 240, 255)
TEXT_SECONDARY = (100, 130, 165)
TEXT_DIM       = (45,   65,  90)
SEPARATOR      = (22,   36,  56)

# =============================================================================
# ── LOGGING ───────────────────────────────────────────────────────────────────
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/tmp/cq2a_display.log"),
    ],
)
log = logging.getLogger("CQ2A-Display")

# =============================================================================
# ── UTILITAIRES ───────────────────────────────────────────────────────────────
# =============================================================================

def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def value_color(key: str, value) -> tuple:
    if value is None:
        return COLOR_UNKNOWN
    if key == "AQI":
        if value >= 70: return COLOR_OK
        if value >= 40: return COLOR_WARN
        return COLOR_ALERT
    t = THRESHOLDS.get(key)
    if not t:
        return TEXT_PRIMARY
    if value <= t["ok"]:
        return COLOR_OK
    if value <= t["warn"]:
        return COLOR_WARN
    return COLOR_ALERT


def aqi_label(value) -> str:
    if value is None:  return "N/A"
    if value >= 90:    return "Excellent"
    if value >= 70:    return "Bon"
    if value >= 50:    return "Modéré"
    if value >= 25:    return "Mauvais"
    return "Dangereux"


def compute_aqi(measure: dict) -> float | None:
    """
    =========================================================
    PLACEHOLDER — À REMPLACER PAR LA FORMULE EXACTE
    =========================================================
    Paramètres disponibles dans `measure` :
      measure["Temperature"]  → float (°C)
      measure["humidite"]     → float (% RH)
      measure["CO2"]          → float (ppm)
      measure["COV"]          → float (ppm)
      measure["PM1"]          → float (µg/m³)
      measure["PM2_5"]        → float (µg/m³)
      measure["PM10"]         → float (µg/m³)

    Retourne un float 0-500 ou None si données insuffisantes.

    Exemple :
      co2  = measure.get("CO2")
      pm25 = measure.get("PM2_5")
      if co2 is None: return None
      return round(VOTRE_FORMULE(co2, pm25), 1)
    =========================================================
    """

    temp = measure.get("Temperature")
    humi = measure.get("humidite")
    co2  = measure.get("CO2")
    cov = measure.get("COV")
    pm1 = measure.get("PM1")
    pm2_5 = measure.get("PM2_5")
    pm10 = measure.get("PM10")

    # ── REMPLACER CE BLOC PAR LA VRAIE FORMULE ──
    def sub_index(value, thresholds):
        # thresholds = [(max_val, score), ...] trié du meilleur au pire
        for max_val, score in thresholds:
            if value <= max_val:
                return score
        return 0

    pm1_score   = sub_index(pm1,   [(10,100),(20,80),(35,60),(50,40),(75,20)])
    pm25_score  = sub_index(pm2_5, [(10,100),(25,80),(45,60),(65,40),(150,20)])
    pm10_score  = sub_index(pm10,  [(20,100),(50,80),(80,60),(100,40),(200,20)])
    co2_score   = sub_index(co2,   [(600,100),(1000,80),(1500,60),(2000,40),(5000,20)])
    cov_score   = sub_index(cov,   [(50,100),(150,80),(300,60),(500,40),(1000,20)])

    # Score de base = minimum (pire polluant)
    base = min(pm1_score, pm25_score, pm10_score, co2_score, cov_score)

    # Malus confort (temp & humidité)
    temp_penalty = 0 if 19 <= temp <= 25 else (-3 if 17 <= temp <= 27 else -5)
    humi_penalty = 0 if 40 <= humi <= 60 else (-3 if 30 <= humi <= 70 else -5)

    final = max(0, min(100, base + temp_penalty + humi_penalty))
    return final
    # ────────────────────────────────────────────


# =============================================================================
# ── CLIENT API ────────────────────────────────────────────────────────────────
# =============================================================================

class ApiClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session  = requests.Session()
        self.session.timeout = 10

    def get_screen_config(self, ip: str) -> dict | None:
        """GET /raspberry_pi.php — retourne la config de l'écran pour cette IP."""
        try:
            r = self.session.get(f"{self.base_url}/raspberry_pi.php")
            r.raise_for_status()
            for e in r.json().get("ecrans", []):
                if e.get("Adresse_IP") == ip:
                    log.info(f"Config écran : {e.get('nom_ecran')} (id={e.get('Id_Ecran')})")
                    return e
            log.warning(f"Aucun écran pour l'IP {ip}.")
            return None
        except Exception as exc:
            log.error(f"get_screen_config : {exc}")
            return None

    def set_screen_state(self, screen_id: int, online: bool):
        """PUT /raspberry_pi.php?id=X — met à jour le champ Etat."""
        try:
            self.session.put(
                f"{self.base_url}/raspberry_pi.php?id={screen_id}",
                json={"Etat": online},
            )
            log.info(f"Écran #{screen_id} → {'en ligne' if online else 'hors ligne'}")
        except Exception as exc:
            log.warning(f"set_screen_state : {exc}")

    def get_latest_measure(self) -> dict | None:
        """GET /data.php?limit=1&order=desc — dernière ligne de la table DATA."""
        try:
            r = self.session.get(
                f"{self.base_url}/data.php",
                params={"limit": 1, "order": "desc"},
            )
            r.raise_for_status()
            rows = r.json().get("data", [])
            return rows[0] if rows else None
        except Exception as exc:
            log.error(f"get_latest_measure : {exc}")
            return None

    def get_history(self, limit: int = 20) -> list:
        """GET /data.php?limit=N&order=asc — N dernières mesures pour graphiques."""
        try:
            r = self.session.get(
                f"{self.base_url}/data.php",
                params={"limit": limit, "order": "asc"},
            )
            r.raise_for_status()
            return r.json().get("data", [])
        except Exception as exc:
            log.error(f"get_history : {exc}")
            return []


# =============================================================================
# ── AFFICHAGE PYGAME ──────────────────────────────────────────────────────────
# =============================================================================

class Display:
    """
    Rendu du dashboard sur LCD19WV (1440×900).

    Optimisations performances Pi :
      - Surface de fond pré-rendue (_bg_cache) : grille et halo dessinés
        une seule fois, blittés à chaque frame → supprime ~300 draw.line/frame
      - Arc AQI pré-rendu (_aqi_cache) : reconstruit uniquement quand la
        valeur change, pas à chaque frame
      - Boucle principale à 1 FPS : inutile de redessiner plus vite
      - Pas de transparence SRCALPHA dans la boucle principale (uniquement
        pour les sparklines, une fois par cycle de données)
    """

    # ── Dimensions calées sur 1440×900 ───────────────────────────────────────
    MARGIN     = 16   # marge extérieure
    HEADER_H   = 58   # hauteur bande titre
    FOOTER_H   = 22   # hauteur pied de page
    AQI_W      = 240  # largeur colonne AQI
    AQI_H      = 300  # hauteur bloc AQI
    CARD_H     = 110  # hauteur carte capteur
    HIST_H     = 170  # hauteur panneau historique
    COLS       = 3    # colonnes de cartes

    def __init__(self, width: int, height: int, fullscreen: bool):
        pygame.init()
        pygame.mouse.set_visible(False)

        flags = pygame.FULLSCREEN | pygame.NOFRAME if fullscreen else 0
        self.screen = pygame.display.set_mode((width, height), flags)
        pygame.display.set_caption("CQ2A")

        self.W = width
        self.H = height

        # Polices — tailles adaptées à 1440×900
        self.font_large  = pygame.font.SysFont("dejavusans", 36, bold=True)
        self.font_medium = pygame.font.SysFont("dejavusans", 26, bold=True)
        self.font_small  = pygame.font.SysFont("dejavusans", 18)
        self.font_tiny   = pygame.font.SysFont("dejavusans", 14)
        # Police chiffres — plus grande pour les valeurs capteurs
        self.font_value  = pygame.font.SysFont("dejavusans", 34, bold=True)
        # Police énorme pour la valeur AQI centrale
        self.font_aqi    = pygame.font.SysFont("dejavusans", 62, bold=True)

        self.clock = pygame.time.Clock()

        # Données partagées (thread DataFetcher → thread Display)
        self.measure    : dict | None = None
        self.history    : list        = []
        self.screen_cfg : dict | None = None
        self.last_update: datetime | None = None
        self.fetch_error: bool        = False
        self._lock = threading.Lock()

        # Caches de surfaces pré-rendues
        self._bg_cache   : pygame.Surface | None = None  # fond (grille + halo)
        self._aqi_cache  : pygame.Surface | None = None  # arc AQI
        self._aqi_val_cached = object()  # valeur ayant servi au dernier rendu AQI
        self._hist_cache : pygame.Surface | None = None  # sparklines historique
        self._hist_data_cached = None    # tuple de données ayant servi au rendu

        self._build_bg_cache()

    # ── Cache fond ────────────────────────────────────────────────────────────

    def _build_bg_cache(self):
        """Pré-rend le fond (grille + halo) une seule fois."""
        surf = pygame.Surface((self.W, self.H))
        surf.fill(BG_DARK)

        # Grille subtile
        for x in range(0, self.W, 72):
            pygame.draw.line(surf, (11, 18, 30), (x, 0), (x, self.H))
        for y in range(0, self.H, 72):
            pygame.draw.line(surf, (11, 18, 30), (0, y), (self.W, y))

        # Halo bleu gauche
        for i in range(200):
            a = max(0, 18 - int(i * 18 / 200))
            pygame.draw.line(surf, (max(0, 0 + a//2), max(0, a*3), min(255, a*12)),
                             (i, 0), (i, self.H))

        self._bg_cache = surf

    # ── Cache arc AQI ─────────────────────────────────────────────────────────

    def _build_aqi_arc(self, value) -> pygame.Surface:
        """
        Pré-rend l'arc AQI dans une surface dédiée.
        Reconstruit uniquement si la valeur a changé.
        Utilise pygame.draw.arc (une seule primitive) au lieu de
        centaines de draw.circle → gain majeur sur Pi.
        """
        w, h   = self.AQI_W, self.AQI_H
        surf   = pygame.Surface((w, h))
        surf.fill(BG_CARD)

        cx     = w // 2
        cy     = h // 2 + 14
        radius = min(w, h) // 2 - 18
        thick  = 14   # épaisseur de l'arc (simulée par plusieurs rayons)

        rect_outer = pygame.Rect(cx - radius, cy - radius, radius * 2, radius * 2)

        # Arc de fond (demi-cercle, de π à 2π)
        pygame.draw.arc(surf, (28, 44, 68), rect_outer,
                        math.pi, 2 * math.pi, thick)

        # Arc valeur — même couleur que le texte/label
        filled = min((value or 0) / 100.0, 1.0)
        if filled > 0:
            color = value_color("AQI", value)
            end_angle = math.pi + filled * math.pi
            pygame.draw.arc(surf, color, rect_outer,
                            math.pi, end_angle, thick)

        return surf

    # ── Helpers de dessin ─────────────────────────────────────────────────────

    def _text(self, text, font, color, x, y, anchor="topleft"):
        surf = font.render(str(text), True, color)
        rect = surf.get_rect(**{anchor: (x, y)})
        self.screen.blit(surf, rect)
        return rect

    def _card(self, x, y, w, h, radius=10):
        pygame.draw.rect(self.screen, BG_CARD, (x, y, w, h), border_radius=radius)

    # ── En-tête ───────────────────────────────────────────────────────────────

    def _draw_header(self):
        pygame.draw.rect(self.screen, BG_CARD, (0, 0, self.W, self.HEADER_H))
        pygame.draw.line(self.screen, ACCENT_BLUE,
                         (0, self.HEADER_H), (self.W, self.HEADER_H), 2)

        self._text("CQ2A", self.font_large, ACCENT_BLUE, 28, 10)
        self._text("Contrôle Qualité de l'Air",
                   self.font_small, TEXT_SECONDARY, 130, 20)

        if self.screen_cfg:
            nom = self.screen_cfg.get("nom_ecran", "")
            if nom:
                self._text(f"📍 {nom}", self.font_small, TEXT_SECONDARY,
                           self.W // 2, 19, anchor="midtop")

        self._text(datetime.now().strftime("%H:%M:%S"),
                   self.font_large, TEXT_PRIMARY, self.W - 28, 10, anchor="topright")
        self._text(datetime.now().strftime("%d/%m/%Y"),
                   self.font_small, TEXT_SECONDARY, self.W - 28, 38, anchor="topright")

        if self.last_update:
            color = COLOR_ALERT if self.fetch_error else TEXT_DIM
            label = "⚠ Erreur API" if self.fetch_error \
                    else f"Actualisé {self.last_update.strftime('%H:%M:%S')}"
            self._text(label, self.font_tiny, color,
                       self.W // 2, 42, anchor="midtop")

    # ── Bloc AQI (arc + valeur) ────────────────────────────────────────────────

    def _draw_aqi_block(self, x, y, value):
        # Rebuild le cache arc seulement si la valeur a changé
        if value != self._aqi_val_cached:
            self._aqi_cache      = self._build_aqi_arc(value)
            self._aqi_val_cached = value

        self.screen.blit(self._aqi_cache, (x, y))

        # Label "Indice Qualité Air"
        self._text("Indice Qualité Air", self.font_tiny, TEXT_SECONDARY,
                   x + self.AQI_W // 2, y + 8, anchor="midtop")

        # Valeur numérique centrale
        cx   = x + self.AQI_W // 2
        cy   = y + self.AQI_H // 2 + 14
        color = value_color("AQI", value)
        val_str = str(int(value)) if value is not None else "—"
        self._text(val_str, self.font_aqi, color, cx, cy - 28, anchor="center")

        # Libellé (Excellent / Bon / …)
        self._text(aqi_label(value), self.font_small, color,
                   cx, cy + 30, anchor="center")
        self._text("AQI", self.font_tiny, TEXT_DIM, cx, cy + 52, anchor="center")

    # ── Carte capteur ─────────────────────────────────────────────────────────

    def _draw_sensor_card(self, x, y, w, h, label, value, unit, thr_key, icon=""):
        color = value_color(thr_key, value)
        self._card(x, y, w, h)
        # Barre de couleur gauche
        pygame.draw.rect(self.screen, color, (x, y + 8, 4, h - 16), border_radius=2)
        # Label
        lbl = f"{icon} {label}" if icon else label
        self._text(lbl, self.font_tiny, TEXT_SECONDARY, x + 14, y + 9)
        # Valeur
        val_str = f"{value:.1f}" if isinstance(value, float) else (str(value) if value is not None else "—")
        self._text(val_str, self.font_value, color,
                   x + w // 2, y + h // 2 + 4, anchor="center")
        # Unité
        self._text(unit, self.font_tiny, TEXT_DIM,
                   x + w - 8, y + h - 16, anchor="bottomright")

    # ── Sparkline (historique) ────────────────────────────────────────────────

    def _draw_sparkline(self, surf, x, y, w, h, values, color):
        """Dessine une sparkline dans une surface existante (pas self.screen)."""
        if len(values) < 2:
            return
        vmin = min(values)
        vmax = max(values)
        span = vmax - vmin if vmax != vmin else 1
        pts = [
            (x + int(i / (len(values) - 1) * w),
             y + h - int((v - vmin) / span * h))
            for i, v in enumerate(values)
        ]
        pygame.draw.lines(surf, color, False, pts, 2)
        pygame.draw.circle(surf, color, pts[-1], 4)

    # ── Panneau historique (avec cache) ───────────────────────────────────────

    def _draw_history_panel(self, x, y, w, h, history):
        """
        Pré-rend les sparklines dans un cache Surface.
        Le cache est invalidé uniquement quand les données changent,
        pas à chaque frame.
        """
        # Clé de cache : tuple des timestamps (si données identiques → pas de rendu)
        cache_key = tuple(r.get("Temps") for r in history)
        if cache_key != self._hist_data_cached or self._hist_cache is None:
            surf = pygame.Surface((w, h))
            surf.fill(BG_CARD)

            # Titre
            title_surf = self.font_tiny.render(
                "Historique — 20 dernières mesures", True, TEXT_SECONDARY)
            surf.blit(title_surf, (14, 10))

            metrics = [
                ("CO2",         "CO₂",   "ppm",   ACCENT_BLUE),
                ("Temperature", "Temp.", "°C",    COLOR_WARN),
                ("humidite",    "Hum.",  "%",     ACCENT_CYAN),
                ("PM2_5",       "PM2.5", "µg/m³", COLOR_OK),
            ]
            col_w   = (w - 28) // len(metrics)
            graph_h = h - 58

            for i, (field, label, unit, color) in enumerate(metrics):
                gx     = 14 + i * col_w
                gy     = 34
                values = [r[field] for r in history if r.get(field) is not None]

                lbl_surf = self.font_tiny.render(label, True, TEXT_SECONDARY)
                surf.blit(lbl_surf, lbl_surf.get_rect(midtop=(gx + col_w // 2, gy)))

                if values:
                    self._draw_sparkline(surf, gx, gy + 18, col_w - 6, graph_h - 22, values, color)
                    val_surf = self.font_tiny.render(
                        f"{values[-1]:.0f} {unit}", True, color)
                    surf.blit(val_surf,
                              val_surf.get_rect(midbottom=(gx + col_w // 2, h - 4)))
                else:
                    nd = self.font_small.render("—", True, TEXT_DIM)
                    surf.blit(nd, nd.get_rect(center=(gx + col_w // 2, gy + graph_h // 2)))

                if i > 0:
                    pygame.draw.line(surf, SEPARATOR,
                                     (gx - 2, gy + 14), (gx - 2, gy + graph_h), 1)

            # Bordure arrondie simulée
            pygame.draw.rect(surf, ACCENT_CYAN, (0, 2, 4, 4))

            self._hist_cache      = surf
            self._hist_data_cached = cache_key

        self.screen.blit(self._hist_cache, (x, y))

    # ── Écran d'erreur ────────────────────────────────────────────────────────

    def _draw_error(self, msg: str):
        self.screen.fill(BG_DARK)
        self._text("⚠  ERREUR DE CONNEXION", self.font_large, COLOR_ALERT,
                   self.W // 2, self.H // 2 - 60, anchor="center")
        self._text(msg, self.font_medium, TEXT_SECONDARY,
                   self.W // 2, self.H // 2, anchor="center")
        self._text(
            f"Nouvelle tentative dans {REFRESH_INTERVAL}s  —  "
            f"{datetime.now().strftime('%H:%M:%S')}",
            self.font_small, TEXT_DIM,
            self.W // 2, self.H // 2 + 50, anchor="center",
        )

    # ── Layouts adaptatifs ────────────────────────────────────────────────────

    def _get_layout_mode(self, n_sensors: int, show_aqi: bool, show_hist: bool) -> str:
        """
        Retourne le mode de mise en page en fonction du nombre total
        d'éléments actifs (AQI compté comme 1 élément).

        Modes :
          "solo_aqi"   → uniquement l'AQI, plein écran
          "solo_sensor"→ un seul capteur, plein écran
          "duo"        → 2 éléments (AQI + 1 capteur, ou 2 capteurs)
          "few"        → 3-4 éléments, grandes cartes 2 colonnes
          "normal"     → 5-7 éléments, 3 colonnes standard
          "dense"      → 8+ éléments, 4 colonnes compactes
        """
        total = n_sensors + (1 if show_aqi else 0)
        if total == 0:
            return "normal"
        if show_aqi and total == 1:
            return "solo_aqi"
        if not show_aqi and total == 1:
            return "solo_sensor"
        if total == 2:
            return "duo"
        if total <= 4:
            return "few"
        if total <= 8:
            return "normal"
        return "dense"

    def _layout_params(self, mode: str, show_hist: bool) -> dict:
        """
        Retourne un dict de paramètres de layout selon le mode.
        Clés : cols, card_font_size, label_font_size, aqi_w, aqi_h,
               aqi_font_size, hist_h
        """
        hist_h = self.HIST_H if show_hist else 0
        base = {
            "hist_h":          hist_h,
            "aqi_w":           self.AQI_W,
            "aqi_h":           self.AQI_H,
            "aqi_font_size":   62,
            "card_font_size":  34,
            "label_font_size": 18,
            "cols":            self.COLS,
        }
        if mode == "solo_aqi":
            base.update({"aqi_w": 600, "aqi_h": 680, "aqi_font_size": 180})
        elif mode == "solo_sensor":
            base.update({"card_font_size": 160, "label_font_size": 36, "cols": 1})
        elif mode == "duo":
            base.update({
                "aqi_w": 380, "aqi_h": 500, "aqi_font_size": 110,
                "card_font_size": 90,  "label_font_size": 26, "cols": 1,
            })
        elif mode == "few":
            base.update({
                "aqi_w": 300, "aqi_h": 380, "aqi_font_size": 80,
                "card_font_size": 60,  "label_font_size": 22, "cols": 2,
            })
        elif mode == "dense":
            base.update({
                "aqi_w": 200, "aqi_h": 250, "aqi_font_size": 48,
                "card_font_size": 26,  "label_font_size": 13, "cols": 4,
            })
        return base

    def _make_fonts(self, params: dict) -> dict:
        """Crée les polices selon les paramètres de layout."""
        return {
            "aqi":   pygame.font.SysFont("dejavusans", params["aqi_font_size"],  bold=True),
            "value": pygame.font.SysFont("dejavusans", params["card_font_size"], bold=True),
            "label": pygame.font.SysFont("dejavusans", params["label_font_size"]),
            "tiny":  pygame.font.SysFont("dejavusans", max(12, params["label_font_size"] - 4)),
        }

    # ── Dessin AQI adaptatif ──────────────────────────────────────────────────

    def _draw_aqi_block_adaptive(self, x, y, w, h, value, fonts):
        """Dessine le bloc AQI dans une zone (x,y,w,h) avec polices dynamiques."""
        color = value_color("AQI", value)
        self._card(x, y, w, h)

        cx = x + w // 2
        cy = y + h // 2

        # Arc de fond + arc valeur
        radius  = min(w, h) // 2 - 20
        thick   = max(8, radius // 8)
        rect_a  = pygame.Rect(cx - radius, cy - radius + 10, radius * 2, radius * 2)

        pygame.draw.arc(self.screen, (28, 44, 68), rect_a, math.pi, 2 * math.pi, thick)
        filled = min((value or 0) / 100.0, 1.0)
        if filled > 0:
            pygame.draw.arc(self.screen, color, rect_a,
                            math.pi, math.pi + filled * math.pi, thick)

        # Label titre
        self._text("Indice Qualité Air", fonts["tiny"], TEXT_SECONDARY,
                   cx, y + 8, anchor="midtop")

        # Valeur numérique
        val_str = str(int(value)) if value is not None else "—"
        self._text(val_str, fonts["aqi"], color, cx, cy - 10, anchor="center")

        # Libellé qualitatif
        self._text(aqi_label(value), fonts["label"], color,
                   cx, cy + h // 4, anchor="center")
        self._text("AQI", fonts["tiny"], TEXT_DIM,
                   cx, cy + h // 4 + fonts["label"].get_height() + 4, anchor="center")

    # ── Carte capteur adaptative ──────────────────────────────────────────────

    def _draw_sensor_card_adaptive(self, x, y, w, h, label, value, unit, thr_key, icon, fonts):
        """Dessine une carte capteur avec polices dynamiques."""
        color = value_color(thr_key, value)
        self._card(x, y, w, h)

        bar_w = max(4, w // 60)
        pygame.draw.rect(self.screen, color, (x, y + 8, bar_w, h - 16), border_radius=2)

        lbl = f"{icon} {label}" if icon else label
        pad = bar_w + 8
        self._text(lbl, fonts["tiny"], TEXT_SECONDARY, x + pad, y + 10)

        val_str = (f"{value:.1f}" if isinstance(value, float)
                   else (str(value) if value is not None else "—"))
        self._text(val_str, fonts["value"], color,
                   x + w // 2, y + h // 2 + 4, anchor="center")

        self._text(unit, fonts["tiny"], TEXT_DIM,
                   x + w - 8, y + h - 16, anchor="bottomright")

    # ── Dashboard principal ───────────────────────────────────────────────────

    def draw_dashboard(self):
        with self._lock:
            cfg     = self.screen_cfg or {}
            measure = self.measure
            history = list(self.history)

        # Fond pré-rendu (blit unique, pas de redraw)
        self.screen.blit(self._bg_cache, (0, 0))
        self._draw_header()

        if measure is None:
            self._draw_error("Impossible de récupérer les données depuis l'API PHP.")
            pygame.display.flip()
            return

        # ── Drapeaux d'affichage (table raspberry_pi) ─────────────────────────
        show_aqi  = cfg.get("AQI",         True)
        show_co2  = cfg.get("co2",         True)
        show_cov  = cfg.get("cov",         True)
        show_hum  = cfg.get("humidite",    True)
        show_temp = cfg.get("temperature", True)
        show_pm1  = cfg.get("pm1",         True)
        show_pm25 = cfg.get("pm2.5",       True)
        show_pm10 = cfg.get("pm10",        True)
        show_hist = cfg.get("historique",  False)

        sensors = []
        if show_temp: sensors.append(("Temp.",    "Temperature", "°C",    "Temperature", "🌡"))
        if show_hum:  sensors.append(("Humidité", "humidite",    "% RH",  "humidite",    "💧"))
        if show_co2:  sensors.append(("CO₂",      "CO2",         "ppm",   "CO2",         ""))
        if show_cov:  sensors.append(("COV",      "COV",         "ppm",   "COV",         ""))
        if show_pm25: sensors.append(("PM 2.5",   "PM2_5",       "µg/m³", "PM2_5",       ""))
        if show_pm10: sensors.append(("PM 10",    "PM10",        "µg/m³", "PM10",        ""))
        if show_pm1:  sensors.append(("PM 1",     "PM1",         "µg/m³", "PM1",         ""))

        # ── Calcul du layout adaptatif ────────────────────────────────────────
        mode   = self._get_layout_mode(len(sensors), show_aqi, show_hist)
        params = self._layout_params(mode, show_hist)
        fonts  = self._make_fonts(params)

        M   = self.MARGIN
        TOP = self.HEADER_H + M

        hist_h   = params["hist_h"]
        hist_top = (self.H - self.FOOTER_H - hist_h - M
                    if show_hist else self.H - self.FOOTER_H - M)
        avail_h  = hist_top - TOP - M

        # ── Mode "AQI seul" — plein écran ─────────────────────────────────────
        if mode == "solo_aqi":
            aw = params["aqi_w"]
            ah = params["aqi_h"]
            ax = (self.W - aw) // 2
            ay = TOP + (avail_h - ah) // 2
            self._draw_aqi_block_adaptive(ax, ay, aw, ah, compute_aqi(measure), fonts)
            self._draw_footer(hist_top, show_hist, history, measure, M, hist_h)
            pygame.display.flip()
            return

        # ── Mode "1 capteur seul" — plein écran ───────────────────────────────
        if mode == "solo_sensor" and sensors:
            label, data_key, unit, thr_key, icon = sensors[0]
            pad = 60
            self._draw_sensor_card_adaptive(
                M + pad, TOP + pad,
                self.W - 2 * M - 2 * pad,
                avail_h - 2 * pad,
                label, measure.get(data_key), unit, thr_key, icon, fonts,
            )
            self._draw_footer(hist_top, show_hist, history, measure, M, hist_h)
            pygame.display.flip()
            return

        # ── Layouts multi-éléments ─────────────────────────────────────────────
        aqi_w = params["aqi_w"]
        aqi_h = min(params["aqi_h"], avail_h)
        cols  = params["cols"]

        # Positionnement AQI
        if show_aqi:
            self._draw_aqi_block_adaptive(M, TOP, aqi_w, aqi_h,
                                          compute_aqi(measure), fonts)
            left_edge = M + aqi_w + M
        else:
            left_edge = M

        # Grille de cartes capteurs
        grid_x = left_edge
        grid_w = self.W - grid_x - M

        if sensors:
            rows   = -(-len(sensors) // cols)
            card_w = (grid_w - (cols - 1) * M) // cols
            card_h = min(220, (avail_h - (rows - 1) * M) // max(rows, 1))

            for idx, (label, data_key, unit, thr_key, icon) in enumerate(sensors):
                row = idx // cols
                col = idx % cols
                cx  = grid_x + col * (card_w + M)
                cy  = TOP + row * (card_h + M)
                self._draw_sensor_card_adaptive(
                    cx, cy, card_w, card_h,
                    label, measure.get(data_key), unit, thr_key, icon, fonts,
                )

        # Timestamp mesure
        if measure.get("Temps"):
            self._text(f"Mesure : {measure['Temps']}",
                       self.font_tiny, TEXT_DIM, left_edge, hist_top - 16)

        self._draw_footer(hist_top, show_hist, history, measure, M, hist_h)
        pygame.display.flip()

    def _draw_footer(self, hist_top, show_hist, history, measure, M, hist_h):
        """Dessine le panneau historique et le pied de page."""
        if show_hist and history:
            self._draw_history_panel(
                M, hist_top,
                self.W - 2 * M, hist_h - M,
                history,
            )
        footer_y = self.H - self.FOOTER_H
        pygame.draw.line(self.screen, SEPARATOR, (0, footer_y), (self.W, footer_y), 1)
        self._text("CQ2A", self.font_tiny, TEXT_DIM,
                   self.W // 2, footer_y + 4, anchor="midtop")

    def update(self, measure, history, screen_cfg, fetch_error):
        with self._lock:
            self.measure     = measure
            self.history     = history
            self.screen_cfg  = screen_cfg
            self.fetch_error = fetch_error
            self.last_update = datetime.now()


# =============================================================================
# ── THREAD DE RÉCUPÉRATION DES DONNÉES ───────────────────────────────────────
# =============================================================================

class DataFetcher(threading.Thread):
    def __init__(self, api: ApiClient, display: Display, local_ip: str):
        super().__init__(daemon=True, name="DataFetcher")
        self.api       = api
        self.display   = display
        self.local_ip  = local_ip
        self.screen_id : int | None  = None
        self._cfg      : dict | None = None

    def run(self):
        self._cfg = self.api.get_screen_config(self.local_ip)
        if self._cfg:
            self.screen_id = self._cfg.get("Id_Ecran")
            self.api.set_screen_state(self.screen_id, online=True)
        else:
            log.warning("Pi non enregistré — affichage complet par défaut.")

        while True:
            self._fetch_cycle()
            time.sleep(REFRESH_INTERVAL)

    def _fetch_cycle(self):
        error = False
        try:
            new_cfg = self.api.get_screen_config(self.local_ip)
            if new_cfg:
                self._cfg = new_cfg

            measure = self.api.get_latest_measure()
            if measure is None:
                error = True

            history = self.api.get_history(20)

            self.display.update(measure, history, self._cfg, error)
            log.info(f"OK — {measure.get('Temps') if measure else 'N/A'}")

        except Exception as exc:
            log.error(f"Erreur fetch : {exc}")
            self.display.update(None, [], self._cfg, True)


# =============================================================================
# ── BOUCLE PRINCIPALE ─────────────────────────────────────────────────────────
# =============================================================================

def main():
    local_ip = get_local_ip()
    log.info(f"CQ2A Display  |  IP : {local_ip}  |  {SCREEN_WIDTH}x{SCREEN_HEIGHT}  |  API : {API_BASE_URL}")

    api     = ApiClient(API_BASE_URL)
    display = Display(SCREEN_WIDTH, SCREEN_HEIGHT, FULLSCREEN)
    fetcher = DataFetcher(api, display, local_ip)
    fetcher.start()

    # Attendre le premier fetch (max 8s)
    deadline = time.time() + 8
    while display.last_update is None and time.time() < deadline:
        time.sleep(0.1)

    running = True
    try:
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_q):
                        running = False
                    elif event.key == pygame.K_f:
                        pygame.display.toggle_fullscreen()

            display.draw_dashboard()
            display.clock.tick(1)   # 1 FPS — suffisant, économise le CPU du Pi

    except KeyboardInterrupt:
        log.info("Arrêt.")

    finally:
        if fetcher.screen_id:
            api.set_screen_state(fetcher.screen_id, online=False)
        pygame.quit()
        log.info("Display arrêté.")


if __name__ == "__main__":
    main()
