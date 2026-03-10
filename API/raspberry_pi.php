<?php
require_once 'config.php';

$method     = $_SERVER['REQUEST_METHOD'];
$pdo        = getDB();
$id         = isset($_GET['id']) ? (int)$_GET['id'] : null;
$BOOL_FIELDS = ['Etat', 'AQI', 'co2', 'cov', 'humidite', 'temperature', 'pm1', 'pm2.5', 'pm10', 'historique'];

// Convertit les champs bit(1) en booléens lisibles
function formatEcran(array $row, array $boolFields): array {
    foreach ($boolFields as $field) {
        if (array_key_exists($field, $row)) {
            $row[$field] = (bool)(int)$row[$field];
        }
    }
    return $row;
}

// ─────────────────────────────────────────────────────────────────────────────
// GET /raspberry_pi.php        — Liste tous les écrans
// GET /raspberry_pi.php?id=1   — Récupère un écran par ID
// ─────────────────────────────────────────────────────────────────────────────
if ($method === 'GET') {
    if ($id !== null) {
        $stmt = $pdo->prepare("SELECT * FROM raspberry_pi WHERE Id_Ecran = ?");
        $stmt->execute([$id]);
        $ecran = $stmt->fetch();

        if (!$ecran) {
            respond(404, ['error' => "Écran #$id introuvable"]);
        }
        respond(200, formatEcran($ecran, $BOOL_FIELDS));
    }

    $stmt = $pdo->query("SELECT * FROM raspberry_pi ORDER BY Id_Ecran");
    $rows = array_map(fn($r) => formatEcran($r, $BOOL_FIELDS), $stmt->fetchAll());
    respond(200, ['ecrans' => $rows, 'total' => count($rows)]);
}

// ─────────────────────────────────────────────────────────────────────────────
// POST /raspberry_pi.php — Ajouter un écran
//
// Body JSON :
// {
//   "Adresse_IP":     "192.168.1.20",
//   "nom_ecran":      "RPI_Cuisine",
//   "niveau_d_acces": 1,
//   "Disposition":    0,
//   "Etat":           false,
//   "AQI":            true,
//   "co2":            true,
//   "cov":            false,
//   "humidite":       true,
//   "temperature":    true,
//   "pm1":            false,
//   "pm2.5":          false,
//   "pm10":           false,
//   "historique":     true
// }
// ─────────────────────────────────────────────────────────────────────────────
if ($method === 'POST') {
    $body = getBody();
    $ip   = trim($body['Adresse_IP'] ?? '');
    $nom  = trim($body['nom_ecran'] ?? '');

    if (empty($ip)) {
        respond(400, ['error' => 'Adresse_IP est requise']);
    }

    $niveau = isset($body['niveau_d_acces']) ? (int)$body['niveau_d_acces'] : 1;
    $dispo  = isset($body['Disposition'])    ? (int)$body['Disposition']    : 0;
    $b      = fn($key) => isset($body[$key]) ? ($body[$key] ? 1 : 0) : 0;

    $stmt = $pdo->prepare("
        INSERT INTO raspberry_pi
            (Adresse_IP, nom_ecran, niveau_d_acces, Disposition,
             Etat, AQI, co2, cov, humidite, temperature, pm1, `pm2.5`, pm10, historique)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ");
    $stmt->execute([
        $ip, $nom, $niveau, $dispo,
        $b('Etat'), $b('AQI'), $b('co2'), $b('cov'),
        $b('humidite'), $b('temperature'), $b('pm1'), $b('pm2.5'), $b('pm10'), $b('historique')
    ]);

    respond(201, [
        'message'    => 'Écran ajouté',
        'Id_Ecran'   => (int)$pdo->lastInsertId(),
        'nom_ecran'  => $nom,
        'Adresse_IP' => $ip,
    ]);
}

// ─────────────────────────────────────────────────────────────────────────────
// PUT /raspberry_pi.php?id=1 — Modifier un écran (tous les champs sont optionnels)
// ─────────────────────────────────────────────────────────────────────────────
if ($method === 'PUT') {
    if ($id === null) {
        respond(400, ['error' => 'Paramètre ?id= requis']);
    }

    $check = $pdo->prepare("SELECT Id_Ecran FROM raspberry_pi WHERE Id_Ecran = ?");
    $check->execute([$id]);
    if (!$check->fetch()) {
        respond(404, ['error' => "Écran #$id introuvable"]);
    }

    $body   = getBody();
    $fields = [];
    $params = [];

    foreach (['Adresse_IP', 'nom_ecran'] as $f) {
        if (isset($body[$f])) {
            $fields[] = "`$f` = ?";
            $params[] = trim($body[$f]);
        }
    }

    foreach (['niveau_d_acces', 'Disposition'] as $f) {
        if (isset($body[$f])) {
            $fields[] = "`$f` = ?";
            $params[] = (int)$body[$f];
        }
    }

    foreach (['Etat', 'AQI', 'co2', 'cov', 'humidite', 'temperature', 'pm1', 'pm2.5', 'pm10', 'historique'] as $f) {
        if (isset($body[$f])) {
            $fields[] = "`$f` = ?";
            $params[] = $body[$f] ? 1 : 0;
        }
    }

    if (empty($fields)) {
        respond(400, ['error' => 'Aucun champ à modifier fourni']);
    }

    $params[] = $id;
    $stmt = $pdo->prepare("UPDATE raspberry_pi SET " . implode(', ', $fields) . " WHERE Id_Ecran = ?");
    $stmt->execute($params);

    respond(200, ['message' => "Écran #$id mis à jour"]);
}

// ─────────────────────────────────────────────────────────────────────────────
// DELETE /raspberry_pi.php?id=1 — Supprimer un écran
// ─────────────────────────────────────────────────────────────────────────────
if ($method === 'DELETE') {
    if ($id === null) {
        respond(400, ['error' => 'Paramètre ?id= requis']);
    }

    $check = $pdo->prepare("SELECT Id_Ecran FROM raspberry_pi WHERE Id_Ecran = ?");
    $check->execute([$id]);
    if (!$check->fetch()) {
        respond(404, ['error' => "Écran #$id introuvable"]);
    }

    $stmt = $pdo->prepare("DELETE FROM raspberry_pi WHERE Id_Ecran = ?");
    $stmt->execute([$id]);

    respond(200, ['message' => "Écran #$id supprimé"]);
}

respond(405, ['error' => 'Méthode non autorisée']);
