from odoo import fields, models, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

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

    # Ajout du texte de certification
    gpl_certification_text = fields.Char(
        string='Texte de certification légale',
        config_parameter='gpl_fleet.certification_text',
        size=500,
        help="Texte légal qui apparaîtra sur les certificats de montage GPL",
        default="""Certifions que le véhicule décrit ci-dessous a été équipé conformément aux prescriptions de l'arrêté
    du 31 Août 1983 relatif aux conditions d'équipement de surveillance et d'exploitation des installations
    de GPL équipant les véhicules automobiles."""
    )

    # Champ pour stocker les IDs au format JSON
    gpl_default_technician_ids_json = fields.Char(
        string='Techniciens par défaut (JSON)',
        config_parameter='gpl_fleet.default_technician_ids_json',
        help="Liste des IDs des techniciens par défaut au format JSON"
    )
    # Nouveaux champs pour le technicien par défaut
    gpl_use_default_technician = fields.Boolean(
        string='Utiliser un technicien par défaut',
        config_parameter='gpl_fleet.use_default_technician',
        help="Sélectionner automatiquement un technicien par défaut pour les nouvelles installations"
    )

    # Champ calculé pour l'interface utilisateur
    gpl_default_technician_ids = fields.Many2many(
        'hr.employee',
        string='Techniciens par défaut',
        compute='_compute_gpl_default_technician_ids',
        inverse='_inverse_gpl_default_technician_ids',
        help="Techniciens qui seront automatiquement assignés aux nouvelles installations"
    )

    # === NOUVEAUX PARAMÈTRES POUR LES RÉSERVOIRS ===

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

    # Statistiques en lecture seule
    gpl_total_reservoirs = fields.Integer(
        string='Total réservoirs',
        compute='_compute_reservoir_stats',
        help="Nombre total de réservoirs GPL dans le système"
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
        help="Nombre de réservoirs avec certification expirée"
    )

    def _compute_reservoir_stats(self):
        """Calcule les statistiques des réservoirs"""
        for record in self:
            # Total des réservoirs GPL
            total_reservoirs = self.env['stock.lot'].search_count([
                ('product_id.is_gpl_reservoir', '=', True)
            ])

            # Réservoirs installés (liés à un véhicule)
            installed_reservoirs = self.env['stock.lot'].search_count([
                ('product_id.is_gpl_reservoir', '=', True),
                ('vehicle_id', '!=', False)
            ])

            # Réservoirs expirant bientôt
            expiring_reservoirs = self.env['stock.lot'].search_count([
                ('product_id.is_gpl_reservoir', '=', True),
                ('state', '=', 'expiring_soon')
            ])

            # Réservoirs expirés
            expired_reservoirs = self.env['stock.lot'].search_count([
                ('product_id.is_gpl_reservoir', '=', True),
                ('state', '=', 'expired')
            ])

            record.gpl_total_reservoirs = total_reservoirs
            record.gpl_reservoirs_installed = installed_reservoirs
            record.gpl_reservoirs_expiring = expiring_reservoirs
            record.gpl_reservoirs_expired = expired_reservoirs

    def action_view_reservoir_stats(self):
        """Action pour voir les statistiques détaillées des réservoirs"""
        return {
            'name': 'Statistiques des réservoirs GPL',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.lot',
            'view_mode': 'kanban,tree,form,pivot',
            'domain': [('product_id.is_gpl_reservoir', '=', True)],
            'context': {'search_default_group_state': 1}
        }

    def action_refresh_reservoir_states(self):
        """Action pour forcer le recalcul des états de tous les réservoirs"""
        reservoirs = self.env['stock.lot'].search([
            ('product_id.is_gpl_reservoir', '=', True)
        ])
        # Forcer le recalcul en touchant le champ de certification_date
        for reservoir in reservoirs:
            reservoir._compute_state()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Mise à jour terminée',
                'message': f'États recalculés pour {len(reservoirs)} réservoirs.',
                'type': 'success',
                'sticky': False,
            }
        }
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
