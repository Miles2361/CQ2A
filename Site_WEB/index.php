<?php
require 'config.php';      

// Dernière donnée
$stmt = $pdo->query("SELECT * FROM DATA ORDER BY Temps DESC LIMIT 1");        // Exécute une requête SQL pour récupérer la dernière ligne enregistrée
$data = $stmt->fetch();                                                       // Récupère le résultat sous forme de tableau associatif

// Calcul simple d'un score qualité air (basé sur PM2.5)
$aqi = round(($data['PM2_5'] / 35) * 100); // Calcule un indice qualité air en pourcentage basé sur une valeur max de 35
$aqi_status = "Bon"; // Définit par défaut le statut comme "Bon"
if ($aqi > 50) $aqi_status = "Modéré"; // Si l'indice dépasse 50 → statut Modéré
if ($aqi > 100) $aqi_status = "Mauvais"; // Si l'indice dépasse 100 → statut Mauvais
?>

<!DOCTYPE html>
<html> 
<head>
    <meta charset="UTF-8">
    <title>Dashboard Air</title> 
    <link rel="stylesheet" href="style.css">
</head>

<body> 


<div class="top-menu"> <!-- Barre de navigation principale -->
    
    <a href="index.php" class="<?= basename($_SERVER['PHP_SELF']) == 'index.php' ? 'active' : '' ?>"> 📊 Tableau de bord </a>                                        <!-- Lien vers la page principale avec classe active si on est dessus -->
    <a href="historique.php" class="<?= basename($_SERVER['PHP_SELF']) == 'historique.php' ? 'active' : '' ?>"> 📈 Historique</a>                                    <!-- Lien vers la page historique avec activation automatique -->
    <a href="#">ℹ À propos</a>                                                                                                                                        <!-- Lien simple (non fonctionnel pour l’instant) -->

</div>

<div class="container"> <!-- Conteneur principal du dashboard -->

    <!-- SCORE AIR -->
    <div class="aqi-card">                                          <!-- Carte principale affichant l'indice -->
        <h1><?= $aqi ?></h1>                                        <!-- Affiche la valeur calculée de l'indice -->
        <span class="badge"><?= $aqi_status ?></span>               <!-- Affiche le statut (Bon, Modéré, Mauvais) -->
        <p>La qualité de l'air est acceptable.</p>                  <!-- Texte descriptif -->
        <small>Dernière mise à jour : <?= $data['Temps'] ?></small> <!-- Affiche la date de la dernière mesure -->
    </div>

    <!-- CARTES -->
    <div class="cards">                                             <!-- Conteneur des cartes secondaires -->

        <div class="card">                                          <!-- Carte température -->
            <h3>🌡 Température</h3>                                 
            <p class="value"><?= $data['Temperature'] ?>°C</p>      <!-- Affiche la température -->
        </div>

        <div class="card">                                          <!-- Carte humidité -->
            <h3>💧 Humidité</h3> 
            <p class="value"><?= $data['humidite'] ?>%</p>          <!-- Affiche le taux d'humidité -->
        </div>

        <div class="card active">                                   <!-- Carte ventilation mise en avant -->
            <h3>🌀 Système Ventilation</h3>
            <p class="value">ACTIF <span class="auto">AUTO</span></p> <!-- Indique que la ventilation est active -->
        </div>

    </div> 
    <!-- POLLUANTS -->
    <div class="polluants">                                         <!-- Section des polluants -->
        <h2>⚠ Niveaux de Polluants</h2> 

        <?php
        function progress($value, $max) {                           // Fonction qui calcule le pourcentage de remplissage
            $percent = ($value / $max) * 100;                       // Calcule le pourcentage par rapport à la valeur maximale
            return min($percent, 100);                              // Empêche de dépasser 100%
        }
        ?>
        <div class="polluant"> <!-- Bloc PM1 -->
            <label>PM1 (<?= $data['PM1'] ?> µg/m³)</label> <!-- Affiche valeur PM1 -->
            <div class="bar"> <!-- Barre de fond -->
                <div style="width:<?= progress($data['PM1'],15) ?>%"></div> <!-- Barre remplie dynamiquement -->
            </div>
        </div>

        <div class="polluant"> <!-- Bloc PM2.5 -->
            <label>PM2.5 (<?= $data['PM2_5'] ?> µg/m³)</label>
            <div class="bar">
                <div style="width:<?= progress($data['PM2_5'],35) ?>%"></div>
            </div>
        </div>

        <div class="polluant"> <!-- Bloc PM10 -->
            <label>PM10 (<?= $data['PM10'] ?> µg/m³)</label>
            <div class="bar warning"> <!-- Classe warning pour couleur différente -->
                <div style="width:<?= progress($data['PM10'],150) ?>%"></div>
            </div>
        </div>

        <div class="polluant"> <!-- Bloc CO2 -->
            <label>CO2 (<?= $data['CO2'] ?> ppm)</label>
            <div class="bar">
                <div style="width:<?= progress($data['CO2'],1000) ?>%"></div>
            </div>
        </div>

        <div class="polluant"> <!-- Bloc COV -->
            <label>COV (<?= $data['COV'] ?> µg/m³)</label>
            <div class="bar">
                <div style="width:<?= progress($data['COV'],500) ?>%"></div>
            </div>

         
        </div>

    </div> 

</div> 

</body> 
</html> 