# -*- coding: utf-8 -*-
{
    'name': "GPL Installation - Gestion Complète",

    'summary': "Gestion complète des installations GPL avec suivi des réservoirs",

    'description': """
        Module complet de gestion des installations GPL
        ===============================================

        **Fonctionnalités principales :**

        🚗 **Gestion des véhicules GPL**
        - Suivi complet du cycle de vie des véhicules
        - Workflow avec statuts personnalisables
        - Planification des rendez-vous
        - Tableau de bord Kanban pour le suivi

        🔧 **Installations GPL**
        - Processus d'installation guidé (simplifié ou avancé)
        - Gestion automatique des stocks et nomenclatures
        - Génération automatique des bons de commande et livraison
        - Facturation intégrée
        - Certificats de montage automatiques

        🛢️ **Gestion avancée des réservoirs**
        - Suivi détaillé avec dates de fabrication, certification, réépreuves
        - Différenciation stock vs installés
        - Alertes automatiques pour les contrôles
        - Dashboard interactif avec statistiques
        - Gestion de la durée de vie (15 ans maximum)
        - Calcul automatique des dates de réépreuve (5 ans)

        🔨 **Réparations GPL**
        - Workflow complet de réparation
        - Gestion des pièces et services
        - Intégration stock et facturation
        - Suivi des remplacements de réservoirs

        ✅ **Contrôles et validations**
        - Contrôles techniques
        - Réépreuves de réservoirs
        - Suivi des certifications
        - Alertes automatiques

        📊 **Reporting et analyses**
        - Dashboard temps réel
        - Certificats de montage conformes
        - Certificats de contrôle triennal
        - Statistiques complètes

        ⚙️ **Configuration avancée**
        - Assistant de configuration initiale
        - Paramètres personnalisables
        - Workflow simplifié ou avancé
        - Gestion multi-entreprise

        🎯 **Points forts**
        - Interface intuitive avec Odoo 17
        - Workflow adaptatif selon la taille de l'entreprise
        - Conformité réglementaire
        - Traçabilité complète
        - Alertes proactives
        - Migration des données existantes
    """,

    'author': "SPSS",
    'website': "https://www.spss-dz.com",
    'category': 'Industries',
    'version': '17.0.2.0.0',
    'license': 'LGPL-3',

    # Dépendances requises
    'depends': [
        'base',
        'fleet',  # Gestion des véhicules
        'product',  # Produits et nomenclatures
        'stock',  # Gestion des stocks et lots
        'mrp',  # Nomenclatures et kits
        'hr',  # Employés/techniciens
        'purchase',  # Achats de matériel
        'account',  # Facturation
        'mail',  # Messagerie et suivi
        'sale',  # Ventes et devis
        'web',  # Interface web
    ],

    # Données et vues à charger
    'data': [
        # === SÉCURITÉ ===
        'security/ir.model.access.csv',
        'security/gpl_security.xml',

        # === DONNÉES DE BASE ===
        'data/ir_sequence_data.xml',
        #'data/migration_data.xml',

        # === VUES PRINCIPALES ===
        # Configuration
        'views/res_config_settings_views.xml',

        # Véhicules et suivi
        'views/fleet_vehicle_model_views.xml',
        'views/gpl_vehicle_views.xml',

        # Réservoirs (nouveau système amélioré)
        'views/gpl_reservoir_views.xml',

        # Produits et templates
        'views/product_template.xml',

        # === OPÉRATIONS ===
        # Installations
        'views/gpl_installation_views.xml',

        # Réparations
        'views/gpl_repair_views.xml',

        # Contrôles et validations
        'views/gpl_inspection_views.xml',
        'views/gpl_reservoir_testing_views.xml',

        # === ASSISTANTS ===
        'views/gpl_existing_installation_wizard_views.xml',
        'views/gpl_setup_wizard_views.xml',

        # === RAPPORTS ===
        'report/gpl_reports.xml',
        'report/gpl_certificates.xml',
        'report/gpl_triennial_certificate.xml',

        # === MENUS ET NAVIGATION ===
        'views/gpl_menus.xml',
    ],

    # === CARACTÉRISTIQUES AVANCÉES ===

    # Interface moderne
    'assets': {
        'web.assets_backend': [
            'gpl_fleet/static/src/css/gpl_dashboard.css',
            'gpl_fleet/static/src/js/gpl_dashboard.js',
        ],
    },

    # Données de démonstration (optionnel)
    'demo': [
        'demo/demo_data.xml',
    ],

    # Installation et configuration
    'installable': True,
    'application': True,
    'auto_install': False,

    # Priorité d'installation
    'sequence': 10,

    # === COMPATIBILITÉ ===
    # Version Odoo supportée
    'depends_version': '17.0',

    # === FONCTIONNALITÉS AVANCÉES ===

    # Post-installation
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',

    # Configuration externe
    'external_dependencies': {
        'python': ['python-dateutil'],
    },

    # === MÉTADONNÉES ===

    # Images et captures d'écran
    'images': [
        'static/description/banner.png',
        'static/description/icon.png',
        'static/description/screenshot_dashboard.png',
        'static/description/screenshot_vehicles.png',
        'static/description/screenshot_reservoirs.png',
    ],

    # Support et maintenance
    'support': 'mahaya.imad@gmail.com',
    'maintainer': 'SPSS',

    # === INFORMATIONS COMMERCIALES ===

    # Prix (pour Odoo Apps Store)
    'price': 399.00,
    'currency': 'EUR',

    # Mots-clés pour la recherche
    'keywords': [
        'GPL', 'LPG', 'Gas', 'Installation', 'Automotive',
        'Fleet', 'Reservoir', 'Tank', 'Certification',
        'Workshop', 'Maintenance', 'Repair'
    ],

    # Classification
    'complexity': 'expert',
    'maturity': 'production',

    # === DESCRIPTION DÉTAILLÉE ===
    'long_description': """
# GPL Installation - Module Professionnel Complet

## 🎯 Public cible
- Installateurs GPL certifiés
- Garages spécialisés GPL
- Centres de contrôle technique
- Gestionnaires de flottes GPL

## 📋 Prérequis techniques
- Odoo 17.0 ou supérieur
- Modules fleet, stock, mrp, account installés
- Accès administrateur pour la configuration initiale

## 🚀 Installation rapide
1. **Assistant de configuration** : Configuration guidée en 5 minutes
2. **Migration automatique** : Import des données existantes
3. **Données d'exemple** : Environnement de test pré-configuré
4. **Documentation** : Guide utilisateur complet inclus

## 💼 Retour sur investissement
- **Gain de temps** : Automatisation des tâches répétitives
- **Conformité** : Respect de la réglementation automatique
- **Traçabilité** : Suivi complet et historique
- **Alertes** : Prévention des non-conformités
- **Professionnalisme** : Certificats et rapports conformes

## 🔧 Personnalisation
Module entièrement personnalisable selon vos besoins :
- Workflow adaptable
- Certificats personnalisés
- Champs spécifiques
- Intégrations tierces

## 📞 Support
- Support technique inclus 30 jours
- Documentation complète
- Vidéos de formation
- Communauté d'utilisateurs

---
*Développé spécifiquement pour les professionnels GPL*
    """,
}
