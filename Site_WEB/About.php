<?php
require 'config.php';

$stmt = $pdo->query("SELECT * FROM DATA ORDER BY Temps DESC");
$datas = $stmt->fetchAll();
?>

<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Historique</title>
    <link rel="stylesheet" href="style_2.css">
</head>
<body>

<div class="container">

<?php include 'menu.php'; ?>

<div class="top-menu">
    <a href="index.php">📊 Tableau de bord</a>            <!-- Lien vers la page principale -->                 
    <a href="historique.php">📈 Historique</a>            <!-- Lien vers la page historique avec activation automatique -->
    <a href="About.php" class="active">ℹ À propos</a>      <!-- "class="active""  -----permet le rond blanc quand on est sur la page (de savoir dans quelle page on est) --> 
</div>

<h1>Surveillance de l'Air</h1>

</div>
</body>
</html>