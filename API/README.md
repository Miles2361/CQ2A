# 📡 API PHP — Documentation

## Structure des fichiers
```
api/
├── config.php        # Connexion BDD + fonctions utilitaires
├── data.php          # Mesures capteurs (table temporelle)
├── compte.php        # Gestion des comptes
└── raspberry_pi.php  # Configuration des écrans
```

---

## ⚙️ Configuration
Dans `config.php`, modifier :
```php
define('DB_HOST', 'localhost');
define('DB_NAME', 'nom_de_votre_bdd');
define('DB_USER', 'votre_utilisateur');
define('DB_PASS', 'votre_mot_de_passe');
```

---

## 📊 data.php — Mesures capteurs (table temporelle)
> ⚠️ Table en **append-only** : GET et POST uniquement. Pas de PUT ni DELETE.

| Méthode | URL | Description |
|---------|-----|-------------|
| GET  | `/data.php`                   | Liste les mesures |
| GET  | `/data.php?debut=...&fin=...`  | Filtrer par période |
| POST | `/data.php`                   | Ajouter une mesure |

### GET — Filtres disponibles
| Paramètre | Exemple               | Description |
|-----------|-----------------------|-------------|
| `debut`   | `2026-02-26 08:00:00` | Date de début |
| `fin`     | `2026-02-26 12:00:00` | Date de fin |
| `limit`   | `50`                  | Nb résultats (défaut 100, max 1000) |
| `offset`  | `0`                   | Pagination |
| `order`   | `asc` ou `desc`       | Ordre chronologique (défaut desc) |

```
GET /data.php?debut=2026-02-26 08:00:00&fin=2026-02-26 12:00:00&limit=10
```

### POST — Insérer une mesure
```json
{
  "Temps":       "2026-02-26 13:00:00",
  "Temperature": 22.5,
  "humidite":    48.0,
  "CO2":         430,
  "COV":         0.4,
  "PM10":        14,
  "PM2_5":       9,
  "PM1":         6
}
```
> `Temps` est optionnel (NOW() utilisé par défaut). Tous les capteurs sont optionnels (NULL si absent).

---

## 👤 compte.php — Gestion des comptes

| Méthode | URL               | Description |
|---------|-------------------|-------------|
| GET    | `/compte.php`      | Liste tous les comptes |
| GET    | `/compte.php?id=1` | Détail d'un compte |
| POST   | `/compte.php`      | Créer un compte |
| PUT    | `/compte.php?id=1` | Modifier un compte |
| DELETE | `/compte.php?id=1` | Supprimer un compte |

### POST — Créer un compte
```json
{
  "login":          "nouveau_user",
  "mot_de_passe":   "monMotDePasse",
  "niveau_d_acces": 1
}
```

### PUT — Modifier (tous les champs sont optionnels)
```json
{
  "login":                    "nouveau_login",
  "mot_de_passe":             "nouveau_mdp",
  "niveau_d_acces":           2,
  "derniere_date_de_connexion": "2026-03-10 14:00:00"
}
```

---

## 🖥️ raspberry_pi.php — Configuration des écrans

| Méthode | URL                      | Description |
|---------|--------------------------|-------------|
| GET    | `/raspberry_pi.php`       | Liste tous les écrans |
| GET    | `/raspberry_pi.php?id=1`  | Détail d'un écran |
| POST   | `/raspberry_pi.php`       | Ajouter un écran |
| PUT    | `/raspberry_pi.php?id=1`  | Modifier un écran |
| DELETE | `/raspberry_pi.php?id=1`  | Supprimer un écran |

### POST — Ajouter un écran
```json
{
  "Adresse_IP":     "192.168.1.20",
  "nom_ecran":      "RPI_Cuisine",
  "niveau_d_acces": 1,
  "Disposition":    0,
  "Etat":           false,
  "AQI":            true,
  "co2":            true,
  "cov":            false,
  "humidite":       true,
  "temperature":    true,
  "pm1":            false,
  "pm2.5":          false,
  "pm10":           false,
  "historique":     true
}
```

### PUT — Modifier un écran (tous les champs sont optionnels)
```json
{
  "nom_ecran":   "RPI_Cuisine_V2",
  "Etat":        true,
  "temperature": true
}
```
