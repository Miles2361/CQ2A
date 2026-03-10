<?php
require_once 'config.php';

$method = $_SERVER['REQUEST_METHOD'];
$pdo    = getDB();

// ─────────────────────────────────────────────────────────────────────────────
// GET /data.php — Récupérer les mesures avec filtres optionnels
//
// Paramètres GET disponibles :
//   ?debut=2026-02-26 08:00:00   filtre date début
//   ?fin=2026-02-26 12:00:00     filtre date fin
//   ?limit=50                    nombre max de résultats (défaut 100, max 1000)
//   ?offset=0                    pagination
//   ?order=asc|desc              ordre chronologique (défaut desc)
// ─────────────────────────────────────────────────────────────────────────────
if ($method === 'GET') {
    $where  = [];
    $params = [];

    if (!empty($_GET['debut'])) {
        $where[]  = 'Temps >= ?';
        $params[] = $_GET['debut'];
    }

    if (!empty($_GET['fin'])) {
        $where[]  = 'Temps <= ?';
        $params[] = $_GET['fin'];
    }

    $whereClause = count($where) > 0 ? 'WHERE ' . implode(' AND ', $where) : '';
    $order       = strtolower($_GET['order'] ?? 'desc') === 'asc' ? 'ASC' : 'DESC';
    $limit       = max(1, min(1000, (int)($_GET['limit']  ?? 100)));
    $offset      = max(0, (int)($_GET['offset'] ?? 0));

    $stmt = $pdo->prepare("SELECT * FROM DATA $whereClause ORDER BY Temps $order LIMIT $limit OFFSET $offset");
    $stmt->execute($params);
    $rows = $stmt->fetchAll();

    $countStmt = $pdo->prepare("SELECT COUNT(*) as total FROM DATA $whereClause");
    $countStmt->execute($params);
    $total = $countStmt->fetch()['total'];

    respond(200, [
        'total'  => (int)$total,
        'limit'  => $limit,
        'offset' => $offset,
        'data'   => $rows,
    ]);
}

// ─────────────────────────────────────────────────────────────────────────────
// POST /data.php — Insérer une nouvelle mesure
// ⚠️  Table temporelle : INSERT uniquement, pas de PUT ni DELETE
//
// Body JSON :
// {
//   "Temps":       "2026-02-26 13:00:00",  (optionnel → NOW() par défaut)
//   "Temperature": 22.5,
//   "humidite":    48.0,
//   "CO2":         430,
//   "COV":         0.4,
//   "PM10":        14,
//   "PM2_5":       9,
//   "PM1":         6
// }
// ─────────────────────────────────────────────────────────────────────────────
if ($method === 'POST') {
    $body  = getBody();
    $temps = !empty($body['Temps']) ? $body['Temps'] : date('Y-m-d H:i:s');

    $temperature = isset($body['Temperature']) ? (float)$body['Temperature'] : null;
    $humidite    = isset($body['humidite'])    ? (float)$body['humidite']    : null;
    $co2         = isset($body['CO2'])         ? (float)$body['CO2']         : null;
    $cov         = isset($body['COV'])         ? (float)$body['COV']         : null;
    $pm10        = isset($body['PM10'])        ? (float)$body['PM10']        : null;
    $pm2_5       = isset($body['PM2_5'])       ? (float)$body['PM2_5']       : null;
    $pm1         = isset($body['PM1'])         ? (float)$body['PM1']         : null;

    $stmt = $pdo->prepare("
        INSERT INTO DATA (Temps, Temperature, humidite, CO2, COV, PM10, PM2_5, PM1)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ");
    $stmt->execute([$temps, $temperature, $humidite, $co2, $cov, $pm10, $pm2_5, $pm1]);

    respond(201, [
        'message' => 'Mesure enregistrée',
        'Id_DATA' => (int)$pdo->lastInsertId(),
        'Temps'   => $temps,
    ]);
}

respond(405, ['error' => 'Méthode non autorisée. Table temporelle : GET et POST uniquement (pas de PUT ni DELETE)']);
