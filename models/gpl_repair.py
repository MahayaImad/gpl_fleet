# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class RepairOrder(models.Model):
    _inherit = 'repair.order'

    # Champ principal pour lier aux véhicules GPL
    gpl_vehicle_id = fields.Many2one(
        'gpl.vehicle',
        string='Véhicule GPL',
        tracking=True,
        help="Véhicule GPL concerné par cette réparation"
    )

    # Information utile sur le réservoir
    reservoir_lot_id = fields.Many2one(
        'stock.lot',
        string="Réservoir GPL",
        related='gpl_vehicle_id.reservoir_lot_id',
        store=True,
        readonly=True
    )

    # Champ de diagnostic spécifique aux problèmes GPL
    diagnostic = fields.Text(
        string="Diagnostic GPL",
        tracking=True,
        help="Diagnostic spécifique au système GPL"
    )

    @api.onchange('gpl_vehicle_id')
    def _onchange_gpl_vehicle(self):
        if self.gpl_vehicle_id:
            # Auto-remplir le partenaire depuis le véhicule
            self.partner_id = self.gpl_vehicle_id.client_id

            # Définir le produit comme étant le réservoir GPL si disponible
            if self.gpl_vehicle_id.reservoir_lot_id:
                self.product_id = self.gpl_vehicle_id.reservoir_lot_id.product_id
                self.lot_id = self.gpl_vehicle_id.reservoir_lot_id

    @api.model
    def create(self, vals):
        res = super(RepairOrder, self).create(vals)
        if res.gpl_vehicle_id:
            # Mettre à jour le statut du véhicule
            repair_status = self.env.ref('gpl_fleet.vehicle_status_en_service', raise_if_not_found=False)
            if repair_status:
                res.gpl_vehicle_id.write({
                    'status_id': repair_status.id,
                    'repair_order_id': res.id,
                    'next_service_type': 'repair'
                })

            # Log dans le chatter du véhicule
            res.gpl_vehicle_id.message_post(
                body=_("Ordre de réparation %s créé") % res.name,
                subtype_id=self.env.ref('mail.mt_note').id
            )
        return res

    def action_repair_done(self):
        res = super(RepairOrder, self).action_repair_done()
        for repair in self:
            if repair.gpl_vehicle_id:
                # Mettre à jour le statut du véhicule quand la réparation est terminée
                completed_status = self.env.ref('gpl_fleet.vehicle_status_termine', raise_if_not_found=False)
                if completed_status:
                    repair.gpl_vehicle_id.write({
                        'status_id': completed_status.id,
                        'next_service_type': False
                    })

                # Log dans le chatter du véhicule
                repair.gpl_vehicle_id.message_post(
                    body=_("Réparation %s terminée") % repair.name,
                    subtype_id=self.env.ref('mail.mt_note').id
                )
        return res

    def action_repair_cancel(self):
        res = super(RepairOrder, self).action_repair_cancel()
        for repair in self:
            if repair.gpl_vehicle_id:
                # Remettre le véhicule à son statut initial
                initial_status = self.env.ref('gpl_fleet.vehicle_status_nouveau', raise_if_not_found=False)
                if initial_status:
                    repair.gpl_vehicle_id.write({
                        'status_id': initial_status.id,
                        'repair_order_id': False,
                        'next_service_type': False
                    })
        return res
