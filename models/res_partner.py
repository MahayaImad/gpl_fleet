from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_gpl_client = fields.Boolean(
        string="Client Véhicule GPL",
        help="Cochez cette case si ce partenaire possède un ou plusieurs véhicules GPL."
    )

    vehicle_ids = fields.One2many(
        'gpl.vehicle',
        'client_id',
        string='Véhicules'
    )

