from dateutil.relativedelta import relativedelta
from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'  # Fixed from *inherit to _inherit

    is_gpl_reservoir = fields.Boolean(string="Est un réservoir GPL")
    is_gpl_kit = fields.Boolean(string="Est un kit GPL", compute='_compute_is_gpl_kit', store=True)

    is_reservoir_readonly = fields.Boolean(string="Réservoir readonly", compute="_compute_reservoir_readonly")

    capacity = fields.Float(string="Capacité (litres)")
    shape = fields.Selection([
        ('cylindrical', 'Cylindrique'),
        ('toroidal', 'Toroïdal'),
        ('other', 'Autre')
    ], string="Forme")

    fabricant_id = fields.Many2one('gpl.reservoir.fabricant', string="Fabricant")

    @api.depends('is_gpl_kit')
    def _compute_reservoir_readonly(self):  # Fixed from computereservoir_readonly
        for rec in self:
            if not rec.id:
                rec.is_reservoir_readonly = False  # nouveau produit : champ libre
            else:
                rec.is_reservoir_readonly = rec.is_gpl_kit

    @api.depends_context('active_model', 'active_id')
    def _compute_is_gpl_kit(self):  # Fixed from *compute*is_gpl_kit
        for template in self:
            # Initialize as False first
            template.is_gpl_kit = False

            # Cherche les nomenclatures où ce produit est le produit principal
            boms = self.env['mrp.bom'].search([('product_tmpl_id', '=', template.id)])
            found_reservoir = False
            for bom in boms:
                for line in bom.bom_line_ids:
                    # Safely check if the product exists and has the is_gpl_reservoir attribute
                    if line.product_id and line.product_id.product_tmpl_id and line.product_id.product_tmpl_id.is_gpl_reservoir:
                        found_reservoir = True
                        break
                if found_reservoir:
                    break
            template.is_gpl_kit = found_reservoir
