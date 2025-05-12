from odoo import models, fields

class GplReservoireFabricant(models.Model):
    _name = 'gpl.reservoir.fabricant'
    _description = 'Fabricant de Réservoir GPL'

    name = fields.Char(string='Nom', required=True)
    code = fields.Char(string='Code')
    pays = fields.Char(string='Pays')
    active = fields.Boolean(default=True)

    product_ids = fields.One2many('product.template', 'fabricant_id', string='Réservoirs')

