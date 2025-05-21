from odoo import fields, models, api


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

    # Ajout du texte de certification
    gpl_certification_text = fields.Char(
        string='Texte de certification légale',
        config_parameter='gpl_fleet.certification_text',
        size=500,
        help="Texte légal qui apparaîtra sur les certificats de montage GPL",
        default="""Certifions que le véhicule décrit ci-dessous a été équipé conformément aux prescriptions de l'arrêté
    du 31 Août 1983 relatif aux conditions d'équipement de surveillance et d'exploitation des installations
    de GPL équipant les véhicules automobiles."""
    )

    # Champ pour stocker les IDs au format JSON
    gpl_default_technician_ids_json = fields.Char(
        string='Techniciens par défaut (JSON)',
        config_parameter='gpl_fleet.default_technician_ids_json',
        help="Liste des IDs des techniciens par défaut au format JSON"
    )
    # Nouveaux champs pour le technicien par défaut
    gpl_use_default_technician = fields.Boolean(
        string='Utiliser un technicien par défaut',
        config_parameter='gpl_fleet.use_default_technician',
        help="Sélectionner automatiquement un technicien par défaut pour les nouvelles installations"
    )

    # Champ calculé pour l'interface utilisateur
    gpl_default_technician_ids = fields.Many2many(
        'hr.employee',
        string='Techniciens par défaut',
        compute='_compute_gpl_default_technician_ids',
        inverse='_inverse_gpl_default_technician_ids',
        help="Techniciens qui seront automatiquement assignés aux nouvelles installations"
    )

    @api.depends('gpl_default_technician_ids_json')
    def _compute_gpl_default_technician_ids(self):
        """Convertit la chaîne JSON en champ Many2many"""
        for record in self:
            try:
                import json
                ids = json.loads(record.gpl_default_technician_ids_json or '[]')
                record.gpl_default_technician_ids = [(6, 0, ids)]
            except:
                record.gpl_default_technician_ids = [(6, 0, [])]

    def _inverse_gpl_default_technician_ids(self):
        """Convertit le champ Many2many en chaîne JSON"""
        for record in self:
            import json
            record.gpl_default_technician_ids_json = json.dumps(record.gpl_default_technician_ids.ids)
