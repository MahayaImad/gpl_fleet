from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
from dateutil.relativedelta import relativedelta


class GplExistingInstallationWizard(models.TransientModel):
    _name = 'gpl.existing.installation.wizard'
    _description = 'Assistant pour enregistrer une installation GPL existante'

    # Étape du wizard
    step = fields.Selection([
        ('client', 'Informations Client'),
        ('vehicle', 'Informations Véhicule'),
        ('reservoir', 'Informations Réservoir'),
        ('summary', 'Résumé')
    ], string='Étape', default='client')

    # === INFORMATIONS CLIENT ===
    client_id = fields.Many2one('res.partner', string='Client existant')
    create_new_client = fields.Selection([
        ('new', 'Nouveau client'),
        ('existing', 'Client existant'),
    ], string="Client :", default='new')
    # Champs pour nouveau client
    client_name = fields.Char(string='Nom / Raison sociale')
    client_phone = fields.Char(string='Téléphone')
    client_email = fields.Char(string='Email')
    client_street = fields.Char(string='Adresse')
    client_city = fields.Char(string='Ville')
    client_zip = fields.Char(string='Code postal')
    client_is_company = fields.Boolean(string='Est une entreprise')

    # === INFORMATIONS VÉHICULE ===
    license_plate = fields.Char(string='Matricule')
    vin_sn = fields.Char(string='Numéro de châssis (VIN)')
    model_id = fields.Many2one('fleet.vehicle.model', string='Modèle')
    model_year = fields.Char(string='Année')
    acquisition_date = fields.Date(string="Date d'immatriculation", default=fields.Date.today)

    # === INFORMATIONS RÉSERVOIR ===
    reservoir_product_id = fields.Many2one(
        'product.product',
        string='Type de réservoir',
        domain="[('is_gpl_reservoir', '=', True)]"
    )
    reservoir_serial_number = fields.Char(string='Numéro de série du réservoir')
    reservoir_certification_number = fields.Char(string='Numéro de certification')
    reservoir_manufacturing_date = fields.Date(string='Date de fabrication')
    reservoir_last_test_date = fields.Date(string="Date de dernière épreuve")
    reservoir_capacity = fields.Float(string='Capacité (litres)', related='reservoir_product_id.capacity',
                                      readonly=True)
    reservoir_fabricant = fields.Many2one(string='Fabricant', related='reservoir_product_id.fabricant_id',
                                          readonly=True)

    # Date calculée
    reservoir_next_test_date = fields.Date(string="Date d'expiration calculée", compute='_compute_next_test_date')
    reservoir_age_years = fields.Float(string="Âge (années)", compute='_compute_age_info', store=True)
    reservoir_remaining_life_years = fields.Float(string="Durée de vie restante (années)",
                                        compute='_compute_age_info', store=True)
    reservoir_remaining_life_years_pourcentage = fields.Float(string="Durée de vie",
                                                    compute='_compute_age_info', store=True)
    reservoir_days_until_next_test = fields.Integer(string="Jours jusqu'à la prochaine réépreuve",
                                          compute='_compute_next_test_date_days', store=True)

    # === INFORMATIONS INSTALLATION ===
    installation_date = fields.Date(string="Date d'installation", default=fields.Date.today)
    installation_notes = fields.Text(string='Notes sur l\'installation existante')

    # Installateur externe
    external_installer = fields.Char(string='Installateur externe')
    external_certificate = fields.Char(string='Numéro de certificat externe')

    # === DONNÉES CRÉÉES ===
    created_client_id = fields.Many2one('res.partner', string='Client créé', readonly=True)
    created_vehicle_id = fields.Many2one('gpl.vehicle', string='Véhicule créé', readonly=True)
    created_reservoir_id = fields.Many2one('stock.lot', string='Réservoir créé', readonly=True)
    created_installation_id = fields.Many2one('gpl.service.installation', string='Installation créée', readonly=True)

    @api.depends('reservoir_last_test_date')
    def _compute_next_test_date(self):
        """Calcule la date d'expiration du réservoir"""
        for wizard in self:
            if wizard.reservoir_last_test_date:
                # Récupérer la durée de validité depuis les paramètres (par défaut 5 ans)
                validity_years = int(self.env['ir.config_parameter'].sudo().get_param(
                    'gpl_fleet.reservoir_validity_years', '5'
                ))
                wizard.reservoir_next_test_date = wizard.reservoir_last_test_date + relativedelta(years=validity_years)
            else:
                wizard.reservoir_next_test_date = False

    @api.depends('reservoir_last_test_date')
    def _compute_next_test_date_days(self):
        """Calcule la date d'expiration du réservoir"""
        today = fields.Date.today()
        for wizard in self:
            if wizard.reservoir_last_test_date:
                # Récupérer la durée de validité depuis les paramètres (par défaut 5 ans)
                validity_years = int(self.env['ir.config_parameter'].sudo().get_param(
                    'gpl_fleet.reservoir_validity_years', '5'
                ))
                wizard.reservoir_days_until_next_test = (wizard.reservoir_next_test_date - today).days
            else:
                wizard.reservoir_days_until_next_test = False
    @api.depends('reservoir_manufacturing_date')
    def _compute_age_info(self):
        """Calcule l'âge et la durée de vie restante"""
        today = fields.Date.today()
        for record in self:
            if record.reservoir_manufacturing_date and record.is_gpl_reservoir:
                years_diff = (today - record.reservoir_manufacturing_date).days / 365.25
                record.reservoir_age_years = years_diff
                record.reservoir_remaining_life_years = max(0, 15 - years_diff)
                record.reservoir_remaining_life_years_pourcentage = (record.reservoir_remaining_life_years / 15) * 100
            else:
                record.reservoir_age_years = 0
                record.reservoir_remaining_life_years = 0
                record.reservoir_remaining_life_years_pourcentage = 0
    @api.onchange('client_id')
    def _onchange_client_id(self):
        """Pré-remplit les informations si client existant sélectionné"""
        if self.client_id:
            self.client_name = self.client_id.name
            self.client_phone = self.client_id.phone
            self.client_email = self.client_id.email
            self.client_street = self.client_id.street
            self.client_city = self.client_id.city
            self.client_zip = self.client_id.zip
            self.client_is_company = self.client_id.is_company

    @api.onchange('license_plate')
    def _onchange_license_plate(self):
        """Vérifie si le véhicule existe déjà - VERSION CORRIGÉE"""
        if self.license_plate:
            existing_vehicle = self.env['gpl.vehicle'].search([
                ('license_plate', '=', self.license_plate)
            ], limit=1)
            if existing_vehicle:
                # Utiliser warning au lieu de ValidationError pour ne pas bloquer
                return {
                    'warning': {
                        'title': _('Véhicule existant'),
                        'message': _('Un véhicule avec ce matricule existe déjà dans le système.\n'
                                     'Véhicule: %s\nClient: %s') % (
                                       existing_vehicle.name,
                                       existing_vehicle.client_id.name if existing_vehicle.client_id else 'Non défini'
                                   )
                    }
                }
    @api.onchange('reservoir_serial_number')
    def _onchange_reservoir_serial_number(self):
        """Vérifie si le réservoir existe déjà - VERSION CORRIGÉE"""
        if self.reservoir_serial_number:
            existing_reservoir = self.env['stock.lot'].search([
                ('name', '=', self.reservoir_serial_number),
                ('product_id.is_gpl_reservoir', '=', True)
            ], limit=1)
            if existing_reservoir:
                # Utiliser warning au lieu de ValidationError
                return {
                    'warning': {
                        'title': _('Réservoir existant'),
                        'message': _('Un réservoir avec ce numéro de série existe déjà dans le système.\n'
                                     'Réservoir: %s\nProduit: %s') % (
                                       existing_reservoir.name,
                                       existing_reservoir.product_id.name
                                   )
                    }
                }

    def action_next_step(self):
        """Passe à l'étape suivante après validation"""
        self.ensure_one()

        if self.step == 'client':
            # Valider les informations client
            if self.create_new_client and not self.client_name:
                raise ValidationError(_("Le nom du client est requis."))
            elif not self.create_new_client and not self.client_id:
                raise ValidationError(_("Veuillez sélectionner un client existant."))
            # Si la validation réussit, passer à l'étape suivante
            self.step = 'vehicle'

        elif self.step == 'vehicle':
            # Valider les informations du véhicule
            if not self.license_plate:
                raise ValidationError(_("Le matricule du véhicule est requis."))
            if not self.model_id:
                raise ValidationError(_("Le modèle du véhicule est requis."))
            # Si la validation réussit, passer à l'étape suivante
            self.step = 'reservoir'

        elif self.step == 'reservoir':
            # Valider les informations du réservoir
            if not self.reservoir_product_id:
                raise ValidationError(_("Le type de réservoir est requis."))
            if not self.reservoir_serial_number:
                raise ValidationError(_("Le numéro de série du réservoir est requis."))
            # Si la validation réussit, passer à l'étape suivante
            self.step = 'summary'

        return self._return_wizard_action()

    def action_previous_step(self):
        """Retourne à l'étape précédente"""
        self.ensure_one()

        if self.step == 'summary':
            self.step = 'reservoir'
        elif self.step == 'reservoir':
            self.step = 'vehicle'
        elif self.step == 'vehicle':
            self.step = 'client'

        return self._return_wizard_action()

    def _validate_client_info(self):
        """Valide les informations client"""
        if self.create_new_client:
            if not self.client_name:
                raise ValidationError(_('Le nom du client est requis.'))
        else:
            if not self.client_id:
                raise ValidationError(_('Veuillez sélectionner un client existant.'))

    def _validate_vehicle_info(self):
        """Valide les informations véhicule"""
        if not self.license_plate:
            raise ValidationError(_('Le matricule du véhicule est requis.'))
        if not self.model_id:
            raise ValidationError(_('Le modèle du véhicule est requis.'))

    def _validate_reservoir_info(self):
        """Valide les informations réservoir"""
        if not self.reservoir_product_id:
            raise ValidationError(_('Le type de réservoir est requis.'))
        if not self.reservoir_serial_number:
            raise ValidationError(_('Le numéro de série du réservoir est requis.'))

    def action_create_installation(self):
        """Crée tous les enregistrements nécessaires"""
        self.ensure_one()

        try:
            # 1. Créer ou récupérer le client
            client = self._create_or_get_client()

            # 2. Créer le véhicule
            vehicle = self._create_vehicle(client)

            # 3. Créer le réservoir
            reservoir = self._create_reservoir()

            # 4. Lier le réservoir au véhicule
            vehicle.write({'reservoir_lot_id': reservoir.id})
            reservoir.write({'vehicle_id': vehicle.id})

            # Sauvegarder les références
            self.write({
                'created_client_id': client.id,
                'created_vehicle_id': vehicle.id,
                'created_reservoir_id': reservoir.id
            })

            return self._show_success_message()

        except Exception as e:
            raise UserError(_('Erreur lors de la création: %s') % str(e))

    def _create_or_get_client(self):
        """Crée un nouveau client ou récupère un existant"""
        if self.create_new_client:
            client_vals = {
                'name': self.client_name,
                'phone': self.client_phone,
                'email': self.client_email,
                'street': self.client_street,
                'city': self.client_city,
                'zip': self.client_zip,
                'is_company': self.client_is_company,
                'is_gpl_client': True,
                'customer_rank': 1,  # Marquer comme client
            }
            return self.env['res.partner'].create(client_vals)
        else:
            # Marquer le client existant comme client GPL
            self.client_id.write({'is_gpl_client': True})
            return self.client_id

    def _create_vehicle(self, client):
        """Crée le véhicule"""
        vehicle_vals = {
            'license_plate': self.license_plate,
            'vin_sn': self.vin_sn,
            'model_id': self.model_id.id,
            'model_year': self.model_year,
            'acquisition_date': self.acquisition_date,
            'client_id': client.id,
            'status_id': self.env.ref('gpl_fleet.vehicle_status_termine').id,
            'next_service_type': False,
        }
        return self.env['gpl.vehicle'].create(vehicle_vals)

    def _create_reservoir(self):
        """Crée le lot de réservoir"""
        reservoir_vals = {
            'name': self.reservoir_serial_number,
            'product_id': self.reservoir_product_id.id,
            'certification_number': self.reservoir_certification_number,
            'manufacturing_date': self.reservoir_manufacturing_date,
            'company_id': self.env.company.id,
        }
        return self.env['stock.lot'].create(reservoir_vals)

    def _create_installation(self, vehicle, reservoir):
        """Crée l'enregistrement d'installation"""
        installation_vals = {
            'name': self.env['ir.sequence'].next_by_code('gpl.service.installation') or 'New',
            'vehicle_id': vehicle.id,
            'reservoir_lot_id': reservoir.id,
            'date_service': self.installation_date,
            'date_completion': self.installation_date,
            'state': 'done',  # Installation déjà terminée
            'notes': self._build_installation_notes(),
        }

        # Ajouter un technicien par défaut si configuré
        default_technician_ids = self._get_default_technicians()
        if default_technician_ids:
            installation_vals['technician_ids'] = [(6, 0, default_technician_ids)]

        installation = self.env['gpl.service.installation'].create(installation_vals)

        # Créer une ligne pour le réservoir
        self.env['gpl.installation.line'].create({
            'installation_id': installation.id,
            'product_id': self.reservoir_product_id.id,
            'product_uom_qty': 1.0,
            'lot_id': reservoir.id,
        })

        return installation

    def _build_installation_notes(self):
        """Construit les notes d'installation"""
        notes = [
            "=== INSTALLATION EXISTANTE ENREGISTRÉE ===",
            f"Date d'enregistrement: {fields.Date.today()}",
        ]

        if self.external_installer:
            notes.append(f"Installateur externe: {self.external_installer}")

        if self.external_certificate:
            notes.append(f"Certificat externe: {self.external_certificate}")

        if self.installation_notes:
            notes.append(f"Notes: {self.installation_notes}")

        return "\n".join(notes)

    def _get_default_technicians(self):
        """Récupère les techniciens par défaut"""
        try:
            import json
            default_technician_ids_json = self.env['ir.config_parameter'].sudo().get_param(
                'gpl_fleet.default_technician_ids_json', '[]'
            )
            return json.loads(default_technician_ids_json)
        except:
            return []

    def _show_success_message(self):
        """Affiche le message de succès et propose les actions"""
        message = _(
            "Installation existante enregistrée avec succès !\n\n"
            "• Client: %s\n"
            "• Véhicule: %s\n"
            "• Réservoir: %s"
        ) % (
                      self.created_client_id.name,
                      self.created_vehicle_id.name,
                      self.created_reservoir_id.name
                  )

        return {
            'name': _('Enregisrement créée'),
            'type': 'ir.actions.act_window',
            'res_model': 'gpl.existing.installation.success',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_message': message,
                'default_vehicle_id': self.created_vehicle_id.id,
                'default_client_id': self.created_client_id.id,
            }
        }

    def _return_wizard_action(self):
        """Retourne l'action pour rester dans le wizard"""
        return {
            'name': _('Enregistrer installation existante'),
            'type': 'ir.actions.act_window',
            'res_model': 'gpl.existing.installation.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    @api.onchange('create_new_client')
    def _onchange_create_new_client(self):
        """Réinitialise les champs appropriés lorsque le type de client change"""
        if self.create_new_client == 'new':
            # Si on passe à "Nouveau client", on efface le client sélectionné
            self.client_id = False
        else:
            # Si on passe à "Client existant", on efface les champs de nouveau client
            self.client_name = False
            self.client_phone = False
            self.client_email = False
            self.client_street = False
            self.client_city = False
            self.client_zip = False
            self.client_is_company = False


class GplExistingInstallationSuccess(models.TransientModel):
    _name = 'gpl.existing.installation.success'
    _description = 'Message de succès pour installation existante'

    message = fields.Text(string='Message', readonly=True)
    vehicle_id = fields.Many2one('gpl.vehicle', string='Véhicule créé')
    client_id = fields.Many2one('res.partner', string='Client')

    def action_view_vehicle(self):
        """Ouvre le véhicule créé"""
        return {
            'name': _('Véhicule'),
            'type': 'ir.actions.act_window',
            'res_model': 'gpl.vehicle',
            'res_id': self.vehicle_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_reservoir(self):
        """Ouvre le réservoir créé"""
        return {
            'name': _('Réservoir'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.lot',
            'res_id': self.reservoir_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_client(self):
        """Ouvre la fiche client"""
        return {
            'name': _('Client'),
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': self.client_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
