# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_gpl_client = fields.Boolean(
        string="Is GPL Vehicle Client",
        help="Check this box if this partner owns one or more GPL vehicles."
    )

    vehicle_ids = fields.One2many(
        'gpl.vehicle',
        'client_id',
        string='Vehicles'
    )

