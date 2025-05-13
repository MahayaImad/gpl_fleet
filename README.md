# Module GPL Installation pour Odoo 17

## Description
Le module **GPL Installation** est une solution complète pour la gestion des installations GPL sur véhicules dans Odoo 17. Il permet de suivre l'ensemble du cycle de vie d'une installation GPL, depuis l'enregistrement du véhicule jusqu'à la maintenance, en passant par l'installation et les réparations.

## Fonctionnalités principales

### 1. Gestion des véhicules GPL
- Enregistrement détaillé des véhicules avec informations techniques
- Suivi du statut des véhicules dans le flux d'installation
- Gestion des rendez-vous et planification des interventions
- Vue Kanban pour suivre les véhicules à travers les différentes étapes

### 2. Installations GPL
- Processus complet d'installation de réservoir GPL
- Traçabilité des réservoirs et composants installés
- Gestion automatique des stocks de pièces
- Création de bons de livraison pour les pièces utilisées
- Facturation intégrée des installations

### 3. Réparations GPL
- Intégration avec le module standard de réparation d'Odoo
- Diagnostic et suivi des problèmes spécifiques aux systèmes GPL
- Gestion des pièces de rechange et des services
- Facturation automatique des réparations

### 4. Gestion des réservoirs
- Suivi des réservoirs GPL par numéro de série
- Dates de certification et d'expiration des réservoirs
- Alertes pour les contrôles périodiques
- Historique complet des interventions par réservoir

## Installation

### Prérequis
- Odoo 17.0
- Modules dépendants : fleet, product, stock, mrp, hr, account, mail, repair

### Procédure d'installation
1. Téléchargez le module et placez-le dans le dossier addons d'Odoo
2. Mettez à jour la liste des applications dans Odoo
3. Recherchez "GPL Installation" et cliquez sur "Installer"
4. Configurez les paramètres de base après l'installation

## Configuration

### Paramètres généraux
- Configurer les séquences pour les installations et réparations
- Définir les statuts de véhicules disponibles
- Configurer les catégories de produits pour les kits GPL

### Produits et réservoirs
- Créer les produits pour les réservoirs GPL
- Définir les nomenclatures pour les kits d'installation
- Configurer les emplacements de stock

## Utilisation

### Flux de travail standard
1. **Enregistrement du véhicule**
   - Créer une fiche véhicule avec les informations du client
   - Planifier un rendez-vous d'installation

2. **Installation GPL**
   - Créer une installation depuis la fiche véhicule
   - Ajouter les produits et composants utilisés
   - Créer et valider le bon de livraison
   - Finaliser l'installation et mettre à jour le statut du véhicule

3. **Réparation et maintenance**
   - Créer un ordre de réparation depuis la fiche véhicule
   - Diagnostiquer et réparer les problèmes
   - Facturer la réparation au client

### Rapports et analyses
- Statistiques d'installations par technicien
- Suivi des stocks de pièces et réservoirs
- Analyses des coûts et revenus par type d'intervention

## Personnalisation
Le module est conçu pour être facilement extensible :
- Ajout de champs personnalisés sur les véhicules et installations
- Création de nouveaux statuts et étapes dans le flux
- Personnalisation des rapports et documents

## Support technique
Pour toute question ou assistance technique :
- Email : support@monentreprise.com
- Documentation en ligne : https://www.monentreprise.com/documentation

## Licence
Ce module est distribué sous licence LGPL-3.
