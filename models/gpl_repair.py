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

    # Champ de diagnostic spécifique aux problèmes GPL
    diagnostic = fields.Text(
        string="Diagnostic GPL",
        tracking=True,
        help="Diagnostic spécifique au système GPL"
    )

    # Champ de type de réparation GPL
    gpl_repair_type = fields.Selection([
        ('reservoir', 'Réservoir GPL'),
        ('injector', 'Injecteurs GPL'),
        ('tube', 'Tuyauterie GPL'),
        ('pressure', 'Pression et étanchéité'),
        ('electronic', 'Système électronique'),
        ('control', 'Contrôle périodique'),
        ('other', 'Autre composant GPL')
    ], string="Type de réparation GPL", tracking=True)

    # Champ pour indiquer si c'est une réparation GPL
    is_gpl_repair = fields.Boolean(
        string="Réparation GPL",
        compute="_compute_is_gpl_repair",
        store=True
    )

    @api.depends('gpl_vehicle_id')
    def _compute_is_gpl_repair(self):
        for repair in self:
            repair.is_gpl_repair = bool(repair.gpl_vehicle_id)

    @api.onchange('gpl_vehicle_id')
    def _onchange_gpl_vehicle(self):
        if self.gpl_vehicle_id:
            # Auto-remplir le partenaire depuis le véhicule
            self.partner_id = self.gpl_vehicle_id.client_id

            # Toujours utiliser le produit de service GPL générique
            service_product = self._get_or_create_gpl_service_product()
            self.product_id = service_product.id
            self.lot_id = False  # Pas de numéro de lot pour les services

    def _get_or_create_gpl_service_product(self):
        """Récupère ou crée un produit de service générique pour les réparations GPL"""
        ProductProduct = self.env['product.product']
        service_product = ProductProduct.search([
            ('name', '=', 'Service Réparation GPL'),
            ('type', '=', 'service')
        ], limit=1)

        if not service_product:
            # Créer le produit s'il n'existe pas
            service_product = ProductProduct.create({
                'name': 'Service Réparation GPL',
                'type': 'service',
                'categ_id': self.env.ref('product.product_category_all').id,
                'uom_id': self.env.ref('uom.product_uom_unit').id,
                'uom_po_id': self.env.ref('uom.product_uom_unit').id,
                'sale_ok': True,
                'purchase_ok': False,
                'invoice_policy': 'order',
                # Les produits de service n'ont pas de suivi par numéro de série
                'tracking': 'none',
            })

        return service_product

    @api.onchange('gpl_repair_type')
    def _onchange_gpl_repair_type(self):
        """Met à jour la description en fonction du type de réparation"""
        if self.gpl_repair_type and self.gpl_vehicle_id:
            repair_types = dict(self._fields['gpl_repair_type'].selection)
            repair_type_name = repair_types.get(self.gpl_repair_type)
            self.name = f"Réparation {repair_type_name} - {self.gpl_vehicle_id.name}"

            # Définir un texte de diagnostic initial en fonction du type
            diagnostic_templates = {
                'reservoir': "Inspection du réservoir GPL et accessoires",
                'injector': "Vérification des injecteurs et système d'alimentation",
                'tube': "Contrôle de l'état des tuyaux et raccords",
                'pressure': "Test d'étanchéité et contrôle de pression",
                'electronic': "Diagnostic du système électronique de gestion GPL",
                'control': "Contrôle périodique du système GPL",
                'other': "Diagnostic du système GPL"
            }

            if not self.diagnostic:  # Ne pas écraser un diagnostic existant
                self.diagnostic = diagnostic_templates.get(self.gpl_repair_type, "")

    @api.model
    def create(self, vals):
        # Si c'est une réparation GPL, toujours utiliser le produit de service
        if vals.get('gpl_vehicle_id'):
            service_product = self._get_or_create_gpl_service_product()
            vals['product_id'] = service_product.id
            # Pour un produit de service, pas de numéro de lot
            vals['lot_id'] = False

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

    def name_get(self):
        """Personnalisation de l'affichage du nom pour inclure les informations du véhicule"""
        result = []
        for repair in self:
            if repair.gpl_vehicle_id:
                name = f"{repair.name} ({repair.gpl_vehicle_id.license_plate})"
                result.append((repair.id, name))
            else:
                result.append((repair.id, repair.name))
        return result or super(RepairOrder, self).name_get()


class GplVehicle(models.Model):
    _inherit = 'gpl.vehicle'

    repair_order_id = fields.Many2one('repair.order', string='Ordre de réparation en cours')
    repair_count = fields.Integer(string='Nombre de réparations', compute='_compute_repair_count')

    def _compute_repair_count(self):
        """Calcule le nombre de réparations pour chaque véhicule"""
        for vehicle in self:
            vehicle.repair_count = self.env['repair.order'].search_count([
                ('gpl_vehicle_id', '=', vehicle.id)
            ])

    def action_create_repair_order(self):
        """
        Crée un nouvel ordre de réparation pour le véhicule GPL
        en utilisant uniquement un produit de service générique.
        """
        self.ensure_one()

        # Vérifier si le client est défini
        if not self.client_id:
            raise UserError(_("Veuillez définir un client pour ce véhicule avant de créer une réparation."))

        # Chercher ou créer un produit de service générique pour GPL
        ProductProduct = self.env['product.product']
        service_product = ProductProduct.search([
            ('name', '=', 'Service Réparation GPL'),
            ('type', '=', 'service')
        ], limit=1)

        if not service_product:
            # Créer le produit de service s'il n'existe pas
            service_product = ProductProduct.create({
                'name': 'Service Réparation GPL',
                'type': 'service',
                'categ_id': self.env.ref('product.product_category_all').id,
                'uom_id': self.env.ref('uom.product_uom_unit').id,
                'uom_po_id': self.env.ref('uom.product_uom_unit').id,
                'sale_ok': True,
                'purchase_ok': False,
                'tracking': 'none',  # Pas de suivi par numéro de série pour les services
            })

        # Récupérer le type d'opération par défaut pour les réparations
        RepairOrder = self.env['repair.order']
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'repair_operation'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)

        if not picking_type:
            raise UserError(
                _("Aucun type d'opération de réparation trouvé. Veuillez configurer un type d'opération de réparation."))

        # Préparation des valeurs pour repair.order
        values = {
            'product_id': service_product.id,
            'product_qty': 1.0,
            'product_uom': service_product.uom_id.id,
            'partner_id': self.client_id.id,
            'state': 'draft',
            'name': f"Réparation GPL - {self.name}",
            'lot_id': False,  # Pas de numéro de lot pour un service
            'schedule_date': fields.Datetime.now(),
            'user_id': self.env.user.id,
            'company_id': self.env.company.id,
            'picking_type_id': picking_type.id,
            'tag_ids': [(4, self.env.ref('gpl_fleet.tag_gpl_repair').id, 0)] if self.env.ref('gpl_fleet.tag_gpl_repair',
                                                                                             False) else [],
            'internal_notes': f"Réparation du véhicule GPL {self.name} (Immatriculation: {self.license_plate})",
        }

        # Création de l'ordre de réparation
        repair_order = RepairOrder.create(values)

        # Extension du modèle pour stocker le lien avec le véhicule GPL
        # (Ceci doit être fait après modification du modèle repair.order pour ajouter gpl_vehicle_id)
        if hasattr(repair_order, 'gpl_vehicle_id'):
            repair_order.gpl_vehicle_id = self.id

        # Mise à jour du statut du véhicule
        repair_status = self.env.ref('gpl_fleet.vehicle_status_en_service', raise_if_not_found=False)
        update_vals = {
            'next_service_type': 'repair'
        }

        # Stocker l'ID de la réparation si le champ est disponible dans le modèle
        if hasattr(self, 'repair_order_id'):
            update_vals['repair_order_id'] = repair_order.id

        if repair_status:
            update_vals['status_id'] = repair_status.id

        self.write(update_vals)

        # Ouvrir le formulaire de réparation
        return {
            'name': _('Réparation GPL'),
            'view_mode': 'form',
            'res_model': 'repair.order',
            'res_id': repair_order.id,
            'type': 'ir.actions.act_window',
        }

    def action_view_repairs(self):
        """
        Ouvre la liste des réparations pour ce véhicule
        """
        self.ensure_one()

        action = self.env.ref('repair.action_repair_order_tree').read()[0]
        action.update({
            'domain': [('gpl_vehicle_id', '=', self.id)],
            'context': {
                'default_gpl_vehicle_id': self.id,
                'default_partner_id': self.client_id.id if self.client_id else False,
                'search_default_gpl_vehicle_id': self.id
            },
            'name': _('Réparations de %s') % self.name,
            'views': [(False, 'tree'), (False, 'form'), (False, 'kanban')]
        })

        return action
