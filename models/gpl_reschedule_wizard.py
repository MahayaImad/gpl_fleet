from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta


class GplVehicleRescheduleWizard(models.TransientModel):
    _name = 'gpl.vehicle.reschedule.wizard'
    _description = 'Assistant de reprogrammation de rendez-vous'

    vehicle_id = fields.Many2one('gpl.vehicle', string='Véhicule', required=True)
    current_date = fields.Datetime(string='Rendez-vous actuel', readonly=True)
    new_date = fields.Datetime(string='Nouveau rendez-vous', required=True)
    new_technician_ids = fields.Many2many('hr.employee', string='Nouveaux techniciens')
    reason = fields.Text(string='Raison du changement')
    notify_client = fields.Boolean(string='Notifier le client', default=True)

    # Champs calculés pour affichage
    service_type = fields.Selection(related='vehicle_id.next_service_type', readonly=True)
    client_id = fields.Many2one(related='vehicle_id.client_id', readonly=True)
    estimated_duration = fields.Float(related='vehicle_id.estimated_duration', readonly=True)

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        vehicle_id = self.env.context.get('default_vehicle_id')
        if vehicle_id:
            vehicle = self.env['gpl.vehicle'].browse(vehicle_id)
            res.update({
                'current_date': vehicle.appointment_date,
                'new_technician_ids': [(6, 0, vehicle.assigned_technician_ids.ids)],
            })
        return res

    def action_reschedule(self):
        """Effectue la reprogrammation"""
        self.ensure_one()

        if not self.new_date:
            raise UserError(_("Veuillez sélectionner une nouvelle date."))

        # Vérifier que la nouvelle date est dans le futur
        if self.new_date <= fields.Datetime.now():
            raise UserError(_("La nouvelle date doit être dans le futur."))

        # Mettre à jour le véhicule
        values = {
            'appointment_date': self.new_date,
        }

        if self.new_technician_ids:
            values['assigned_technician_ids'] = [(6, 0, self.new_technician_ids.ids)]

        self.vehicle_id.write(values)

        # Enregistrer l'historique
        message = f"""Rendez-vous reprogrammé:
        • Ancienne date: {self.current_date}
        • Nouvelle date: {self.new_date}"""

        if self.new_technician_ids:
            technician_names = ', '.join(self.new_technician_ids.mapped('name'))
            message += f"\n• Nouveaux techniciens: {technician_names}"

        if self.reason:
            message += f"\n• Raison: {self.reason}"

        self.vehicle_id.message_post(body=message)

        # Notifier le client si demandé
        if self.notify_client and self.vehicle_id.client_id:
            self._notify_client()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Rendez-vous reprogrammé'),
                'message': _('Le rendez-vous pour %s a été reprogrammé avec succès.') % self.vehicle_id.name,
                'type': 'success',
            }
        }

    def _notify_client(self):
        """Envoie une notification au client"""
        template = self.env.ref('gpl_fleet.email_template_appointment_reschedule', raise_if_not_found=False)
        if template:
            template.send_mail(self.vehicle_id.id, force_send=True)
        else:
            # Créer une activité de rappel pour appeler le client
            self.env['mail.activity'].create({
                'activity_type_id': self.env.ref('mail.mail_activity_data_call').id,
                'summary': f'Appeler client - RDV reprogrammé',
                'note': f'''Appeler {self.vehicle_id.client_id.name} pour l'informer du changement de RDV:

                Véhicule: {self.vehicle_id.name}
                Ancien RDV: {self.current_date}
                Nouveau RDV: {self.new_date}
                Téléphone: {self.vehicle_id.client_phone or 'Non renseigné'}

                Raison: {self.reason or 'Non spécifiée'}''',
                'res_model_id': self.env['ir.model']._get('gpl.vehicle').id,
                'res_id': self.vehicle_id.id,
                'user_id': self.env.uid,
                'date_deadline': fields.Date.today(),
            })


class GplQuickAppointmentWizard(models.TransientModel):
    _name = 'gpl.quick.appointment.wizard'
    _description = 'Assistant de création rapide de rendez-vous'

    vehicle_id = fields.Many2one('gpl.vehicle', string='Véhicule', required=True)
    appointment_date = fields.Datetime(string='Date du rendez-vous', required=True,
                                       default=lambda self: fields.Datetime.now())
    service_type = fields.Selection([
        ('installation', 'Installation GPL'),
        ('repair', 'Réparation'),
        ('inspection', 'Contrôle Technique/Validation'),
        ('testing', 'Réépreuve Réservoir'),
    ], string='Type de service', required=True)
    technician_ids = fields.Many2many('hr.employee', string='Techniciens assignés')


    def action_create_appointment(self):
        """Crée le rendez-vous"""
        self.ensure_one()

        values = {
            'appointment_date': self.appointment_date,
            'next_service_type': self.service_type,
        }

        if self.technician_ids:
            values['assigned_technician_ids'] = [(6, 0, self.technician_ids.ids)]

        # Mettre à jour le statut
        planned_status = self.env.ref('gpl_fleet.vehicle_status_planifie', raise_if_not_found=False)
        if planned_status:
            values['status_id'] = planned_status.id

        self.vehicle_id.write(values)

        # Message de confirmation
        message = f"""Nouveau rendez-vous programmé:
        • Date: {self.appointment_date}
        • Service: {dict(self._fields['service_type'].selection)[self.service_type]}"""

        if self.technician_ids:
            technician_names = ', '.join(self.technician_ids.mapped('name'))
            message += f"\n• Techniciens: {technician_names}"

        # if self.notes:
        #     message += f"\n• Notes: {self.notes}"

        self.vehicle_id.message_post(body=message)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Rendez-vous créé'),
                'message': _('Le rendez-vous pour %s a été programmé avec succès.') % self.vehicle_id.name,
                'type': 'success',
            }
        }
