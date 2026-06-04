<?php
'''
Titre : CQ2A/API/config.php
Nom : Hammouda
Prénom : Rayan
Date : 05/05/2026
'''
// ─── Configuration de la base de données ─────────────────────────────────────
define('DB_HOST', 'localhost');
define('DB_NAME', 'CQ2A');
define('DB_USER', 'cq2a_api');
define('DB_PASS', 'eclipseCQ2A2026');
define('DB_CHARSET', 'utf8mb4');

function getDB(): PDO {
    static $pdo = null;
    if ($pdo === null) {
        $dsn = "mysql:host=" . DB_HOST . ";dbname=" . DB_NAME . ";charset=" . DB_CHARSET;
        $options = [
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES   => false,
        ];
        try {
            $pdo = new PDO($dsn, DB_USER, DB_PASS, $options);
        } catch (PDOException $e) {
            http_response_code(500);
            die(json_encode(['error' => 'Connexion BDD impossible : ' . $e->getMessage()]));
        }
    }
    return $pdo;
}

// ─── Headers CORS et JSON ─────────────────────────────────────────────────────
header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit();
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function getBody(): array {
    $raw = file_get_contents('php://input');
    if (!is_string($raw)) {
        return [];
    }

    $raw = trim($raw);
    if ($raw === '') {
        return $_POST ?? [];
    }

    // Retire un éventuel BOM UTF-8 en début de payload.
    if (strncmp($raw, "\xEF\xBB\xBF", 3) === 0) {
        $raw = substr($raw, 3);
    }

    $data = json_decode($raw, true);
    if (is_array($data)) {
        return $data;
    }

    // Fallback pour body urlencoded envoyé sans JSON valide.
    $parsed = [];
    parse_str($raw, $parsed);
    if (is_array($parsed) && !empty($parsed)) {
        return $parsed;
    }

    return $_POST ?? [];
}

function respond(int $code, array $data): void {
    http_response_code($code);
    echo json_encode($data, JSON_UNESCAPED_UNICODE);
    exit();
}
