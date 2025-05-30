from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
from dateutil.relativedelta import relativedelta


class GplSetupWizard(models.TransientModel):
    _name = 'gpl.setup.wizard'
    _description = 'Assistant de configuration initiale GPL'

    # Étapes du wizard
    step = fields.Selection([
        ('welcome', 'Bienvenue'),
        ('company_info', 'Informations Entreprise'),
        ('technicians', 'Techniciens'),
        ('products', 'Produits Réservoirs'),
        ('settings', 'Paramètres'),
        ('complete', 'Terminé')
    ], string='Étape', default='welcome')

    # === INFORMATIONS ENTREPRISE ===
    company_name = fields.Char(string='Nom de l\'entreprise', related='company_id.name', readonly=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    has_gpl_license = fields.Boolean(string='Possède une licence d\'installation GPL')
    license_number = fields.Char(string='Numéro de licence')
    certification_authority = fields.Char(string='Organisme certificateur')

    # === TECHNICIENS ===
    create_technicians = fields.Boolean(string='Créer des techniciens', default=True)
    technician_names = fields.Text(
        string='Noms des techniciens',
        placeholder="Saisissez un nom par ligne:\nMed Ali\nOmar Khaled",
        help="Saisissez un nom de technicien par ligne"
    )
    default_technician_id = fields.Many2one('hr.employee', string='Technicien par défaut')

    # === PRODUITS RÉSERVOIRS ===
    create_sample_products = fields.Boolean(string='Créer des produits réservoirs types', default=True)
    reservoir_types = fields.Text(
        string='Types de réservoirs',
        default="""Réservoir GPL 40L Cylindrique
Réservoir GPL 60L Cylindrique
Réservoir GPL 80L Toroïdal
Réservoir GPL 100L Cylindrique""",
        help="Un type par ligne au format: Nom Capacité Forme"
    )

    # === PARAMÈTRES ===
    use_simplified_flow = fields.Boolean(string='Activer le flux simplifié', default=True)
    auto_invoice = fields.Boolean(string='Facturation automatique', default=False)
    reservoir_validity_years = fields.Integer(string='Validité réservoirs (années)', default=5)
    warning_months = fields.Integer(string='Alerte avant expiration (mois)', default=6)
    enable_alerts = fields.Boolean(string='Activer les alertes', default=True)

    # === DONNÉES D'EXEMPLE ===
    create_sample_data = fields.Boolean(string='Créer des données d\'exemple', default=False)
    sample_vehicles_count = fields.Integer(string='Nombre de véhicules d\'exemple', default=5)
    sample_reservoirs_count = fields.Integer(string='Nombre de réservoirs d\'exemple', default=10)

    # === STATUT DE CRÉATION ===
    created_technicians_count = fields.Integer(readonly=True)
    created_products_count = fields.Integer(readonly=True)
    created_vehicles_count = fields.Integer(readonly=True)
    created_reservoirs_count = fields.Integer(readonly=True)

    def action_next_step(self):
        """Passe à l'étape suivante"""
        self.ensure_one()

        current_step = self.step

        if current_step == 'welcome':
            self.step = 'company_info'
        elif current_step == 'company_info':
            self._validate_company_info()
            self.step = 'technicians'
        elif current_step == 'technicians':
            self.step = 'products'
        elif current_step == 'products':
            self.step = 'settings'
        elif current_step == 'settings':
            self._apply_configuration()
            self.step = 'complete'

        return self._return_wizard_action()

    def action_previous_step(self):
        """Retourne à l'étape précédente"""
        self.ensure_one()

        current_step = self.step

        if current_step == 'complete':
            self.step = 'settings'
        elif current_step == 'settings':
            self.step = 'products'
        elif current_step == 'products':
            self.step = 'technicians'
        elif current_step == 'technicians':
            self.step = 'company_info'
        elif current_step == 'company_info':
            self.step = 'welcome'

        return self._return_wizard_action()

    def _validate_company_info(self):
        """Valide les informations entreprise"""
        if self.has_gpl_license and not self.license_number:
            raise ValidationError(_("Veuillez saisir le numéro de licence GPL."))

    def _apply_configuration(self):
        """Applique toute la configuration"""
        # 1. Créer les techniciens
        if self.create_technicians and self.technician_names:
            self._create_technicians()

        # 2. Créer les produits réservoirs
        if self.create_sample_products and self.reservoir_types:
            self._create_reservoir_products()

        # 3. Appliquer les paramètres
        self._apply_settings()

        # 4. Créer les données d'exemple si demandé
        if self.create_sample_data:
            self._create_sample_data()

    def _create_technicians(self):
        """Crée les techniciens"""
        names = [name.strip() for name in self.technician_names.split('\n') if name.strip()]
        created_count = 0

        for name in names:
            # Vérifier si le technicien existe déjà
            existing = self.env['hr.employee'].search([('name', '=', name)], limit=1)
            if not existing:
                employee = self.env['hr.employee'].create({
                    'name': name,
                    'job_title': 'Technicien GPL',
                    'company_id': self.company_id.id,
                })
                created_count += 1

                # Définir le premier comme technicien par défaut
                if not self.default_technician_id:
                    self.default_technician_id = employee

        self.created_technicians_count = created_count

    def _create_reservoir_products(self):
        """Crée les produits réservoirs types"""
        lines = [line.strip() for line in self.reservoir_types.split('\n') if line.strip()]
        created_count = 0

        for line in lines:
            # Parser la ligne pour extraire nom, capacité, forme
            parts = line.split()
            if len(parts) >= 3:
                # Extraire la capacité (nombre suivi de L)
                capacity = 0
                shape = 'cylindrical'

                for part in parts:
                    if 'L' in part and any(c.isdigit() for c in part):
                        try:
                            capacity = float(part.replace('L', ''))
                        except:
                            pass
                    elif part.lower() in ['toroidal', 'toroïdal']:
                        shape = 'toroidal'
                    elif part.lower() == 'autre':
                        shape = 'other'

                # Vérifier si le produit existe déjà
                existing = self.env['product.template'].search([
                    ('name', '=', line),
                    ('is_gpl_reservoir', '=', True)
                ], limit=1)

                if not existing:
                    self.env['product.template'].create({
                        'name': line,
                        'is_gpl_reservoir': True,
                        'type': 'product',
                        'tracking': 'serial',
                        'capacity': capacity,
                        'shape': shape,
                        'sale_ok': True,
                        'purchase_ok': True,
                    })
                    created_count += 1

        self.created_products_count = created_count

    def _apply_settings(self):
        """Applique les paramètres de configuration"""
        IrConfigParameter = self.env['ir.config_parameter'].sudo()

        # Paramètres d'installation
        IrConfigParameter.set_param('gpl_fleet.simplified_flow', str(self.use_simplified_flow))
        IrConfigParameter.set_param('gpl_fleet.auto_invoice', str(self.auto_invoice))

        # Paramètres des réservoirs
        IrConfigParameter.set_param('gpl_fleet.reservoir_validity_years', str(self.reservoir_validity_years))
        IrConfigParameter.set_param('gpl_fleet.reservoir_warning_months', str(self.warning_months))
        IrConfigParameter.set_param('gpl_fleet.enable_reservoir_alerts', str(self.enable_alerts))

        # Technicien par défaut
        if self.default_technician_id:
            IrConfigParameter.set_param('gpl_fleet.use_default_technician', 'True')
            import json
            IrConfigParameter.set_param('gpl_fleet.default_technician_ids_json',
                                        json.dumps([self.default_technician_id.id]))

        # Informations entreprise
        if self.has_gpl_license and self.license_number:
            IrConfigParameter.set_param('gpl_fleet.company_license_number', self.license_number)
            if self.certification_authority:
                IrConfigParameter.set_param('gpl_fleet.certification_authority', self.certification_authority)

    def _create_sample_data(self):
        """Crée des données d'exemple"""
        from datetime import date
        import random

        # Créer des clients d'exemple
        sample_clients = []
        for i in range(3):
            client = self.env['res.partner'].create({
                'name': f'Client GPL Example {i + 1}',
                'is_company': True,
                'customer_rank': 1,
                'is_gpl_client': True,
                'phone': f'0123456{i:03d}',
                'email': f'client{i + 1}@example.com',
            })
            sample_clients.append(client)

        # Créer des modèles de véhicules d'exemple
        brand = self.env['fleet.vehicle.model.brand'].search([('name', '=', 'Exemple')], limit=1)
        if not brand:
            brand = self.env['fleet.vehicle.model.brand'].create({'name': 'Exemple'})

        models = []
        for model_name in ['Citadine', 'Berline', 'SUV']:
            model = self.env['fleet.vehicle.model'].create({
                'brand_id': brand.id,
                'name': model_name,
                'vehicle_type': 'car'
            })
            models.append(model)

        # Créer des véhicules d'exemple
        created_vehicles = 0
        for i in range(self.sample_vehicles_count):
            self.env['gpl.vehicle'].create({
                'license_plate': f'EX-{i + 1:03d}-GP',
                'model_id': random.choice(models).id,
                'client_id': random.choice(sample_clients).id,
                'vin_sn': f'EXAMPLE{i + 1:010d}',
                'model_year': str(random.randint(2015, 2023)),
                'acquisition_date': date.today() - relativedelta(days=random.randint(30, 1000)),
            })
            created_vehicles += 1

        # Créer des réservoirs d'exemple
        products = self.env['product.template'].search([('is_gpl_reservoir', '=', True)], limit=5)
        created_reservoirs = 0

        if products:
            for i in range(self.sample_reservoirs_count):
                product = random.choice(products)
                product_product = product.product_variant_ids[0]

                # Dates aléatoires
                months_ago = random.randint(6, 60)
                manufacturing_date = date.today() - relativedelta(months=months_ago)
                certification_date = manufacturing_date + relativedelta(months=random.randint(3, 12))

                self.env['stock.lot'].create({
                    'name': f'EXPL-{i + 1:04d}',
                    'product_id': product_product.id,
                    'manufacturing_date': manufacturing_date,
                    'certification_date': certification_date,
                    'certification_number': f'CERT-EX-{i + 1:04d}',
                })
                created_reservoirs += 1

        self.created_vehicles_count = created_vehicles
        self.created_reservoirs_count = created_reservoirs

    def action_finish_setup(self):
        """Termine la configuration et ferme l'assistant"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Configuration terminée'),
                'message': _('Votre système GPL est maintenant configuré et prêt à être utilisé !'),
                'type': 'success',
                'sticky': True,
            }
        }

    def action_open_dashboard(self):
        """Ouvre le dashboard après configuration"""
        return {
            'name': _('Dashboard GPL'),
            'type': 'ir.actions.act_window',
            'res_model': 'gpl.reservoir.dashboard',
            'view_mode': 'form',
            'target': 'current',
        }

    def _return_wizard_action(self):
        """Retourne l'action pour rester dans le wizard"""
        return {
            'name': _('Configuration GPL - Assistant'),
            'type': 'ir.actions.act_window',
            'res_model': 'gpl.setup.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def is_system_configured(self):
        """Vérifie si le système GPL est déjà configuré"""
        # Vérifier s'il y a des techniciens, produits réservoirs, etc.
        has_technicians = self.env['hr.employee'].search_count([]) > 0
        has_reservoir_products = self.env['product.template'].search_count([('is_gpl_reservoir', '=', True)]) > 0
        has_settings = self.env['ir.config_parameter'].sudo().get_param('gpl_fleet.simplified_flow') is not None

        return has_technicians and has_reservoir_products and has_settings

    @api.model
    def _valid_field_parameter(self, field, name):
        # Allow 'placeholder' parameter for all field types
        if name == 'placeholder':
            return True
        return super()._valid_field_parameter(field, name)
