<?php
require_once 'config.php';

$method = $_SERVER['REQUEST_METHOD'];
$pdo    = getDB();
$id     = isset($_GET['id']) ? (int)$_GET['id'] : null;

// ─────────────────────────────────────────────────────────────────────────────
// GET /compte.php       — Liste tous les comptes
// GET /compte.php?id=1  — Récupère un compte par ID
// ─────────────────────────────────────────────────────────────────────────────
if ($method === 'GET') {
    if ($id !== null) {
        $stmt = $pdo->prepare("SELECT Id_Compte, login, derniere_date_de_connexion, niveau_d_acces FROM Compte WHERE Id_Compte = ?");
        $stmt->execute([$id]);
        $compte = $stmt->fetch();

        if (!$compte) {
            respond(404, ['error' => "Compte #$id introuvable"]);
        }
        respond(200, $compte);
    }

    $stmt = $pdo->query("SELECT Id_Compte, login, derniere_date_de_connexion, niveau_d_acces FROM Compte ORDER BY Id_Compte");
    respond(200, ['comptes' => $stmt->fetchAll()]);
}

// ─────────────────────────────────────────────────────────────────────────────
// POST /compte.php — Créer un nouveau compte
//
// Body JSON :
// {
//   "login":          "nouveau_user",
//   "mot_de_passe":   "monMotDePasse",
//   "niveau_d_acces": 1
// }
// ─────────────────────────────────────────────────────────────────────────────
if ($method === 'POST') {
    $body     = getBody();
    $login    = trim($body['login'] ?? '');
    $password = trim($body['mot_de_passe'] ?? '');
    $niveau   = isset($body['niveau_d_acces']) ? (int)$body['niveau_d_acces'] : 1;

    if (empty($login) || empty($password)) {
        respond(400, ['error' => 'login et mot_de_passe sont requis']);
    }

    // Vérifier unicité du login
    $check = $pdo->prepare("SELECT Id_Compte FROM Compte WHERE login = ?");
    $check->execute([$login]);
    if ($check->fetch()) {
        respond(409, ['error' => "Le login '$login' est déjà utilisé"]);
    }

    $stmt = $pdo->prepare("INSERT INTO Compte (login, mot_de_passe, niveau_d_acces) VALUES (?, ?, ?)");
    $stmt->execute([$login, $password, $niveau]);

    respond(201, [
        'message'        => 'Compte créé',
        'Id_Compte'      => (int)$pdo->lastInsertId(),
        'login'          => $login,
        'niveau_d_acces' => $niveau,
    ]);
}

// ─────────────────────────────────────────────────────────────────────────────
// PUT /compte.php?id=1 — Modifier un compte existant
//
// Body JSON (tous les champs sont optionnels) :
// {
//   "login":          "nouveau_login",
//   "mot_de_passe":   "nouveau_mdp",
//   "niveau_d_acces": 2
// }
// ─────────────────────────────────────────────────────────────────────────────
if ($method === 'PUT') {
    if ($id === null) {
        respond(400, ['error' => 'Paramètre ?id= requis']);
    }

    $check = $pdo->prepare("SELECT Id_Compte FROM Compte WHERE Id_Compte = ?");
    $check->execute([$id]);
    if (!$check->fetch()) {
        respond(404, ['error' => "Compte #$id introuvable"]);
    }

    $body   = getBody();
    $fields = [];
    $params = [];

    if (!empty($body['login'])) {
        $loginCheck = $pdo->prepare("SELECT Id_Compte FROM Compte WHERE login = ? AND Id_Compte != ?");
        $loginCheck->execute([$body['login'], $id]);
        if ($loginCheck->fetch()) {
            respond(409, ['error' => "Le login '{$body['login']}' est déjà utilisé"]);
        }
        $fields[] = 'login = ?';
        $params[] = trim($body['login']);
    }

    if (!empty($body['mot_de_passe'])) {
        $fields[] = 'mot_de_passe = ?';
        $params[] = trim($body['mot_de_passe']);
    }

    if (isset($body['niveau_d_acces'])) {
        $fields[] = 'niveau_d_acces = ?';
        $params[] = (int)$body['niveau_d_acces'];
    }

    if (isset($body['derniere_date_de_connexion'])) {
        $fields[] = 'derniere_date_de_connexion = ?';
        $params[] = $body['derniere_date_de_connexion'];
    }

    if (empty($fields)) {
        respond(400, ['error' => 'Aucun champ à modifier fourni']);
    }

    $params[] = $id;
    $stmt = $pdo->prepare("UPDATE Compte SET " . implode(', ', $fields) . " WHERE Id_Compte = ?");
    $stmt->execute($params);

    respond(200, ['message' => "Compte #$id mis à jour"]);
}

// ─────────────────────────────────────────────────────────────────────────────
// DELETE /compte.php?id=1 — Supprimer un compte
// ─────────────────────────────────────────────────────────────────────────────
if ($method === 'DELETE') {
    if ($id === null) {
        respond(400, ['error' => 'Paramètre ?id= requis']);
    }

    $check = $pdo->prepare("SELECT Id_Compte FROM Compte WHERE Id_Compte = ?");
    $check->execute([$id]);
    if (!$check->fetch()) {
        respond(404, ['error' => "Compte #$id introuvable"]);
    }

    $stmt = $pdo->prepare("DELETE FROM Compte WHERE Id_Compte = ?");
    $stmt->execute([$id]);

    respond(200, ['message' => "Compte #$id supprimé"]);
}

respond(405, ['error' => 'Méthode non autorisée']);
