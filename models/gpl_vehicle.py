from odoo import models, fields, api

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
        ('inspection', 'Contrôle Technique'),
        ('testing', 'Test Réservoir (Réépreuve)'),
        ('validation', 'Validation Officielle'),
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

    repair_id = fields.Many2one(
        'gpl.service.repair',
        'Repair GPL',
        readonly=False
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

    def action_open_installation(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'gpl.service.installation',
            'res_id': self.installation_id.id,
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'current',
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
        Crée une nouvelle installation GPL pour le véhicule
        et met à jour le statut du véhicule.
        """
        self.ensure_one()
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
    # @api.depends('reservoir_id')
    # def _compute_reservoir_info(self):
    #     for record in self:
    #         if record.reservoir_id:
    #             record.reservoir_serial = record.reservoir_id.name
    #             record.reservoir_certification = record.reservoir_id.certification_number
    #             record.reservoir_certification_date = record.reservoir_id.certification_date
    #             record.reservoir_expiry_date = record.reservoir_id.expiry_date
    #             record.reservoir_state = record.reservoir_id.state
    #         else:
    #             record.reservoir_serial = False
    #             record.reservoir_certification = False
    #             record.reservoir_certification_date = False
    #             record.reservoir_expiry_date = False
    #             record.reservoir_state = False
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
