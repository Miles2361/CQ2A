# CQ2A — Contrôleur d'écran Raspberry Pi

Script Python d'affichage plein écran (HDMI → DisplayPort) pour le dashboard
de qualité de l'air CQ2A.

---

## Prérequis

- Raspberry Pi OS (Bullseye ou Bookworm)
- Python 3.10+
- Écran HDMI (via adaptateur DP)
- Accès réseau vers le serveur hébergeant l'API PHP

---

## Installation

```bash
# 1. Copier le script
cp display_controller.py /home/pi/

# 2. Installer les dépendances
pip install pygame requests

# 3. Éditer la configuration dans le script
nano /home/pi/display_controller.py
```

### Paramètres à configurer (début du fichier)

| Variable          | Description                                 | Exemple                        |
|-------------------|---------------------------------------------|-------------------------------|
| `API_BASE_URL`    | URL de base de votre API PHP                | `http://192.168.1.50/CQ2A/API`|
| `REFRESH_INTERVAL`| Secondes entre chaque actualisation        | `30`                          |
| `SCREEN_WIDTH`    | Résolution horizontale de l'écran          | `1920`                        |
| `SCREEN_HEIGHT`   | Résolution verticale de l'écran            | `1080`                        |
| `FULLSCREEN`      | Plein écran (`True`) ou fenêtré (`False`)  | `True`                        |

---

## Enregistrer votre Raspberry Pi dans la BDD

Avant le premier lancement, ajoutez votre Pi dans la table `raspberry_pi`
via l'API (adapter l'IP et les capteurs à activer) :

```bash
curl -X POST http://VOTRE_API/raspberry_pi.php \
  -H "Content-Type: application/json" \
  -d '{
    "Adresse_IP":     "192.168.1.XXX",
    "nom_ecran":      "RPI_MonEcran",
    "niveau_d_acces": 1,
    "Disposition":    0,
    "Etat":           false,
    "AQI":            true,
    "co2":            true,
    "cov":            true,
    "humidite":       true,
    "temperature":    true,
    "pm1":            true,
    "pm2.5":          true,
    "pm10":           true,
    "historique":     true
  }'
```

Le script détecte automatiquement son IP locale et récupère sa configuration
depuis l'API au démarrage.

---

## Lancement manuel (test)

```bash
# Avec affichage graphique actif
DISPLAY=:0 python3 /home/pi/display_controller.py

# En mode fenêtré (debug — modifier FULLSCREEN=False dans le script)
python3 /home/pi/display_controller.py
```

### Raccourcis clavier
| Touche    | Action                          |
|-----------|---------------------------------|
| `ESC` / `Q` | Quitter                       |
| `F`       | Basculer plein écran / fenêtré  |
| `R`       | Forcer actualisation            |

---

## Lancement automatique au démarrage (systemd)

```bash
sudo nano /etc/systemd/system/cq2a-display.service
```

```ini
[Unit]
Description=CQ2A Display Controller
After=network.target graphical.target

[Service]
User=pi
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/pi/.Xauthority
WorkingDirectory=/home/pi
ExecStart=/usr/bin/python3 /home/pi/display_controller.py
Restart=always
RestartSec=10

[Install]
WantedBy=graphical.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable cq2a-display
sudo systemctl start cq2a-display

# Voir les logs
sudo journalctl -u cq2a-display -f
```

---

## Ce que fait le script

1. **Détecte son IP locale** automatiquement
2. **Interroge `raspberry_pi.php`** pour trouver sa config (capteurs activés, disposition)
3. **Signale son état `Etat=true`** à l'API (écran en ligne)
4. **Interroge `data.php`** toutes les 30s pour la dernière mesure
5. **Calcule un AQI simplifié** à partir du CO₂, PM2.5 et COV
6. **Affiche un dashboard plein écran** avec :
   - Heure/date en temps réel
   - Jauge AQI avec arc coloré (vert → rouge)
   - Cartes capteurs (couleur selon seuils)
   - Mini graphiques d'historique (20 dernières mesures)
7. **Signale `Etat=false`** à l'API à l'arrêt propre

### Couleurs des indicateurs
| Couleur | Signification |
|---------|--------------|
| 🟢 Vert  | Valeur normale |
| 🟡 Jaune | Valeur à surveiller |
| 🔴 Rouge | Valeur critique |
| ⚪ Gris  | Donnée indisponible |

---

## Logs

```bash
# En temps réel
tail -f /tmp/cq2a_display.log
```

---

## Dépannage

**L'écran reste noir**
```bash
# Vérifier que le display est disponible
echo $DISPLAY   # doit afficher :0
xrandr          # liste les sorties vidéo
```

**Erreur "cannot connect to X server"**
```bash
export DISPLAY=:0
export XAUTHORITY=/home/pi/.Xauthority
python3 /home/pi/display_controller.py
```

**L'API ne répond pas**
- Vérifier que `API_BASE_URL` est correct
- Tester manuellement : `curl http://VOTRE_API/data.php?limit=1`
- Vérifier le réseau : `ping VOTRE_SERVEUR`
