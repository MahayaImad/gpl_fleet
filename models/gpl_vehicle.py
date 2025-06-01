from odoo import models, fields, api, _
from datetime import datetime, timedelta
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

    # === NOUVEAUX CHAMPS POUR LE CALENDRIER ===

    # Durée estimée du service en heures
    estimated_duration = fields.Float(
        string='Durée estimée (heures)',
        compute='_compute_estimated_duration',
        store=True,
        help="Durée estimée du service en heures selon le type d'intervention"
    )

    # RDV toute la journée
    appointment_all_day = fields.Boolean(
        string='Toute la journée',
        default=False,
        help="Cocher si le rendez-vous/service prend toute la journée"
    )

    # Technicien assigné pour ce RDV
    assigned_technician_id = fields.Many2one(
        'hr.employee',
        string='Technicien assigné',
        help="Technicien principal assigné à ce rendez-vous"
    )

    # Priorité du service
    service_priority = fields.Selection([
        ('low', 'Normale'),
        ('medium', 'Importante'),
        ('high', 'Urgente')
    ], string='Priorité', default='low', tracking=True)

    # Couleur pour le calendrier (calculée automatiquement)
    color = fields.Integer(
        string='Couleur',
        compute='_compute_calendar_color',
        store=True,
        help="Couleur pour l'affichage calendrier"
    )

    # Informations de contact
    appointment_notes = fields.Text(
        string='Notes du rendez-vous',
        help="Notes spécifiques pour ce rendez-vous"
    )

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

    vehicle_type_code = fields.Char(
        string="Type de véhicule",
        compute="_compute_vehicle_type_code",
        store=True,
        readonly=False,
        help="Code de type du véhicule (par défaut: caractères 3 à 8 du VIN)"
    )
    acquisition_date = fields.Date(
        "Date d'immatriculation",
        required=False,
        default=fields.Date.today,
        help="Date d'immatriculation du véhicule"
    )

    model_year = fields.Char(
        'Année',
        help='Année du modèle'
    )

    tag_ids = fields.Many2many(
         'gpl.vehicle.tag',
         'gpl_vehicle_vehicle_tag_rel',
         'vehicle_tag_id',
         'tag_id',
         'Tags',
         copy=False
    )
    odometer = fields.Integer(
        string='Kilométrage',
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
        string='Installation active',
        readonly=True,
        help="Installation GPL en cours pour ce véhicule"
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

    @api.depends('vin_sn')
    def _compute_vehicle_type_code(self):
        """Extrait les caractères 3 à 8 du VIN quand le champ est vide"""
        for vehicle in self:
            # Ne pas écraser une valeur déjà définie manuellement
            if not vehicle.vehicle_type_code and vehicle.vin_sn and len(vehicle.vin_sn) >= 8:
                vehicle.vehicle_type_code = vehicle.vin_sn[3:8]
            elif not vehicle.vehicle_type_code:
                vehicle.vehicle_type_code = False

    # Méthode pour réinitialiser le code type selon le VIN
    def action_reset_vehicle_type_code(self):
        """Réinitialise le code type basé sur le VIN"""
        for vehicle in self:
            if vehicle.vin_sn and len(vehicle.vin_sn) >= 8:
                vehicle.vehicle_type_code = vehicle.vin_sn[3:8]

    # Méthode onchange pour suggérer le type lors de la saisie du VIN
    @api.onchange('vin_sn')
    def _onchange_vin_sn(self):
        if self.vin_sn and len(self.vin_sn) >= 8 and not self.vehicle_type_code:
            self.vehicle_type_code = self.vin_sn[3:8]
    def action_view_installations(self):
        self.ensure_one()

        installations = self.env['gpl.service.installation'].search([('vehicle_id', '=', self.id)])
        installation_count = len(installations)

        # Si une seule installation existe, l'ouvrir directement
        if installation_count == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Installation GPL',
                'res_model': 'gpl.service.installation',
                'view_mode': 'form',
                'res_id': installations.id,  # ID de l'installation unique
                'target': 'current',
                'context': {'default_vehicle_id': self.id}
            }
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

        installations = self.env['gpl.service.installation'].search([('vehicle_id', '=', self.id)])
        installation_count = len(installations)

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

        # Si une seule installation existe, l'ouvrir directement
        if installation_count == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Installation GPL',
                'res_model': 'gpl.service.installation',
                'view_mode': 'form',
                'res_id': installations.id,  # ID de l'installation unique
                'target': 'current',
                'context': {'default_vehicle_id': self.id}
            }

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

    @api.depends('next_service_type', 'service_priority')
    def _compute_estimated_duration(self):
        """Calcule la durée estimée selon le type de service"""
        duration_mapping = {
            'installation': {
                'low': 4.0,  # Installation normale: 4h
                'medium': 5.0,  # Installation complexe: 5h
                'high': 6.0  # Installation urgente/difficile: 6h
            },
            'repair': {
                'low': 2.0,  # Réparation simple: 2h
                'medium': 4.0,  # Réparation moyenne: 4h
                'high': 6.0  # Réparation complexe: 6h
            },
            'inspection': {
                'low': 1.0,  # Contrôle simple: 1h
                'medium': 1.5,  # Contrôle approfondi: 1.5h
                'high': 2.0  # Contrôle avec problèmes: 2h
            },
            'testing': {
                'low': 3.0,  # Réépreuve normale: 3h
                'medium': 4.0,  # Réépreuve avec réparation: 4h
                'high': 5.0  # Réépreuve complexe: 5h
            }
        }

        for record in self:
            service_type = record.next_service_type or 'repair'
            priority = record.service_priority or 'low'

            if service_type in duration_mapping:
                record.estimated_duration = duration_mapping[service_type].get(priority, 2.0)
            else:
                record.estimated_duration = 2.0  # Durée par défaut

    @api.depends('next_service_type', 'service_priority', 'appointment_date')
    def _compute_calendar_color(self):
        """Calcule la couleur pour l'affichage calendrier"""
        from datetime import datetime, timedelta

        for record in self:
            color = 0  # Couleur par défaut

            # Couleur selon le type de service
            if record.next_service_type == 'installation':
                color = 5  # Vert
            elif record.next_service_type == 'repair':
                color = 1  # Rouge
            elif record.next_service_type == 'inspection':
                color = 4  # Bleu
            elif record.next_service_type == 'testing':
                color = 3  # Jaune

            # Modifier la couleur selon la priorité
            if record.service_priority == 'high':
                color = 1  # Rouge pour urgent
            elif record.service_priority == 'medium' and color != 1:
                color = 3  # Orange pour important

            # Couleur spéciale pour les RDV en retard
            if record.appointment_date:
                appointment_date = fields.Datetime.from_string(record.appointment_date)
                if appointment_date < datetime.now():
                    color = 1  # Rouge pour retard

            record.color = color

    # === MÉTHODES D'ACTION AMÉLIORÉES ===

    def action_schedule_appointment(self):
        """Action pour programmer un rendez-vous"""
        self.ensure_one()

        # Vérifier que les prérequis sont remplis
        if not self.next_service_type:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Type de service requis'),
                    'message': _('Veuillez d\'abord définir le type de service à effectuer.'),
                    'type': 'warning',
                }
            }

        return {
            'name': _('Programmer un rendez-vous'),
            'type': 'ir.actions.act_window',
            'res_model': 'gpl.vehicle',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_appointment_date': fields.Datetime.now(),
                'focus_appointment': True
            }
        }

    def action_start_service(self):
        """Démarre le service selon le type prévu"""
        self.ensure_one()

        if not self.next_service_type:
            raise UserError(_("Aucun type de service défini pour ce véhicule."))

        if self.next_service_type == 'installation':
            return self.action_create_installation()
        elif self.next_service_type == 'repair':
            return self.action_create_new_repair()
        elif self.next_service_type == 'inspection':
            return self.action_create_inspection()
        elif self.next_service_type == 'testing':
            return self.action_create_reservoir_testing()
        else:
            raise UserError(_("Type de service non reconnu: %s") % self.next_service_type)

    def action_reschedule_appointment(self):
        """Reprogramme un rendez-vous"""
        self.ensure_one()

        return {
            'name': _('Reprogrammer le rendez-vous'),
            'type': 'ir.actions.act_window',
            'res_model': 'gpl.vehicle.reschedule.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_vehicle_id': self.id,
                'default_current_date': self.appointment_date,
                'default_service_type': self.next_service_type
            }
        }

    def action_complete_appointment(self):
        """Marque le rendez-vous comme terminé"""
        self.ensure_one()

        # Mettre à jour le statut
        completed_status = self.env.ref('gpl_fleet.vehicle_status_termine', raise_if_not_found=False)
        if completed_status:
            self.write({
                'status_id': completed_status.id,
                'appointment_date': False,
                'next_service_type': False,
                'assigned_technician_id': False
            })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Rendez-vous terminé'),
                'message': _('Le rendez-vous pour %s a été marqué comme terminé.') % self.name,
                'type': 'success',
            }
        }

    # === MÉTHODES DE RECHERCHE POUR LE CALENDRIER ===

    @api.model
    def get_today_appointments(self):
        """Retourne les rendez-vous du jour"""
        today = fields.Date.today()
        return self.search([
            ('appointment_date', '>=', today.strftime('%Y-%m-%d 00:00:00')),
            ('appointment_date', '<=', today.strftime('%Y-%m-%d 23:59:59'))
        ])

    @api.model
    def get_week_appointments(self):
        """Retourne les rendez-vous de la semaine"""
        from datetime import datetime, timedelta

        today = datetime.now().date()
        start_week = today - timedelta(days=today.weekday())
        end_week = start_week + timedelta(days=6)

        return self.search([
            ('appointment_date', '>=', start_week.strftime('%Y-%m-%d 00:00:00')),
            ('appointment_date', '<=', end_week.strftime('%Y-%m-%d 23:59:59'))
        ])

    @api.model
    def get_late_appointments(self):
        """Retourne les rendez-vous en retard"""
        now = fields.Datetime.now()
        return self.search([
            ('appointment_date', '<', now),
            ('status_id.is_done', '!=', True)
        ])

    # === CONTRAINTES ET VALIDATIONS ===

    @api.constrains('appointment_date', 'assigned_technician_id')
    def _check_technician_availability(self):
        """Vérifie que le technicien n'est pas déjà occupé à ce créneau"""
        for record in self:
            if record.appointment_date and record.assigned_technician_id:
                # Chercher les conflits (même technicien, même créneau)
                conflicting_appointments = self.search([
                    ('id', '!=', record.id),
                    ('assigned_technician_id', '=', record.assigned_technician_id.id),
                    ('appointment_date', '!=', False)
                ])

                for appointment in conflicting_appointments:
                    if appointment.appointment_date and record.appointment_date:
                        app_start = fields.Datetime.from_string(appointment.appointment_date)
                        app_end = app_start + timedelta(hours=appointment.estimated_duration or 2)

                        rec_start = fields.Datetime.from_string(record.appointment_date)
                        rec_end = rec_start + timedelta(hours=record.estimated_duration or 2)

                        # Vérifier le chevauchement
                        if not (rec_end <= app_start or rec_start >= app_end):
                            raise ValidationError(_(
                                "Le technicien %s est déjà occupé sur ce créneau.\n"
                                "Conflit avec: %s (%s)"
                            ) % (
                                                      record.assigned_technician_id.name,
                                                      appointment.name,
                                                      appointment.appointment_date
                                                  ))

    # === NOTIFICATIONS AUTOMATIQUES ===

    def _send_appointment_reminder(self):
        """Envoie des rappels de rendez-vous"""
        tomorrow = fields.Date.today() + timedelta(days=1)
        appointments_tomorrow = self.search([
            ('appointment_date', '>=', tomorrow.strftime('%Y-%m-%d 00:00:00')),
            ('appointment_date', '<=', tomorrow.strftime('%Y-%m-%d 23:59:59'))
        ])

        for appointment in appointments_tomorrow:
            # Créer une activité de rappel
            self.env['mail.activity'].create({
                'activity_type_id': self.env.ref('mail.mail_activity_data_call').id,
                'summary': f'Rappel RDV - {appointment.name}',
                'note': f'''Rendez-vous prévu demain pour:
                - Véhicule: {appointment.name}
                - Client: {appointment.client_id.name}
                - Service: {appointment.next_service_type}
                - Heure: {appointment.appointment_date}
                - Durée estimée: {appointment.estimated_duration}h''',
                'res_model_id': self.env['ir.model']._get('gpl.vehicle').id,
                'res_id': appointment.id,
                'user_id': appointment.assigned_technician_id.user_id.id if appointment.assigned_technician_id.user_id else self.env.uid,
                'date_deadline': fields.Date.today(),
            })

    @api.model
    def _cron_appointment_reminders(self):
        """Tâche cron pour les rappels de rendez-vous"""
        self._send_appointment_reminder()
        return True
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
