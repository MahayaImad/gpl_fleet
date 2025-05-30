# -*- coding: utf-8 -*-

from . import models


def post_init_hook(cr, registry):
    """Hook exécuté après l'installation du module"""
    import logging
    from odoo import api, SUPERUSER_ID

    _logger = logging.getLogger(__name__)
    _logger.info("GPL Fleet: Initialisation post-installation...")

    # Initialiser l'environnement
    env = api.Environment(cr, SUPERUSER_ID, {})

    try:
        # 1. Vérifier et créer les statuts de véhicules par défaut
        _create_default_vehicle_statuses(env)

        # 2. Configurer les paramètres par défaut
        _set_default_parameters(env)

        # 3. Créer les fabricants de réservoirs par défaut
        _create_default_manufacturers(env)

        # 4. Créer les catégories de produits GPL
        _create_product_categories(env)

        # 5. Mettre à jour les réservoirs existants si nécessaire
        _migrate_existing_reservoirs(env)

        _logger.info("GPL Fleet: Initialisation terminée avec succès")

    except Exception as e:
        _logger.error(f"GPL Fleet: Erreur lors de l'initialisation: {str(e)}")


def _create_default_vehicle_statuses(env):
    """Crée les statuts de véhicules par défaut"""
    StatusModel = env['gpl.vehicle.status']

    default_statuses = [
        {
            'name': 'Enregistré',
            'sequence': 10,
            'description': 'Le véhicule est enregistré mais aucun service n\'est planifié',
            'color': 1
        },
        {
            'name': 'Rendez-vous fixé',
            'sequence': 20,
            'description': 'Le véhicule a un rendez-vous programmé',
            'color': 2
        },
        {
            'name': 'En service',
            'sequence': 30,
            'description': 'Le véhicule est actuellement en cours de service',
            'color': 3
        },
        {
            'name': 'En attente de validation',
            'sequence': 40,
            'description': 'En attente de validation par l\'ingénieur officiel',
            'color': 4
        },
        {
            'name': 'Terminé',
            'sequence': 50,
            'description': 'Tous les services sont terminés et validés',
            'color': 5,
            'is_done': True
        }
    ]

    for status_data in default_statuses:
        existing = StatusModel.search([('name', '=', status_data['name'])], limit=1)
        if not existing:
            StatusModel.create(status_data)


def _set_default_parameters(env):
    """Configure les paramètres système par défaut"""
    IrConfigParameter = env['ir.config_parameter'].sudo()

    default_params = {
        'gpl_fleet.reservoir_validity_years': '5',
        'gpl_fleet.reservoir_warning_months': '6',
        'gpl_fleet.enable_reservoir_alerts': 'True',
        'gpl_fleet.simplified_flow': 'False',
        'gpl_fleet.auto_invoice': 'False',
        'gpl_fleet.certification_text': '''Certifions que le véhicule décrit ci-dessous a été équipé conformément aux prescriptions de l'arrêté du 31 Août 1983 relatif aux conditions d'équipement de surveillance et d'exploitation des installations de GPL équipant les véhicules automobiles.'''
    }

    for key, value in default_params.items():
        if not IrConfigParameter.get_param(key):
            IrConfigParameter.set_param(key, value)


def _create_default_manufacturers(env):
    """Crée les fabricants de réservoirs par défaut"""
    ManufacturerModel = env['gpl.reservoir.fabricant']

    default_manufacturers = [
        {'name': 'BRC', 'code': 'BRC', 'pays': 'Italie'},
        {'name': 'LPG Tech', 'code': 'LPGT', 'pays': 'Pologne'},
        {'name': 'Tomasetto Achille', 'code': 'TOMAS', 'pays': 'Italie'},
        {'name': 'STAG', 'code': 'STAG', 'pays': 'Pologne'},
        {'name': 'Zavoli', 'code': 'ZAVOLI', 'pays': 'Italie'}
    ]

    for manufacturer_data in default_manufacturers:
        existing = ManufacturerModel.search([('code', '=', manufacturer_data['code'])], limit=1)
        if not existing:
            ManufacturerModel.create(manufacturer_data)


def _create_product_categories(env):
    """Crée les catégories de produits GPL"""
    CategoryModel = env['product.category']

    # Catégorie principale GPL
    gpl_cat = CategoryModel.search([('name', '=', 'Équipements GPL')], limit=1)
    if not gpl_cat:
        all_cat = env.ref('product.product_category_all', raise_if_not_found=False)
        parent_id = all_cat.id if all_cat else False
        gpl_cat = CategoryModel.create({
            'name': 'Équipements GPL',
            'parent_id': parent_id
        })

    # Sous-catégories
    subcategories = [
        'Réservoirs GPL',
        'Accessoires GPL',
        'Kits GPL',
        'Pièces détachées GPL'
    ]

    for subcat_name in subcategories:
        existing = CategoryModel.search([
            ('name', '=', subcat_name),
            ('parent_id', '=', gpl_cat.id)
        ], limit=1)
        if not existing:
            CategoryModel.create({
                'name': subcat_name,
                'parent_id': gpl_cat.id
            })


def _migrate_existing_reservoirs(env):
    """Met à jour les réservoirs existants avec les nouveaux champs"""
    StockLot = env['stock.lot']

    # Trouver les réservoirs GPL existants sans date de fabrication
    reservoirs_to_update = StockLot.search([
        ('is_gpl_reservoir', '=', True),
        ('manufacturing_date', '=', False),
        ('certification_date', '!=', False)
    ])

    from dateutil.relativedelta import relativedelta

    for reservoir in reservoirs_to_update:
        # Estimer la date de fabrication (6 mois avant certification)
        estimated_manufacturing = reservoir.certification_date - relativedelta(months=6)

        # Utiliser la date de certification comme première épreuve
        reservoir.write({
            'manufacturing_date': estimated_manufacturing,
            'last_test_date': reservoir.certification_date
        })


def uninstall_hook(cr, registry):
    """Hook exécuté lors de la désinstallation du module"""
    import logging
    _logger = logging.getLogger(__name__)
    _logger.info("GPL Fleet: Désinstallation du module...")

    # Ici on pourrait nettoyer des données spécifiques si nécessaire
    # Par exemple, supprimer les paramètres de configuration

    _logger.info("GPL Fleet: Désinstallation terminée")
