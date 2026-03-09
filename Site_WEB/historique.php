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
    <link rel="stylesheet" href="style.css">
</head>
<body>

<div class="container">

<?php include 'menu.php'; ?>

<div class="top-menu">
    <a href="index.php">📊 Tableau de bord</a>
    <a href="historique.php" class="active">📈 Historique</a>
    <a href="About.php">ℹ À propos</a>
</div>

<h1>📈 Historique des données</h1>

<div class="polluants">
    <table class="history-table">             
        <tr>
            <th>Date</th>
            <th>Temp</th>
            <th>Humidité</th>
            <th>CO2</th>
            <th>PM1</th>
            <th>PM2.5</th>
            <th>PM10</th>
        </tr>

        <?php foreach($datas as $row): ?>
        <tr>
            <td><?= $row['Temps'] ?></td>
            <td><?= $row['Temperature'] ?>°C</td>
            <td><?= $row['humidite'] ?>%</td>
            <td><?= $row['CO2'] ?> ppm</td>
            <td><?= $row['PM1'] ?></td>
            <td><?= $row['PM2_5'] ?></td>
            <td><?= $row['PM10'] ?></td>
        </tr>
        <?php endforeach; ?>    <!--// Boucle pour afficher chaque ligne de données dans le tableau -->

    </table>
</div>

</div>
</body>
</html>