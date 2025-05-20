from odoo import models, fields, api, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta


class GplReservoirTesting(models.Model):
    _name = 'gpl.reservoir.testing'
    _description = 'Réépreuve Réservoir GPL'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Référence", required=True, default="New", copy=False, readonly=True)
    vehicle_id = fields.Many2one('gpl.vehicle', string="Véhicule", required=True)
    client_id = fields.Many2one(related='vehicle_id.client_id', string="Client", store=True)
    date_testing = fields.Date(string="Date de réépreuve", default=fields.Date.today)
    technician_id = fields.Many2one('hr.employee', string="Injénieur")

    reservoir_lot_id = fields.Many2one(related='vehicle_id.reservoir_lot_id', string="Réservoir", readonly=False,
                                       store=True)
    old_certification_number = fields.Char(related='reservoir_lot_id.certification_number',
                                           string="Ancien numéro certification")
    old_certification_date = fields.Date(related='reservoir_lot_id.certification_date',
                                         string="Ancienne date certification")

    new_certification_number = fields.Char(string="Nouveau numéro certification")
    new_certification_date = fields.Date(string="Nouvelle date certification", default=fields.Date.today)
    new_expiry_date = fields.Date(string="Nouvelle date d'expiration", compute='_compute_new_expiry_date', store=True)

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('scheduled', 'Planifié'),
        ('in_progress', 'En cours'),
        ('passed', 'Validé'),
        ('failed', 'Refusé'),
        ('canceled', 'Annulé')
    ], string="État", default='draft', tracking=True)

    notes = fields.Text(string="Notes et observations")

    can_schedule = fields.Boolean(compute='_compute_button_visibility')
    can_start = fields.Boolean(compute='_compute_button_visibility')
    can_validate = fields.Boolean(compute='_compute_button_visibility')
    can_fail = fields.Boolean(compute='_compute_button_visibility')
    can_cancel = fields.Boolean(compute='_compute_button_visibility')

    @api.depends('state')
    def _compute_button_visibility(self):
        for record in self:
            record.can_schedule = record.state == 'draft'
            record.can_start = record.state == 'scheduled'
            record.can_validate = record.state == 'in_progress'
            record.can_fail = record.state == 'in_progress'
            record.can_cancel = record.state in ('draft', 'scheduled', 'in_progress')
    @api.depends('new_certification_date')
    def _compute_new_expiry_date(self):
        for record in self:
            if record.new_certification_date:
                record.new_expiry_date = record.new_certification_date + relativedelta(years=5)
            else:
                record.new_expiry_date = False

    @api.model_create_multi
    def create(self, vals_list):
        """
        Create method updated for Odoo 17 compatibility.
        Handles batch creation with vals_list parameter.
        """
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('gpl.reservoir.testing') or 'New'
        return super(GplReservoirTesting, self).create(vals_list)

    def action_schedule(self):
        self.write({'state': 'scheduled'})

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_validate(self):
        self.ensure_one()
        if not self.new_certification_number or not self.new_certification_date:
            raise UserError(_("Veuillez saisir le nouveau numéro et la nouvelle date de certification."))

        # Mettre à jour le lot de réservoir
        if self.reservoir_lot_id:
            self.reservoir_lot_id.write({
                'certification_number': self.new_certification_number,
                'certification_date': self.new_certification_date
            })

        self.write({'state': 'passed'})

        # Mettre à jour le véhicule
        completed_status = self.env.ref('gpl_fleet.vehicle_status_termine', raise_if_not_found=False)
        if completed_status:
            self.vehicle_id.write({
                'status_id': completed_status.id,
                'next_service_type': False
            })

    def action_fail(self):
        self.write({'state': 'failed'})

    def action_cancel(self):
        self.write({'state': 'canceled'})
