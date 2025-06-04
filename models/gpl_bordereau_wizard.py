from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime


class GplBordereauWizard(models.TransientModel):
    _name = 'gpl.bordereau.wizard'
    _description = 'Assistant de génération de bordereau d\'envoi'

    date_from = fields.Date(
        string='Date de début',
        default=lambda self: fields.Date.today().replace(day=1),
        required=True,
        help="Date de début de la période à inclure dans le bordereau"
    )
    date_to = fields.Date(
        string='Date de fin',
        default=fields.Date.today,
        required=True,
        help="Date de fin de la période à inclure dans le bordereau"
    )
    only_completed = fields.Boolean(
        string='Seulement les installations terminées',
        default=True,
        help="Inclure uniquement les installations avec l'état 'Terminé'"
    )
    exclude_already_sent = fields.Boolean(
        string='Exclure déjà envoyées',
        default=True,
        help="Exclure les installations déjà incluses dans un bordereau précédent"
    )
    installation_ids = fields.Many2many(
        'gpl.service.installation',
        string='Installations à inclure',
        compute='_compute_installation_ids',
        store=False,
        help="Liste des installations qui seront incluses dans le bordereau"
    )
    installation_count = fields.Integer(
        string='Nombre d\'installations',
        compute='_compute_installation_ids',
        help="Nombre total d'installations sélectionnées"
    )
    already_sent_count = fields.Integer(
        string='Déjà envoyées',
        compute='_compute_installation_ids',
        help="Nombre d'installations déjà envoyées dans la période"
    )

    @api.depends('date_from', 'date_to', 'only_completed', 'exclude_already_sent')
    def _compute_installation_ids(self):
        """Calcule la liste des installations à inclure selon les critères"""
        for wizard in self:
            # Construire le domaine de recherche
            domain = [
                ('date_service', '>=', wizard.date_from),
                ('date_service', '<=', wizard.date_to)
            ]

            # Filtrer par état si demandé
            if wizard.only_completed:
                domain.append(('state', '=', 'done'))

            # Exclure celles déjà envoyées si demandé
            if wizard.exclude_already_sent:
                domain.append(('sent_in_bordereau', '=', False))

            # Rechercher les installations correspondantes
            installations = self.env['gpl.service.installation'].search(domain, order='date_service asc')
            wizard.installation_ids = installations
            wizard.installation_count = len(installations)

            # Compter celles déjà envoyées (pour information)
            already_sent_domain = [
                ('date_service', '>=', wizard.date_from),
                ('date_service', '<=', wizard.date_to),
                ('sent_in_bordereau', '=', True)
            ]
            if wizard.only_completed:
                already_sent_domain.append(('state', '=', 'done'))

            wizard.already_sent_count = self.env['gpl.service.installation'].search_count(
                already_sent_domain
            )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        """Vérifie que les dates sont cohérentes"""
        for wizard in self:
            if wizard.date_from > wizard.date_to:
                raise UserError(_("La date de début ne peut pas être postérieure à la date de fin."))

    def action_generate_bordereau(self):
        """Génère le bordereau et marque les installations comme envoyées"""
        self.ensure_one()

        if not self.installation_ids:
            raise UserError(_("Aucune installation à inclure dans le bordereau."))

        # Marquer les installations comme envoyées
        self.installation_ids.mark_as_sent_in_bordereau()

        # Préparer les données pour le rapport
        data = {
            'ids': self.installation_ids.ids,
            'model': 'gpl.service.installation',
            'form': {
                'date_from': self.date_from,
                'date_to': self.date_to,
                'installation_count': self.installation_count,
                'generation_date': fields.Datetime.now(),
            }
        }

        # Générer le rapport PDF
        return {
            'type': 'ir.actions.report',
            'report_name': 'gpl_fleet.report_gpl_bordereau_envoi',
            'report_type': 'qweb-pdf',
            'data': data,
            'context': self.env.context,
            'target': 'self',
        }

    def action_preview_installations(self):
        """Prévisualise les installations qui seront incluses"""
        self.ensure_one()

        return {
            'name': _('Installations à inclure dans le bordereau'),
            'type': 'ir.actions.act_window',
            'res_model': 'gpl.service.installation',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.installation_ids.ids)],
            'context': {
                'search_default_group_client': 1,
                'create': False,
                'edit': False,
            },
            'target': 'current',
        }
