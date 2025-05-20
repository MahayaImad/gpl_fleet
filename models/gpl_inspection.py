from odoo import models, fields, api, _
from odoo.exceptions import UserError


class GplInspection(models.Model):
    _name = 'gpl.inspection'
    _description = 'Contrôle Technique GPL'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Référence", required=True, default="New", copy=False, readonly=True)
    vehicle_id = fields.Many2one('gpl.vehicle', string="Véhicule", required=True)
    client_id = fields.Many2one(related='vehicle_id.client_id', string="Client", store=True)
    date_inspection = fields.Date(string="Date du contrôle", default=fields.Date.today)
    inspector_id = fields.Many2one('hr.employee', string="Inspecteur/Ingénieur")

    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('scheduled', 'Planifié'),
        ('in_progress', 'En cours'),
        ('passed', 'Validé'),
        ('failed', 'Refusé'),
        ('canceled', 'Annulé')
    ], string="État", default='draft', tracking=True)

    notes = fields.Text(string="Notes et observations")
    validation_certificate = fields.Char(string="Numéro de certificat", copy=False)

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

    @api.model_create_multi
    def create(self, vals_list):
        """
        Create method updated for Odoo 17 compatibility.
        Handles batch creation with vals_list parameter.
        """
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('gpl.inspection') or 'New'
        return super(GplInspection, self).create(vals_list)

    def action_schedule(self):
        self.write({'state': 'scheduled'})

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_validate(self):
        self.ensure_one()
        if not self.validation_certificate:
            raise UserError(_("Veuillez saisir un numéro de certificat de validation."))
        self.write({'state': 'passed'})

        # Mettre à jour le véhicule
        completed_status = self.env.ref('gpl_fleet.vehicle_status_termine', raise_if_not_found=False)
        if completed_status:
            self.vehicle_id.write({
                'status_id': completed_status.id,
                'next_service_type': False,
                'validation_certificate': self.validation_certificate,
                'engineer_validation_date': fields.Date.today()
            })

    def action_fail(self):
        self.write({'state': 'failed'})

    def action_cancel(self):
        self.write({'state': 'canceled'})
