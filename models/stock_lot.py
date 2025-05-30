from dateutil.relativedelta import relativedelta

from odoo.exceptions import UserError, ValidationError
from odoo import models, fields, api


class StockLotGplReservoir(models.Model):
    _inherit = 'stock.lot'
    _description = 'Lot de réservoir GPL'

    # === CHAMPS SPÉCIFIQUES GPL ===

    # Dates importantes
    manufacturing_date = fields.Date(string="Date de fabrication", tracking=True,
                                     help="Date de fabrication du réservoir (limite 15 ans)")
    certification_number = fields.Char(string="Numéro de certification", tracking=True)
    certification_date = fields.Date(string="Date de certification initiale", tracking=True)
    last_test_date = fields.Date(string="Date de dernière épreuve", tracking=True)
    next_test_date = fields.Date(string="Date de prochaine réépreuve", compute='_compute_next_test_date',
                                 store=True, tracking=True)
    expiry_date = fields.Date(string="Date d'expiration", compute='_compute_expiry_date',
                              store=True, tracking=True)

    # État du réservoir
    state = fields.Selection([
        ('valid', 'Valide'),
        ('expiring_soon', 'Expiration proche'),
        ('expired', 'Expiré'),
        ('test_required', 'Réépreuve requise'),
        ('too_old', 'Trop ancien (15 ans)'),
        ('out_of_service', 'Hors service')
    ], string="État", compute='_compute_state', store=True)

    # Localisation et statut
    location_status = fields.Selection([
        ('stock', 'En stock'),
        ('installed', 'Installé'),
        ('maintenance', 'En maintenance'),
        ('scrapped', 'Mis au rebut')
    ], string="Statut localisation", compute='_compute_location_status', store=True)

    # Véhicule associé
    vehicle_id = fields.Many2one('gpl.vehicle', string="Installé sur véhicule")

    # Champ calculé pour savoir si c'est un réservoir GPL
    is_gpl_reservoir = fields.Boolean(related='product_id.is_gpl_reservoir',
                                      string="Est un réservoir GPL", store=True)

    # === CHAMPS CALCULÉS POUR DASHBOARD ===

    age_years = fields.Float(string="Âge (années)", compute='_compute_age_info', store=True)
    remaining_life_years = fields.Float(string="Durée de vie restante (années)",
                                        compute='_compute_age_info', store=True)
    days_until_next_test = fields.Integer(string="Jours jusqu'à la prochaine réépreuve",
                                          compute='_compute_test_info', store=True)

    # === MÉTHODES DE CALCUL ===

    @api.depends('manufacturing_date')
    def _compute_age_info(self):
        """Calcule l'âge et la durée de vie restante"""
        today = fields.Date.today()
        for record in self:
            if record.manufacturing_date and record.is_gpl_reservoir:
                years_diff = (today - record.manufacturing_date).days / 365.25
                record.age_years = years_diff
                record.remaining_life_years = max(0, 15 - years_diff)
            else:
                record.age_years = 0
                record.remaining_life_years = 0

    @api.depends('last_test_date', 'certification_date')
    def _compute_next_test_date(self):
        """Calcule la prochaine date de réépreuve (5 ans après la dernière épreuve)"""
        for record in self:
            if record.is_gpl_reservoir:
                # Utiliser la date de dernière épreuve, ou la date de certification initiale
                base_date = record.last_test_date or record.certification_date
                if base_date:
                    record.next_test_date = base_date + relativedelta(years=5)
                else:
                    record.next_test_date = False
            else:
                record.next_test_date = False

    @api.depends('certification_date', 'is_gpl_reservoir')
    def _compute_expiry_date(self):
        """Calcule la date d'expiration pour compatibilité (basée sur certification)"""
        for record in self:
            if record.certification_date and record.is_gpl_reservoir:
                record.expiry_date = record.certification_date + relativedelta(years=5)
            else:
                record.expiry_date = False

    @api.depends('next_test_date', 'manufacturing_date', 'is_gpl_reservoir')
    def _compute_state(self):
        """Calcule l'état du réservoir selon toutes les contraintes"""
        today = fields.Date.today()
        warning_days = int(self.env['ir.config_parameter'].sudo().get_param(
            'gpl_fleet.reservoir_warning_months', '6')) * 30

        for record in self:
            if not record.is_gpl_reservoir:
                record.state = False
                continue

            # 1. Vérifier si trop ancien (15 ans depuis fabrication)
            if record.manufacturing_date:
                age_days = (today - record.manufacturing_date).days
                if age_days > 15 * 365:  # 15 ans
                    record.state = 'too_old'
                    continue

            # 2. Vérifier les réépreuves
            if record.next_test_date:
                days_to_test = (record.next_test_date - today).days

                if days_to_test < 0:
                    record.state = 'test_required'
                    continue
                elif days_to_test < warning_days:
                    record.state = 'expiring_soon'
                    continue

            # 3. Si tout va bien
            record.state = 'valid'

    @api.depends('next_test_date')
    def _compute_test_info(self):
        """Calcule les infos sur les tests"""
        today = fields.Date.today()
        for record in self:
            if record.next_test_date and record.is_gpl_reservoir:
                record.days_until_next_test = (record.next_test_date - today).days
            else:
                record.days_until_next_test = 0

    @api.depends('vehicle_id')
    def _compute_location_status(self):
        """Détermine le statut de localisation"""
        for record in self:
            if not record.is_gpl_reservoir:
                record.location_status = False
            elif record.vehicle_id:
                record.location_status = 'installed'
            elif record.state == 'too_old':
                record.location_status = 'scrapped'
            else:
                record.location_status = 'stock'

    # === MÉTHODES D'ACTION ===
    def action_perform_test(self):
        """Action pour enregistrer une nouvelle épreuve"""
        self.ensure_one()
        return {
            'name': 'Enregistrer une réépreuve',
            'type': 'ir.actions.act_window',
            'res_model': 'gpl.reservoir.testing',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_reservoir_lot_id': self.id,
                'default_vehicle_id': self.vehicle_id.id if self.vehicle_id else False,
            }
        }

    def action_install_on_vehicle(self):
        """Action pour installer sur un véhicule"""
        self.ensure_one()
        if self.location_status != 'stock':
            raise UserError("Ce réservoir n'est pas disponible en stock.")

        return {
            'name': 'Installer sur véhicule',
            'type': 'ir.actions.act_window',
            'res_model': 'gpl.vehicle',
            'view_mode': 'tree,form',
            'domain': [('reservoir_lot_id', '=', False)],
            'context': {'search_default_no_reservoir': 1}
        }

    def action_remove_from_vehicle(self):
        """Action pour retirer du véhicule"""
        self.ensure_one()
        if self.vehicle_id:
            self.vehicle_id.reservoir_lot_id = False
            self.vehicle_id = False

    def action_scrap_reservoir(self):
        """Action pour mettre au rebut"""
        self.ensure_one()
        self.write({
            'location_status': 'scrapped',
            'state': 'out_of_service'
        })

    # === CONTRAINTES ===
    @api.constrains('manufacturing_date', 'certification_date', 'last_test_date')
    def _check_dates_coherence(self):
        """Vérifie la cohérence des dates"""
        for record in self:
            if not record.is_gpl_reservoir:
                continue

            if record.manufacturing_date and record.certification_date:
                if record.certification_date < record.manufacturing_date:
                    raise ValidationError(
                        "La date de certification ne peut pas être antérieure à la date de fabrication."
                    )

            if record.last_test_date and record.certification_date:
                if record.last_test_date < record.certification_date:
                    raise ValidationError(
                        "La date de dernière épreuve ne peut pas être antérieure à la certification initiale."
                    )

    # === RECHERCHE ET DOMAINES ===
    @api.model
    def get_reservoirs_in_stock(self):
        """Retourne les réservoirs disponibles en stock"""
        return self.search([
            ('is_gpl_reservoir', '=', True),
            ('location_status', '=', 'stock'),
            ('state', 'in', ['valid', 'expiring_soon'])
        ])

    @api.model
    def get_reservoirs_installed(self):
        """Retourne les réservoirs installés"""
        return self.search([
            ('is_gpl_reservoir', '=', True),
            ('location_status', '=', 'installed')
        ])

    @api.model
    def get_reservoirs_needing_test(self):
        """Retourne les réservoirs nécessitant une réépreuve"""
        return self.search([
            ('is_gpl_reservoir', '=', True),
            ('state', 'in', ['test_required', 'expiring_soon'])
        ])

    @api.model
    def get_reservoir_statistics(self):
        """Retourne les statistiques des réservoirs"""
        total = self.search_count([('is_gpl_reservoir', '=', True)])
        in_stock = self.search_count([
            ('is_gpl_reservoir', '=', True),
            ('location_status', '=', 'stock')
        ])
        installed = self.search_count([
            ('is_gpl_reservoir', '=', True),
            ('location_status', '=', 'installed')
        ])
        need_test = self.search_count([
            ('is_gpl_reservoir', '=', True),
            ('state', 'in', ['test_required', 'expiring_soon'])
        ])
        too_old = self.search_count([
            ('is_gpl_reservoir', '=', True),
            ('state', '=', 'too_old')
        ])

        return {
            'total': total,
            'in_stock': in_stock,
            'installed': installed,
            'need_test': need_test,
            'too_old': too_old,
            'valid': total - need_test - too_old
        }

    @api.model
    def _cron_check_gpl_reservoir_state(self):
        """
        Méthode cron pour vérifier et mettre à jour l'état de tous les réservoirs GPL
        Appelée quotidiennement par ir.cron
        """
        # Récupérer tous les réservoirs GPL
        reservoirs = self.search([('is_gpl_reservoir', '=', True)])

        # Forcer le recalcul des états
        for reservoir in reservoirs:
            # Déclencher le recalcul des champs calculés
            reservoir._compute_age_info()
            reservoir._compute_test_info()
            reservoir._compute_state()
            reservoir._compute_location_status()

        # Envoyer des notifications pour les réservoirs nécessitant une attention
        if self.env['ir.config_parameter'].sudo().get_param('gpl_fleet.enable_reservoir_alerts', 'True').lower() == 'true':
            self._send_reservoir_alerts()

        return True

    @api.model
    def _send_reservoir_alerts(self):
        """
        Envoie des notifications pour les réservoirs nécessitant une attention
        """
        # Réservoirs nécessitant une réépreuve immédiate
        urgent_reservoirs = self.search([
            ('is_gpl_reservoir', '=', True),
            ('state', 'in', ['test_required', 'expired']),
            ('location_status', '=', 'installed')
        ])

        if urgent_reservoirs:
            # Créer une activité pour le responsable GPL
            activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
            if activity_type:
                for reservoir in urgent_reservoirs:
                    # Créer une activité sur le véhicule associé
                    if reservoir.vehicle_id:
                        self.env['mail.activity'].create({
                            'activity_type_id': activity_type.id,
                            'summary': f'Réépreuve urgente - Réservoir {reservoir.name}',
                            'note': f'Le réservoir {reservoir.name} installé sur {reservoir.vehicle_id.name} nécessite une réépreuve urgente.',
                            'res_model_id': self.env['ir.model']._get('gpl.vehicle').id,
                            'res_id': reservoir.vehicle_id.id,
                            'user_id': reservoir.vehicle_id.create_uid.id or self.env.uid,
                            'date_deadline': fields.Date.today(),
                        })

        # Réservoirs approchant de la date de réépreuve
        warning_reservoirs = self.search([
            ('is_gpl_reservoir', '=', True),
            ('state', '=', 'expiring_soon'),
            ('location_status', '=', 'installed')
        ])

        if warning_reservoirs:
            # Logique similaire pour les alertes d'avertissement
            # avec une date limite dans 30 jours
            pass
