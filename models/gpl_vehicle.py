from odoo import models, fields, api, _
import logging

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class GplVehicle(models.Model):
    _inherit = ['mail.thread', 'mail.activity.mixin', 'avatar.mixin']
    _name = 'gpl.vehicle'
    _description = 'Vehicle GPL'
    _order = 'license_plate asc, acquisition_date asc'

    name = fields.Char(compute="_compute_vehicle_name", store=True)
    description = fields.Html("Vehicle Description")
    active = fields.Boolean('Active', default=True, tracking=True)

    status_id = fields.Many2one('gpl.vehicle.status', 'Statut',
        default=lambda self: self._get_default_status(),
        group_expand='_read_group_status_ids',
        tracking=True,
        help='Statut actuel du véhicule dans le flux de service', ondelete="set null")

    next_service_type = fields.Selection([
        ('installation', 'Installation GPL'),
        ('repair', 'Réparation'),
        ('inspection', 'Contrôle Technique/Validation'),
        ('testing', 'Réépreuve Réservoir'),
    ], string='Prochain Service', tracking=True)

    appointment_date = fields.Datetime('Date de Rendez-vous', tracking=True)
    engineer_validation_date = fields.Date('Date de Validation', tracking=True)
    validation_certificate = fields.Char('Numéro de Certificat de Validation', tracking=True)

    license_plate = fields.Char(
        string="Matricule",
        tracking=True,
        help="Numéro de plaque d'immatriculation du véhicule"
    )
    vin_sn = fields.Char(
        'Numéro de châssis',
        help='Numéro unique inscrit sur le moteur du véhicule (numéro de châssis / VIN)',
        copy=False
    )
    acquisition_date = fields.Date(
        "Date d'immatriculation",
        required=False,
        default=fields.Date.today,
        help="Date d'immatriculation du véhicule"
    )
    color = fields.Char(
        string="Couleur",
        help='Couleur du véhicule'
    )

    model_year = fields.Char(
        'Année',
        help='Année du modèle'
    )
    vehicle_type = fields.Selection(related='model_id.vehicle_type')
    tag_ids = fields.Many2many(
         'gpl.vehicle.tag',
         'gpl_vehicle_vehicle_tag_rel',
         'vehicle_tag_id',
         'tag_id',
         'Tags',
         copy=False
    )
    odometer = fields.Float(
        compute='_get_odometer',
        inverse='_set_odometer',
        string='Dernier relevé du compteur',
        help='Relevé du compteur kilométrique du véhicule au moment de cet enregistrement"'
    )
    odometer_unit = fields.Selection(
        [('kilometers', 'km')],
        'Odometer Unit',
        default='kilometers',
        required=True
    )
    transmission = fields.Selection(
        [('manual', 'Manuele'), ('automatic', 'Automatique')],
        'Transmission',
    )
    category_id = fields.Many2one(
        'fleet.vehicle.model.category',
        'Categorie',
        related="model_id.category_id",
        store=True, readonly=False
    )
    image_128 = fields.Image(
        related='model_id.image_128',
        readonly=True
    )

    vehicle_properties = fields.Properties(
        'Properties',
        definition='model_id.vehicle_properties_definition',
        copy=True
    )
    odometer_count = fields.Integer(
        compute="_compute_count_all",
        string='Kilométrage'
    )
    brand_id = fields.Many2one(
        'fleet.vehicle.model.brand',
        'Brand',
        related="model_id.brand_id",
        store=True, readonly=False
    )
    model_id = fields.Many2one(
        'fleet.vehicle.model',
        'Model',
        tracking=True,
        required=True
    )
    client_id = fields.Many2one(
        'res.partner',
        string="Client",
        compute='_compute_owner',
        store=True, readonly=False
    )
    client_phone = fields.Char(related='client_id.phone', string='Téléphone', readonly=True)

    installation_id = fields.Many2one(
        'gpl.service.installation',
        'Installation GPL',
        readonly=False
    )

    repair_order_id = fields.Many2one(
        'gpl.repair.order',
        string='Réparation en cours',
        readonly=True,
        help="Réparation actuelle pour ce véhicule"
    )

    reservoir_lot_id = fields.Many2one('stock.lot', string="Réservoir installé",
                                     domain="[('product_id.is_gpl_reservoir', '=', True)]",
                                     tracking=True)
    # Champs reliés au réservoir via le lot
    reservoir_certification_number = fields.Char(related="reservoir_lot_id.certification_number",
                                               string="Numéro de certification", readonly=True)
    reservoir_certification_date = fields.Date(related="reservoir_lot_id.certification_date",
                                             string="Date de certification", readonly=True)
    reservoir_expiry_date = fields.Date(related="reservoir_lot_id.expiry_date",
                                       string="Date d'expiration", readonly=True)

    installation_count = fields.Integer(
        compute="_compute_count_all",
        string='Installations'
    )
    repair_count = fields.Integer(
        string='Nombre de réparations',
        compute='_compute_repair_count'
    )

    @api.depends('installation_id')
    def _compute_count_all(self):
        for record in self:
            # Calcul du nombre d'installations liées au véhicule
            record.installation_count = self.env['gpl.service.installation'].search_count([
                ('vehicle_id', '=', record.id)
            ])
            # Calcul du compteur kilométrique (code existant)
            record.odometer_count = self.env['gpl.vehicle.odometer'].search_count([
                ('vehicle_id', '=', record.id)
            ])

    def action_view_installations(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Installations GPL',
            'res_model': 'gpl.service.installation',
            'view_mode': 'tree,form',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {'default_vehicle_id': self.id}
        }

    def _compute_repair_count(self):
        """Calcule le nombre de réparations pour chaque véhicule"""
        for vehicle in self:
            vehicle.repair_count = self.env['gpl.repair.order'].search_count([
                ('vehicle_id', '=', vehicle.id)
            ])

    def action_create_new_repair(self):
        """
        Crée une nouvelle réparation GPL pour le véhicule
        """
        self.ensure_one()

        # Vérifie si une réparation existe déjà
        existing_repair = self.env['gpl.repair.order'].search([
            ('vehicle_id', '=', self.id),
            ('state', 'in', ['draft', 'scheduled', 'preparation', 'in_progress'])
        ], limit=1)

        if existing_repair:
            return {
                'name': _('Réparation GPL existante'),
                'view_mode': 'form',
                'res_model': 'gpl.repair.order',
                'res_id': existing_repair.id,
                'type': 'ir.actions.act_window',
            }

        # Créer une nouvelle réparation
        repair_vals = {
            'vehicle_id': self.id,
            'client_id': self.client_id.id,
            'date_repair': fields.Date.today(),
        }

        new_repair = self.env['gpl.repair.order'].create(repair_vals)

        # Mettre à jour le statut du véhicule
        status_value = self.env.ref('gpl_fleet.vehicle_status_planifie', raise_if_not_found=False)
        if status_value:
            self.write({
                'status_id': status_value.id,
                'next_service_type': 'repair'
            })

        return {
            'name': _('Nouvelle Réparation GPL'),
            'view_mode': 'form',
            'res_model': 'gpl.repair.order',
            'res_id': new_repair.id,
            'type': 'ir.actions.act_window',
        }

    def action_view_repairs(self):
        """
        Ouvre la liste des réparations pour ce véhicule
        """
        self.ensure_one()

        return {
            'name': _('Réparations de %s') % self.name,
            'view_mode': 'tree,form,kanban',
            'res_model': 'gpl.repair.order',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {
                'default_vehicle_id': self.id,
                'default_client_id': self.client_id.id if self.client_id else False,
                'search_default_vehicle_id': self.id
            },
            'type': 'ir.actions.act_window',
        }
    @api.depends('model_id.brand_id.name', 'model_id.name', 'license_plate')
    def _compute_vehicle_name(self):
        for record in self:
            record.name = f"{record.model_id.brand_id.name or ''}/{record.model_id.name or ''}/{record.license_plate or _('No Plate')}"

    def _get_odometer(self):
        GPLVehicleOdometer = self.env['gpl.vehicle.odometer']
        for record in self:
            vehicle_odometer = GPLVehicleOdometer.search(
                [('vehicle_id', '=', record.id)],
                limit=1,
                order='value desc'
            )
            record.odometer = vehicle_odometer.value if vehicle_odometer else 0

    def _set_odometer(self):
        for record in self:
            if record.odometer:
                date = fields.Date.context_today(record)
                data = {'value': record.odometer, 'date': date, 'vehicle_id': record.id}
                self.env['gpl.vehicle.odometer'].create(data)

    @api.model
    def _read_group_status_ids(self, statuses, domain, order):
        return self.env['gpl.vehicle.status'].search([], order=order)

    def _get_default_status(self):
        status = self.env.ref('gpl_fleet.vehicle_status_nouveau', raise_if_not_found=False)
        return status if status and status.id else False

    @api.onchange('next_service_type', 'appointment_date')
    def _onchange_service_planning(self):
        if self.next_service_type and self.appointment_date:
            planned_status = self.env.ref('gpl_fleet.vehicle_status_planifie', raise_if_not_found=False)
            if planned_status:
                self.status_id = planned_status

    def action_create_installation(self):
        """
        Ouvre une installation GPL existante non terminée si elle existe,
        sinon crée une nouvelle installation GPL pour le véhicule
        et met à jour le statut du véhicule.
        """
        self.ensure_one()

        # Rechercher d'abord s'il existe une installation non terminée
        existing_installation = self.env['gpl.service.installation'].search([
            ('vehicle_id', '=', self.id),
            ('state', 'in', ['draft', 'planned', 'in_progress'])  # États non terminés
        ], limit=1)

        if existing_installation:
            # S'il y a une installation existante non terminée, l'ouvrir
            return {
                'name': _('Installation GPL existante'),
                'view_mode': 'form',
                'res_model': 'gpl.service.installation',
                'res_id': existing_installation.id,
                'type': 'ir.actions.act_window',
            }
        # Récupération du statut "En service"
        in_progress_status = self.env.ref('gpl_fleet.vehicle_status_en_service', raise_if_not_found=False)

        # Création de l'installation
        installation_vals = {
            'vehicle_id': self.id,
            'date_service': fields.Datetime.now(),
            'date_planned': self.appointment_date,
        }

        installation = self.env['gpl.service.installation'].create(installation_vals)

        # Mise à jour du statut du véhicule
        if in_progress_status:
            self.write({
                'status_id': in_progress_status.id,
                'installation_id': installation.id,
            })

        # Redirection vers le formulaire d'installation
        return {
            'name': _('Installation GPL'),
            'view_mode': 'form',
            'res_model': 'gpl.service.installation',
            'res_id': installation.id,
            'type': 'ir.actions.act_window',
        }

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
                'invoice_policy': 'order',
                'tracking': 'none',  # Pas de suivi par numéro de série pour les services
            })

        # Préparation des valeurs pour repair.order
        values = {
            'gpl_vehicle_id': self.id,
            'product_id': service_product.id,
            'product_qty': 1.0,
            'partner_id': self.client_id.id,
            'product_uom': service_product.uom_id.id,
            'state': 'draft',
            'invoice_method': 'after_repair',
            'name': f"Réparation GPL - {self.name}",
            'lot_id': False,  # Pas de numéro de lot pour un service
        }

        # Création de l'ordre de réparation
        RepairOrder = self.env['repair.order']
        repair_order = RepairOrder.create(values)

        # Mise à jour du statut du véhicule
        repair_status = self.env.ref('gpl_fleet.vehicle_status_en_service', raise_if_not_found=False)
        update_vals = {
            'repair_order_id': repair_order.id,
            'next_service_type': 'repair'
        }
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

    def action_create_inspection(self):
        """
        Crée un nouveau contrôle technique/validation pour le véhicule
        """
        self.ensure_one()

        # Rechercher d'abord s'il existe un contrôle non terminé
        existing_inspection = self.env['gpl.inspection'].search([
            ('vehicle_id', '=', self.id),
            ('state', 'in', ['draft', 'scheduled', 'in_progress'])
        ], limit=1)

        if existing_inspection:
            # S'il y a un contrôle existant non terminé, l'ouvrir
            return {
                'name': _('Contrôle Technique existant'),
                'view_mode': 'form',
                'res_model': 'gpl.inspection',
                'res_id': existing_inspection.id,
                'type': 'ir.actions.act_window',
            }

        # Récupération du statut "En service"
        in_progress_status = self.env.ref('gpl_fleet.vehicle_status_en_service', raise_if_not_found=False)

        # Création du contrôle technique
        inspection_vals = {
            'vehicle_id': self.id,
            'date_inspection': fields.Date.today(),
        }

        inspection = self.env['gpl.inspection'].create(inspection_vals)

        # Mise à jour du statut du véhicule
        if in_progress_status:
            self.write({
                'status_id': in_progress_status.id,
            })

        # Redirection vers le formulaire de contrôle
        return {
            'name': _('Contrôle Technique'),
            'view_mode': 'form',
            'res_model': 'gpl.inspection',
            'res_id': inspection.id,
            'type': 'ir.actions.act_window',
        }

    def action_create_reservoir_testing(self):
        """
        Crée une nouvelle réépreuve de réservoir pour le véhicule
        """
        self.ensure_one()

        if not self.reservoir_lot_id:
            raise UserError(_("Ce véhicule n'a pas de réservoir GPL installé. Impossible de créer une réépreuve."))

        # Rechercher d'abord s'il existe une réépreuve non terminée
        existing_testing = self.env['gpl.reservoir.testing'].search([
            ('vehicle_id', '=', self.id),
            ('state', 'in', ['draft', 'scheduled', 'in_progress'])
        ], limit=1)

        if existing_testing:
            # S'il y a une réépreuve existante non terminée, l'ouvrir
            return {
                'name': _('Réépreuve Réservoir existante'),
                'view_mode': 'form',
                'res_model': 'gpl.reservoir.testing',
                'res_id': existing_testing.id,
                'type': 'ir.actions.act_window',
            }

        # Récupération du statut "En service"
        in_progress_status = self.env.ref('gpl_fleet.vehicle_status_en_service', raise_if_not_found=False)

        # Création de la réépreuve
        testing_vals = {
            'vehicle_id': self.id,
            'date_testing': fields.Date.today(),
        }

        testing = self.env['gpl.reservoir.testing'].create(testing_vals)

        # Mise à jour du statut du véhicule
        if in_progress_status:
            self.write({
                'status_id': in_progress_status.id,
            })

        # Redirection vers le formulaire de réépreuve
        return {
            'name': _('Réépreuve Réservoir'),
            'view_mode': 'form',
            'res_model': 'gpl.reservoir.testing',
            'res_id': testing.id,
            'type': 'ir.actions.act_window',
        }
class FleetVehicleModel(models.Model):
    _inherit = 'fleet.vehicle.model'

class GplVehicleStatus(models.Model):
    _name = 'gpl.vehicle.status'
    _description = 'Statut du Véhicule'
    _order = 'sequence, id'

    name = fields.Char('Nom', required=True)
    sequence = fields.Integer('Séquence', default=10)
    fold = fields.Boolean('Plié dans Kanban')
    active = fields.Boolean('Actif', default=True)
    description = fields.Text("Description")
    color = fields.Integer("Index de couleur")
    is_done = fields.Boolean('Étape finale')
