from odoo import fields, models, api, _
from odoo.exceptions import UserError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # === PARAMÈTRES D'INSTALLATION ===
    gpl_simplified_flow = fields.Boolean(
        string='Installation GPL simplifiée',
        config_parameter='gpl_fleet.simplified_flow',
        help="Activer le flux d'installation simplifié (préparation → bon de livraison → terminé avec facturation automatique)"
    )

    gpl_auto_invoice = fields.Boolean(
        string='Facturation automatique',
        config_parameter='gpl_fleet.auto_invoice',
        help="Créer automatiquement la facture lors de la validation d'une installation GPL"
    )

    gpl_use_default_technician = fields.Boolean(
        string='Utiliser un technicien par défaut',
        config_parameter='gpl_fleet.use_default_technician',
        help="Sélectionner automatiquement un technicien par défaut pour les nouvelles installations"
    )

    # Champs pour le technicien par défaut
    gpl_default_technician_ids_json = fields.Char(
        string='Techniciens par défaut (JSON)',
        config_parameter='gpl_fleet.default_technician_ids_json',
        help="Liste des IDs des techniciens par défaut au format JSON"
    )

    gpl_default_technician_ids = fields.Many2many(
        'hr.employee',
        string='Techniciens par défaut',
        compute='_compute_gpl_default_technician_ids',
        inverse='_inverse_gpl_default_technician_ids',
        help="Techniciens qui seront automatiquement assignés aux nouvelles installations"
    )

    # === PARAMÈTRES DES RÉSERVOIRS ===
    gpl_reservoir_validity_years = fields.Integer(
        string='Durée de validité des réservoirs (années)',
        config_parameter='gpl_fleet.reservoir_validity_years',
        default=5,
        help="Durée en années avant la réépreuve obligatoire du réservoir GPL"
    )

    gpl_reservoir_warning_months = fields.Integer(
        string='Alerte avant expiration (mois)',
        config_parameter='gpl_fleet.reservoir_warning_months',
        default=6,
        help="Nombre de mois avant expiration pour déclencher l'alerte 'expiration proche'"
    )

    gpl_enable_reservoir_alerts = fields.Boolean(
        string='Activer les alertes de réservoirs',
        config_parameter='gpl_fleet.enable_reservoir_alerts',
        default=True,
        help="Activer les notifications automatiques pour les réservoirs expirant bientôt"
    )

    # === TEXTES LÉGAUX ===
    gpl_certification_text = fields.Char(
        string='Texte de certification légale',
        config_parameter='gpl_fleet.certification_text',
        size=2000,  # Taille suffisante pour le texte légal
        help="Texte légal qui apparaîtra sur les certificats de montage GPL",
        default="Certifions que le véhicule décrit ci-dessous a été équipé conformément aux prescriptions de l'arrêté du 31 Août 1983 relatif aux conditions d'équipement de surveillance et d'exploitation des installations de GPL équipant les véhicules automobiles."
    )

    # === STATISTIQUES EN LECTURE SEULE ===
    gpl_total_reservoirs = fields.Integer(
        string='Total réservoirs',
        compute='_compute_reservoir_stats',
        help="Nombre total de réservoirs GPL dans le système"
    )

    gpl_reservoirs_in_stock = fields.Integer(
        string='Réservoirs en stock',
        compute='_compute_reservoir_stats',
        help="Nombre de réservoirs disponibles en stock"
    )

    gpl_reservoirs_installed = fields.Integer(
        string='Réservoirs installés',
        compute='_compute_reservoir_stats',
        help="Nombre de réservoirs actuellement installés sur des véhicules"
    )

    gpl_reservoirs_expiring = fields.Integer(
        string='Réservoirs expirant bientôt',
        compute='_compute_reservoir_stats',
        help="Nombre de réservoirs nécessitant une réépreuve dans les 6 prochains mois"
    )

    gpl_reservoirs_expired = fields.Integer(
        string='Réservoirs expirés',
        compute='_compute_reservoir_stats',
        help="Nombre de réservoirs avec certification expirée ou trop anciens"
    )

    # === MÉTHODES DE CALCUL ===
    @api.depends('gpl_default_technician_ids_json')
    def _compute_gpl_default_technician_ids(self):
        """Convertit la chaîne JSON en champ Many2many"""
        for record in self:
            try:
                import json
                ids = json.loads(record.gpl_default_technician_ids_json or '[]')
                record.gpl_default_technician_ids = [(6, 0, ids)]
            except:
                record.gpl_default_technician_ids = [(6, 0, [])]

    def _inverse_gpl_default_technician_ids(self):
        """Convertit le champ Many2many en chaîne JSON"""
        for record in self:
            import json
            record.gpl_default_technician_ids_json = json.dumps(record.gpl_default_technician_ids.ids)

    def _compute_reservoir_stats(self):
        """Calcule les statistiques des réservoirs"""
        for record in self:
            StockLot = self.env['stock.lot']

            # Total des réservoirs GPL
            record.gpl_total_reservoirs = StockLot.search_count([
                ('is_gpl_reservoir', '=', True)
            ])

            # Réservoirs en stock
            record.gpl_reservoirs_in_stock = StockLot.search_count([
                ('is_gpl_reservoir', '=', True),
                ('location_status', '=', 'stock')
            ])

            # Réservoirs installés
            record.gpl_reservoirs_installed = StockLot.search_count([
                ('is_gpl_reservoir', '=', True),
                ('location_status', '=', 'installed')
            ])

            # Réservoirs expirant bientôt
            record.gpl_reservoirs_expiring = StockLot.search_count([
                ('is_gpl_reservoir', '=', True),
                ('state', '=', 'expiring_soon')
            ])

            # Réservoirs expirés ou problématiques
            record.gpl_reservoirs_expired = StockLot.search_count([
                ('is_gpl_reservoir', '=', True),
                ('state', 'in', ['expired', 'test_required', 'too_old'])
            ])

    # === ACTIONS ===
    def action_view_reservoir_stats(self):
        """Action pour voir les statistiques détaillées des réservoirs"""
        return {
            'name': _('Dashboard Réservoirs GPL'),
            'type': 'ir.actions.act_window',
            'res_model': 'gpl.reservoir.dashboard',
            'view_mode': 'form',
            'target': 'current',
            'context': {}
        }

    def action_refresh_reservoir_states(self):
        """Action pour forcer le recalcul des états de tous les réservoirs"""
        reservoirs = self.env['stock.lot'].search([
            ('is_gpl_reservoir', '=', True)
        ])

        # Forcer le recalcul en touchant les champs calculés
        for reservoir in reservoirs:
            reservoir._compute_state()
            reservoir._compute_age_info()
            reservoir._compute_test_info()
            reservoir._compute_location_status()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Mise à jour terminée'),
                'message': _('États recalculés pour %d réservoirs.') % len(reservoirs),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_expired_reservoirs(self):
        """Action pour voir les réservoirs nécessitant une attention urgente"""
        return {
            'name': _('Réservoirs à traiter en urgence'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.lot',
            'view_mode': 'tree,form',
            'domain': [
                ('is_gpl_reservoir', '=', True),
                ('state', 'in', ['expired', 'test_required', 'too_old'])
            ],
            'context': {'search_default_test_required': 1}
        }

    # === ACTIONS RAPIDES ===
    def action_open_vehicles(self):
        """Ouvre la gestion des véhicules"""
        return {
            'name': _('Véhicules GPL'),
            'type': 'ir.actions.act_window',
            'res_model': 'gpl.vehicle',
            'view_mode': 'kanban,tree,form',
            'target': 'current'
        }

    def action_open_installations(self):
        """Ouvre la gestion des installations"""
        return {
            'name': _('Installations GPL'),
            'type': 'ir.actions.act_window',
            'res_model': 'gpl.service.installation',
            'view_mode': 'kanban,tree,form',
            'target': 'current'
        }

    def action_open_reservoirs(self):
        """Ouvre la gestion des réservoirs"""
        return {
            'name': _('Dashboard Réservoirs GPL'),
            'type': 'ir.actions.act_window',
            'res_model': 'gpl.reservoir.dashboard',
            'view_mode': 'form',
            'target': 'current'
        }

    def action_open_repairs(self):
        """Ouvre la gestion des réparations"""
        return {
            'name': _('Réparations GPL'),
            'type': 'ir.actions.act_window',
            'res_model': 'gpl.repair.order',
            'view_mode': 'kanban,tree,form',
            'target': 'current'
        }

    def action_open_inspections(self):
        """Ouvre la gestion des contrôles techniques"""
        return {
            'name': _('Contrôles Techniques GPL'),
            'type': 'ir.actions.act_window',
            'res_model': 'gpl.inspection',
            'view_mode': 'tree,form',
            'target': 'current'
        }

    def action_new_existing_installation(self):
        """Ouvre l'assistant d'enregistrement d'installation existante"""
        return {
            'name': _('Enregistrer installation existante'),
            'type': 'ir.actions.act_window',
            'res_model': 'gpl.existing.installation.wizard',
            'view_mode': 'form',
            'target': 'new'
        }

    # === MÉTHODES DE MIGRATION/INITIALISATION ===
    def action_migrate_existing_reservoirs(self):
        """Migration des réservoirs existants pour ajouter les nouvelles données"""
        reservoirs = self.env['stock.lot'].search([
            ('is_gpl_reservoir', '=', True),
            ('manufacturing_date', '=', False)
        ])

        migrated_count = 0
        for reservoir in reservoirs:
            # Si on a une date de certification mais pas de fabrication
            if reservoir.certification_date and not reservoir.manufacturing_date:
                # Estimer la date de fabrication (1 an avant certification)
                from dateutil.relativedelta import relativedelta
                estimated_manufacturing = reservoir.certification_date - relativedelta(years=1)

                reservoir.write({
                    'manufacturing_date': estimated_manufacturing,
                    'last_test_date': reservoir.certification_date
                })
                migrated_count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Migration terminée'),
                'message': _('%d réservoirs ont été mis à jour avec des dates estimées.') % migrated_count,
                'type': 'info',
                'sticky': True,
            }
        }

    def action_create_sample_reservoirs(self):
        """Crée des réservoirs d'exemple pour les tests"""
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_("Seuls les administrateurs peuvent créer des données d'exemple."))

        # Créer des produits réservoirs d'exemple
        product_vals = [
            {
                'name': 'Réservoir GPL 60L Cylindrique',
                'is_gpl_reservoir': True,
                'type': 'product',
                'tracking': 'serial',
                'capacity': 60.0,
                'shape': 'cylindrical',
            },
            {
                'name': 'Réservoir GPL 80L Toroïdal',
                'is_gpl_reservoir': True,
                'type': 'product',
                'tracking': 'serial',
                'capacity': 80.0,
                'shape': 'toroidal',
            }
        ]

        products = []
        for vals in product_vals:
            product = self.env['product.template'].create(vals)
            products.append(product)

        # Créer des lots d'exemple
        from datetime import date
        from dateutil.relativedelta import relativedelta
        import random

        lot_count = 0
        for product in products:
            product_product = product.product_variant_ids[0]

            # Créer 5 lots par produit avec différents âges
            for i in range(5):
                # Dates aléaoires sur les 10 dernières années
                months_ago = random.randint(12, 120)
                manufacturing_date = date.today() - relativedelta(months=months_ago)
                certification_date = manufacturing_date + relativedelta(months=6)

                # Parfois ajouter une réépreuve
                last_test_date = certification_date
                if random.choice([True, False]):
                    last_test_date = certification_date + relativedelta(years=random.randint(1, 3))

                lot_vals = {
                    'name': f'{product.name}-{i + 1:03d}',
                    'product_id': product_product.id,
                    'manufacturing_date': manufacturing_date,
                    'certification_date': certification_date,
                    'last_test_date': last_test_date,
                    'certification_number': f'CERT-{random.randint(10000, 99999)}'
                }

                self.env['stock.lot'].create(lot_vals)
                lot_count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Données d\'exemple créées'),
                'message': _('%d produits et %d réservoirs d\'exemple ont été créés.') % (len(products), lot_count),
                'type': 'success',
                'sticky': True,
            }
        }

    def action_setup_wizard(self):
        """Lance l'assistant de configuration initial"""
        return {
            'name': _('Assistant de configuration GPL'),
            'type': 'ir.actions.act_window',
            'res_model': 'gpl.setup.wizard',
            'view_mode': 'form',
            'target': 'new'
        }
