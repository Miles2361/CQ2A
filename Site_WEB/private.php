<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Contrôle des Écrans</title>
<link rel="stylesheet" href="private_css.css">
<meta name="viewport" content="width=device-width, initial-scale=1">
</head>

<body>

<header class="topbar">
    <div class="title">
        <div class="icon">🖥️</div>
        <div>
            <h1>Contrôle des Écrans</h1>
            <p>Système de gestion à distance</p>
        </div>
    </div>

    <div class="status">
        <span class="dot"></span>
        3 écrans en ligne
    </div>
</header>


<div class="tabs">
    <button class="tab active">⚙️ Panneau de Contrôle</button>
    <button class="tab">🖥️ Aperçu des Écrans</button>
</div>


<section class="screens">

<div class="screen-card">
    <div class="card-header">
        <div>
            <h3>Écran Hall Principal</h3>
            <p>Bâtiment A - Entrée</p>
        </div>
        <span class="badge online">En ligne</span>
    </div>

    <div class="info">
        <div><span>Disposition:</span> Tableau de bord</div>
        <div><span>Luminosité:</span> 80%</div>
        <div><span>Actualisation:</span> 30s</div>
    </div>

    <div class="actions">
        <button class="refresh">⟳ Actualiser</button>
        <button class="settings">⚙</button>
        <button class="power">⏻</button>
    </div>
</div>


<div class="screen-card">
    <div class="card-header">
        <div>
            <h3>Écran Laboratoire</h3>
            <p>Bâtiment B - Lab 204</p>
        </div>
        <span class="badge online">En ligne</span>
    </div>

    <div class="info">
        <div><span>Disposition:</span> AQI plein écran</div>
        <div><span>Luminosité:</span> 70%</div>
        <div><span>Actualisation:</span> 60s</div>
    </div>

    <div class="actions">
        <button class="refresh">⟳ Actualiser</button>
        <button class="settings">⚙</button>
        <button class="power">⏻</button>
    </div>
</div>


<div class="screen-card">
    <div class="card-header">
        <div>
            <h3>Écran Cafétéria</h3>
            <p>Bâtiment C - RDC</p>
        </div>
        <span class="badge offline">Hors ligne</span>
    </div>

    <div class="info">
        <div><span>Disposition:</span> Vue divisée</div>
        <div><span>Luminosité:</span> 90%</div>
        <div><span>Actualisation:</span> 45s</div>
    </div>

    <div class="actions">
        <button class="refresh">⟳ Actualiser</button>
        <button class="settings">⚙</button>
        <button class="power dark">⏻</button>
    </div>
</div>


<div class="screen-card">
    <div class="card-header">
        <div>
            <h3>Écran Extérieur</h3>
            <p>Parking Principal</p>
        </div>
        <span class="badge online">En ligne</span>
    </div>

    <div class="info">
        <div><span>Disposition:</span> Grille de données</div>
        <div><span>Luminosité:</span> 100%</div>
        <div><span>Actualisation:</span> 20s</div>
    </div>

    <div class="actions">
        <button class="refresh">⟳ Actualiser</button>
        <button class="settings">⚙</button>
        <button class="power">⏻</button>
    </div>
</div>

</section>


</body>
</html>