from odoo import fields, models


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
