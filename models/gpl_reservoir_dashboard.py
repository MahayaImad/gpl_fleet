from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta


class GplReservoirDashboard(models.Model):
    _name = 'gpl.reservoir.dashboard'
    _description = 'Dashboard pour réservoirs GPL'

    name = fields.Char(string='Nom', default='Tableau de bord Réservoirs GPL', required=True)

    @api.model
    def action_open_dashboard(self):
        """Action pour ouvrir le dashboard (crée l'enregistrement s'il n'existe pas)"""
        dashboard = self.search([], limit=1)
        if not dashboard:
            dashboard = self.create({'name': 'Tableau de bord Réservoirs GPL'})

        return {
            'name': 'Tableau de bord Réservoirs GPL',
            'type': 'ir.actions.act_window',
            'res_model': 'gpl.reservoir.dashboard',
            'res_id': dashboard.id,
            'view_mode': 'form',
            'view_id': self.env.ref('votre_module.view_gpl_reservoir_dashboard_form').id,
            'target': 'current',
        }

    def name_get(self):
        return [(rec.id, 'Tableau de bord Réservoirs GPL') for rec in self]

    # Statistiques calculées
    total_reservoirs = fields.Integer(string='Total réservoirs', compute='_compute_statistics')
    reservoirs_in_stock = fields.Integer(string='En stock', compute='_compute_statistics')
    reservoirs_installed = fields.Integer(string='Installés', compute='_compute_statistics')
    reservoirs_need_control = fields.Integer(string='À contrôler', compute='_compute_statistics')
    reservoirs_too_old = fields.Integer(string='Trop anciens', compute='_compute_statistics')

    # Répartition par âge
    reservoirs_0_5_years = fields.Integer(string='0-5 ans', compute='_compute_age_distribution')
    reservoirs_5_10_years = fields.Integer(string='5-10 ans', compute='_compute_age_distribution')
    reservoirs_10_15_years = fields.Integer(string='10-15 ans', compute='_compute_age_distribution')
    reservoirs_over_15_years = fields.Integer(string='Plus de 15 ans', compute = '_compute_age_distribution')

    # Alertes
    immediate_retest = fields.Integer(string='Réépreuve immédiate', compute='_compute_alerts')
    retest_6_months = fields.Integer(string='Réépreuve dans 6 mois', compute='_compute_alerts')

    @api.depends()
    def _compute_statistics(self):
        """Calcule les statistiques principales avec actualisation automatique"""
        # ACTUALISATION AUTOMATIQUE - ajoutez ces 6 lignes au début
        reservoirs = self.env['stock.lot'].search([('is_gpl_reservoir', '=', True)])
        for reservoir in reservoirs:
            reservoir._compute_state()
            reservoir._compute_age_info()
            reservoir._compute_test_info()
            reservoir._compute_location_status()

        # VOTRE CODE EXISTANT reste identique
        for dashboard in self:
            StockLot = self.env['stock.lot']

            dashboard.total_reservoirs = StockLot.search_count([
                ('is_gpl_reservoir', '=', True)
            ])

            dashboard.reservoirs_in_stock = StockLot.search_count([
                ('is_gpl_reservoir', '=', True),
                ('location_status', '=', 'stock')
            ])

            dashboard.reservoirs_installed = StockLot.search_count([
                ('is_gpl_reservoir', '=', True),
                ('location_status', '=', 'installed')
            ])

            dashboard.reservoirs_need_control = StockLot.search_count([
                ('is_gpl_reservoir', '=', True),
                ('state', 'in', ['expiring_soon', 'test_required'])
            ])

            dashboard.reservoirs_too_old = StockLot.search_count([
                ('is_gpl_reservoir', '=', True),
                ('state', '=', 'too_old')
            ])

    @api.depends()
    def _compute_age_distribution(self):
        """Calcule la répartition par âge avec actualisation automatique"""
        # ACTUALISATION AUTOMATIQUE - ajoutez ces 6 lignes au début
        reservoirs = self.env['stock.lot'].search([('is_gpl_reservoir', '=', True)])
        for reservoir in reservoirs:
            reservoir._compute_state()
            reservoir._compute_age_info()
            reservoir._compute_test_info()
            reservoir._compute_location_status()

        # VOTRE CODE EXISTANT reste identique
        for dashboard in self:
            StockLot = self.env['stock.lot']

            dashboard.reservoirs_0_5_years = StockLot.search_count([
                ('is_gpl_reservoir', '=', True),
                ('age_years', '<', 5)
            ])

            dashboard.reservoirs_5_10_years = StockLot.search_count([
                ('is_gpl_reservoir', '=', True),
                ('age_years', '>=', 5),
                ('age_years', '<', 10)
            ])

            dashboard.reservoirs_10_15_years = StockLot.search_count([
                ('is_gpl_reservoir', '=', True),
                ('age_years', '>=', 10),
                ('age_years', '<', 15)
            ])

            dashboard.reservoirs_over_15_years = StockLot.search_count([
                ('is_gpl_reservoir', '=', True),
                ('age_years', '>=', 15)
            ])

    @api.depends()
    def _compute_alerts(self):
        """Calcule les alertes avec actualisation automatique"""
        # ACTUALISATION AUTOMATIQUE - ajoutez ces 6 lignes au début
        reservoirs = self.env['stock.lot'].search([('is_gpl_reservoir', '=', True)])
        for reservoir in reservoirs:
            reservoir._compute_state()
            reservoir._compute_age_info()
            reservoir._compute_test_info()
            reservoir._compute_location_status()

        # VOTRE CODE EXISTANT reste identique
        for dashboard in self:
            StockLot = self.env['stock.lot']

            dashboard.immediate_retest = StockLot.search_count([
                ('is_gpl_reservoir', '=', True),
                ('days_until_next_test', '<=', 0)
            ])

            dashboard.retest_6_months = StockLot.search_count([
                ('is_gpl_reservoir', '=', True),
                ('days_until_next_test', '>', 0),
                ('days_until_next_test', '<=', 180)
            ])

    def action_view_all_reservoirs(self):
        """Action pour voir tous les réservoirs"""
        return {
            'name': _('Tous les réservoirs GPL'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.lot',
            'view_mode': 'kanban,tree,form',
            'domain': [('is_gpl_reservoir', '=', True)],
            'context': {'search_default_group_state': 1}
        }

    def action_view_stock_reservoirs(self):
        """Action pour voir les réservoirs en stock"""
        return {
            'name': _('Réservoirs en stock'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.lot',
            'view_mode': 'kanban,tree,form',
            'domain': [
                ('is_gpl_reservoir', '=', True),
                ('location_status', '=', 'stock')
            ],
            'context': {'search_default_valid': 1}
        }

    def action_view_installed_reservoirs(self):
        """Action pour voir les réservoirs installés"""
        return {
            'name': _('Réservoirs installés'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.lot',
            'view_mode': 'kanban,tree,form',
            'domain': [
                ('is_gpl_reservoir', '=', True),
                ('location_status', '=', 'installed')
            ],
            'context': {'search_default_group_vehicle': 1}
        }

    def action_view_control_needed(self):
        """Action pour voir les réservoirs nécessitant un contrôle"""
        return {
            'name': _('Réservoirs à contrôler'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.lot',
            'view_mode': 'tree,form',
            'domain': [
                ('is_gpl_reservoir', '=', True),
                ('state', 'in', ['expiring_soon', 'test_required', 'too_old'])
            ],
            'context': {'search_default_test_required': 1}
        }

    def action_view_immediate_retest(self):
        """Action pour voir les réservoirs nécessitant une réépreuve immédiate"""
        return {
            'name': _('Réépreuves immédiates'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.lot',
            'view_mode': 'tree,form',
            'domain': [
                ('is_gpl_reservoir', '=', True),
                ('days_until_next_test', '<=', 0)
            ]
        }

    def action_view_retest_6_months(self):
        """Action pour voir les réservoirs à contrôler dans 6 mois"""
        return {
            'name': _('Réépreuves dans 6 mois'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.lot',
            'view_mode': 'tree,form',
            'domain': [
                ('is_gpl_reservoir', '=', True),
                ('days_until_next_test', '>', 0),
                ('days_until_next_test', '<=', 180)
            ]
        }

    def action_new_reservoir_product(self):
        """Action pour créer un nouveau produit réservoir"""
        return {
            'name': _('Nouveau réservoir GPL'),
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_is_gpl_reservoir': True,
                'default_type': 'product',
                'default_tracking': 'serial'
            }
        }

    def action_refresh_stats(self):
        """Action pour actualiser les statistiques"""
        # Forcer le recalcul des états de tous les réservoirs
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
                'title': _('Actualisation terminée'),
                'message': _('Statistiques mises à jour pour %d réservoirs.') % len(reservoirs),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_export_reservoir_report(self):
        """Action pour exporter un rapport de tous les réservoirs GPL"""
        # Récupérer tous les réservoirs GPL
        reservoirs = self.env['stock.lot'].search([('is_gpl_reservoir', '=', True)], order='name')

        if not reservoirs:
            raise UserError(_("Aucun réservoir GPL trouvé pour générer le rapport."))

        # Utiliser directement report_action sur les réservoirs
        return self.env.ref('gpl_fleet.action_export_reservoir_report').report_action(reservoirs)

    @api.model
    def get_dashboard_data(self):
        """Retourne les données pour le dashboard sous forme de dictionnaire"""
        dashboard = self.create({})

        return {
            'total_reservoirs': dashboard.total_reservoirs,
            'reservoirs_in_stock': dashboard.reservoirs_in_stock,
            'reservoirs_installed': dashboard.reservoirs_installed,
            'reservoirs_need_control': dashboard.reservoirs_need_control,
            'reservoirs_too_old': dashboard.reservoirs_too_old,
            'age_distribution': {
                '0_5_years': dashboard.reservoirs_0_5_years,
                '5_10_years': dashboard.reservoirs_5_10_years,
                '10_15_years': dashboard.reservoirs_10_15_years,
                'over_15_years': dashboard.reservoirs_over_15_years,
            },
            'alerts': {
                'immediate_retest': dashboard.immediate_retest,
                'retest_6_months': dashboard.retest_6_months,
            }
        }
