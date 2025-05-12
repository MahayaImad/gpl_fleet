from dateutil.relativedelta import relativedelta
from odoo import models, fields, api


class StockLotGplReservoir(models.Model):
    _inherit = 'stock.lot'
    _description = 'Lot de réservoir GPL'

    # Ces champs sont spécifiques à chaque réservoir (numéro de série)
    certification_number = fields.Char(string="Numéro de certification", tracking=True)
    certification_date = fields.Date(string="Date de certification", tracking=True)
    expiry_date = fields.Date(string="Date d'expiration", compute='_compute_expiry_date',
                              store=True, tracking=True)
    state = fields.Selection([
        ('valid', 'Valide'),
        ('expiring_soon', 'Expiration proche'),
        ('expired', 'Expiré')
    ], string="État", compute='_compute_state', store=True)
    vehicle_id = fields.Many2one('gpl.vehicle', string="Installé sur véhicule")

    # Champ calculé pour savoir si c'est un réservoir GPL
    is_gpl_reservoir = fields.Boolean(related='product_id.is_gpl_reservoir',
                                      string="Est un réservoir GPL", store=True)

    @api.depends('certification_date', 'is_gpl_reservoir')
    def _compute_expiry_date(self):
        for record in self:
            if record.certification_date and record.is_gpl_reservoir:
                record.expiry_date = record.certification_date + relativedelta(years=5)
            else:
                record.expiry_date = False

    @api.depends('expiry_date', 'is_gpl_reservoir')
    def _compute_state(self):
        today = fields.Date.today()
        warning_days = 180  # 6 months before expiration

        for record in self:
            if not record.is_gpl_reservoir:
                record.state = False
                continue

            if not record.expiry_date:
                record.state = 'valid'
                continue

            days_to_expiry = (record.expiry_date - today).days

            if days_to_expiry < 0:
                record.state = 'expired'
            elif days_to_expiry < warning_days:
                record.state = 'expiring_soon'
            else:
                record.state = 'valid'
