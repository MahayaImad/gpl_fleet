from odoo import models, api


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        res.mapped('product_tmpl_id')._compute_is_gpl_kit()
        return res

    def write(self, vals):
        res = super().write(vals)
        self.mapped('product_tmpl_id')._compute_is_gpl_kit()
        return res

class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        res.mapped('bom_id.product_tmpl_id')._compute_is_gpl_kit()
        return res

    def write(self, vals):
        res = super().write(vals)
        self.mapped('bom_id.product_tmpl_id')._compute_is_gpl_kit()
        return res
