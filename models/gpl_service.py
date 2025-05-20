import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta
import logging
_logger = logging.getLogger(__name__)
class GplService(models.Model):
    _name = 'gpl.service.installation'
    _description = 'Installation GPL'
    _inherit = ['mail.thread', 'mail.activity.mixin']  # Adding mail features for chatter

    name = fields.Char(string="Nom du service", required=True, default="New", copy=False, readonly=True)

    reservoir_lot_id = fields.Many2one('stock.lot', string="Suivi Réservoir GPL",
                                       domain="[('product_id.is_gpl_reservoir', '=', True)]", tracking=True)

    # Ces champs peuvent être définis comme related pour afficher les informations du lot
    certification_number = fields.Char(related="reservoir_lot_id.certification_number",
                                       string="N° certification", readonly=True)
    certification_date = fields.Date(related="reservoir_lot_id.certification_date",
                                     string="Date certification", readonly=True)
    expiry_date = fields.Date(related="reservoir_lot_id.expiry_date",
                              string="Date expiration", readonly=True)
    reservoir_state = fields.Selection(related="reservoir_lot_id.state",
                                       string="État du réservoir", readonly=True)

    # Le champ serial_number n'est plus nécessaire car on utilise directement le champ 'name' du stock.lot
    # Si vous voulez le garder pour compatibilité:
    serial_number = fields.Char(related="reservoir_lot_id.name", string="N° série réservoir", readonly=True)

    date_service = fields.Date(string="Date du service")
    date_planned = fields.Date(string="Date planifiée")
    date_completion = fields.Date(string="Date de finalisation")

    vehicle_id = fields.Many2one('gpl.vehicle', string="Vehicule")
    client_id = fields.Many2one(related='vehicle_id.client_id', string="Client", store=True)
    technician_id = fields.Many2one('hr.employee', string="Technicien")

    state = fields.Selection([
        ('draft', 'Préparation'),
        ('planned', 'Planifié'),
        ('in_progress', 'En cours'),
        ('done', 'Terminé'),
        ('cancel', 'Annulé')
    ], string="État", default='draft', tracking=True)

    installation_line_ids = fields.One2many('gpl.installation.line', 'installation_id', string="Produits utilisés")
    picking_id = fields.Many2one('stock.picking', string="Bon de livraison")
    invoice_id = fields.Many2one('account.move', string="Facture")
    notes = fields.Text(string="Notes")

    # Statistiques pour le dashboard
    products_count = fields.Integer(string="Nombre de produits", compute="_compute_products_count")
    total_amount = fields.Float(string="Montant total", compute="_compute_total_amount")
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    sale_order_id = fields.Many2one('sale.order', string="Bon de commande client", copy=False)

    # Nouveau champ pour indiquer si le flux simplifié est utilisé
    use_simplified_flow = fields.Boolean(string="Flux simplifié", compute='_compute_use_simplified_flow')

    @api.depends('company_id')
    def _compute_use_simplified_flow(self):
        # Récupérer les paramètres de configuration
        simplified_flow = self.env['ir.config_parameter'].sudo().get_param('gpl_fleet.simplified_flow',
                                                                           'False').lower() == 'true'
        for record in self:
            record.use_simplified_flow = simplified_flow
    @api.depends('installation_line_ids')
    def _compute_products_count(self):
        for record in self:
            record.products_count = len(record.installation_line_ids)


    @api.depends('installation_line_ids', 'installation_line_ids.product_id', 'installation_line_ids.product_uom_qty')
    def _compute_total_amount(self):
        for record in self:
            total = 0.0
            for line in record.installation_line_ids:
                total += line.product_id.list_price * line.product_uom_qty
            record.total_amount = total

    @api.model
    def create(self, vals):
        if isinstance(vals, dict) and vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('gpl.service.installation') or 'New'

        # Si le véhicule contient un réservoir, l'assigner dès la création
        if vals.get('vehicle_id'):
            vehicle = self.env['gpl.vehicle'].browse(vals['vehicle_id'])
            if vehicle and vehicle.reservoir_lot_id:
                vals['reservoir_lot_id'] = vehicle.reservoir_lot_id.id

        return super().create(vals)

    @api.onchange('vehicle_id')
    def onchange_vehicle_id(self):
        if self.vehicle_id:
            # Si le véhicule a un réservoir, l'assigner à l'installation
            if self.vehicle_id.reservoir_lot_id:
                self.reservoir_lot_id = self.vehicle_id.reservoir_lot_id.id

        # Conserver le code existant - définir le client à partir du véhicule
        if self.vehicle_id and self.vehicle_id.client_id:
            self.client_id = self.vehicle_id.client_id

    def action_validate_preparation(self):
        for record in self:
            if not record.vehicle_id:
                raise UserError(_("Veuillez sélectionner un véhicule avant de continuer."))
            if not record.technician_id:
                raise UserError(_("Veuillez assigner un technicien avant de continuer."))
            if not record.date_service:
                raise UserError(_("Veuillez définir une date de service avant de continuer."))

            # Créer un bon de commande client si ce n'est pas déjà fait
            if not record.sale_order_id and record.installation_line_ids:
                self._create_sale_order()

            # Vérifier si le flux simplifié est activé
            simplified_flow = self.env['ir.config_parameter'].sudo().get_param('gpl_fleet.simplified_flow',
                                                                               'False').lower() == 'true'

            if simplified_flow:
                # En mode simplifié, on passe directement de brouillon à en cours
                # 1. Créer le bon de livraison
                picking = record._create_simplified_picking()
                if picking:
                    # 2. Mettre à jour le statut
                    record.write({
                        'state': 'in_progress',
                        'date_planned': fields.Date.today(),
                        'picking_id': picking.id
                    })
                    msg = _("Mode simplifié : Préparation validée et bon de livraison %s créé par %s") % (
                    picking.name, self.env.user.name)
                    record.message_post(body=msg)
            else:
                # Mode standard
                record.write({'state': 'planned', 'date_planned': fields.Date.today()})
                msg = _("Préparation validée par %s") % self.env.user.name
                record.message_post(body=msg)

        return True

    def _create_simplified_picking(self):
        """Crée un bon de livraison en mode simplifié sans demander confirmation"""
        self.ensure_one()

        if not self.installation_line_ids:
            return False

        if not self.client_id:
            raise UserError(_("Aucun client associé au véhicule. Veuillez définir un client."))

        picking_type = self.env['stock.picking.type'].search([('code', '=', 'outgoing')], limit=1)
        if not picking_type:
            raise UserError(_("Aucun type de picking 'Delivery Orders' configuré."))

        # Trouver l'emplacement source et destination
        location_src_id = picking_type.default_location_src_id or self.env.ref('stock.stock_location_stock',
                                                                               raise_if_not_found=False)
        if not location_src_id:
            raise UserError(
                _("Aucun emplacement source trouvé. Veuillez configurer un emplacement source dans le type d'opération ou dans le stock par défaut."))

        # Pour l'emplacement de destination, essayons plusieurs options
        location_dest_id = picking_type.default_location_dest_id
        if not location_dest_id:
            # Essayer de trouver l'emplacement "Client" par défaut
            location_dest_id = self.env.ref('stock.stock_location_customers', raise_if_not_found=False)
            if not location_dest_id:
                # Sinon chercher tout emplacement qui pourrait être une destination externe
                location_dest_id = self.env['stock.location'].search([
                    ('usage', '=', 'customer'),
                    '|', ('company_id', '=', self.env.company.id), ('company_id', '=', False)
                ], limit=1)
                if not location_dest_id:
                    raise UserError(
                        _("Aucun emplacement destination trouvé. Veuillez configurer un emplacement destination dans le type d'opération ou créer un emplacement 'client_id'."))

        try:
            move_vals = []
            for line in self.installation_line_ids:
                # Créer le dictionnaire de valeurs avec une vérification des champs disponibles
                vals = {
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'product_uom': line.product_id.uom_id.id,
                    'location_id': location_src_id.id,
                    'location_dest_id': location_dest_id.id,
                }

                # Ajouter le champ de quantité avec le bon nom selon la version d'Odoo
                # Essayer d'abord 'quantity' (Odoo 17), puis 'product_uom_qty' (versions antérieures)
                StockMove = self.env['stock.move']
                if 'quantity' in StockMove._fields:
                    vals['quantity'] = line.product_uom_qty
                else:
                    vals['product_uom_qty'] = line.product_uom_qty

                move_vals.append((0, 0, vals))

            picking = self.env['stock.picking'].create({
                'picking_type_id': picking_type.id,
                'partner_id': self.client_id.id,
                'origin': self.name,
                'location_id': location_src_id.id,
                'location_dest_id': location_dest_id.id,
                'move_ids': move_vals,
            })

            # Confirmer le bon de livraison
            picking.action_confirm()

            # Pour chaque ligne d'installation, associer le lot au mouvement correspondant
            for line in self.installation_line_ids:
                if line.lot_id and line.product_id:
                    # Trouver le mouvement correspondant à cette ligne
                    move = picking.move_ids.filtered(lambda m: m.product_id.id == line.product_id.id)

                    if move:
                        # Utiliser les API appropriées selon la version d'Odoo
                        if hasattr(move, 'move_line_ids'):
                            # Pour Odoo 15+
                            for move_line in move.move_line_ids:
                                move_line.lot_id = line.lot_id.id
                                # Mettre à jour également le numéro de série si c'est un champ disponible
                                if hasattr(move_line, 'lot_name'):
                                    move_line.lot_name = line.serial_number
                        else:
                            # Fallback pour les versions antérieures
                            for move_line in move.move_line_nosuggest_ids:
                                move_line.lot_id = line.lot_id.id
                                if hasattr(move_line, 'lot_name'):
                                    move_line.lot_name = line.serial_number

            # Réserver les produits
            picking.action_assign()

            # Si après réservation, certains lots n'ont pas été assignés, les forcer
            for move in picking.move_ids:
                if move.state != 'assigned':
                    for move_line in move.move_line_ids:
                        # Trouver la ligne d'installation correspondante
                        install_line = self.installation_line_ids.filtered(
                            lambda l: l.product_id.id == move.product_id.id)

                        if install_line and install_line.lot_id:
                            move_line.lot_id = install_line.lot_id.id
                            if hasattr(move_line, 'lot_name'):
                                move_line.lot_name = install_line.serial_number

                            # Dans Odoo 17, le champ quantity s'appelle peut-être qty_done
                            if hasattr(move_line, 'qty_done'):
                                move_line.qty_done = install_line.product_uom_qty
                            elif hasattr(move_line, 'quantity'):
                                move_line.quantity = install_line.product_uom_qty

            return picking

        except Exception as e:
            raise UserError(_("Erreur lors de la création du bon de livraison: %s") % str(e))

    def _create_sale_order(self):
        """Crée un bon de commande client basé sur les produits utilisés"""
        self.ensure_one()

        if not self.installation_line_ids:
            return False

        if not self.client_id:
            raise UserError(_("Aucun client associé au véhicule. Veuillez définir un client."))

        # Créer l'entête de la commande client
        so_vals = {
            'partner_id': self.client_id.id,
            'date_order': fields.Datetime.now(),
            'origin': self.name,
            'company_id': self.company_id.id,
            'order_line': [],
        }

        # Ajouter les lignes de commande
        for line in self.installation_line_ids:
            so_line = {
                'product_id': line.product_id.id,
                'name': line.product_id.name,
                'product_uom_qty': line.product_uom_qty,
                'product_uom': line.product_id.uom_id.id,
                'price_unit': line.price_unit,
            }
            so_vals['order_line'].append((0, 0, so_line))

        # Créer la commande client
        sale_order = self.env['sale.order'].create(so_vals)

        # Lier la commande client à l'installation
        self.write({'sale_order_id': sale_order.id})

        # Message de confirmation
        msg = _("Bon de commande client %s créé pour cette installation.") % sale_order.name
        self.message_post(body=msg)

        return sale_order

    def action_view_sale_order(self):
        """Ouvre la commande client associée"""
        self.ensure_one()
        if not self.sale_order_id:
            return

        return {
            'name': _('Bon de commande client'),
            'view_mode': 'form',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'type': 'ir.actions.act_window',
        }

    def action_create_picking(self):
        self.ensure_one()

        if not self.installation_line_ids:
            # Si aucune ligne n'existe, permettre à l'utilisateur d'en ajouter
            return {
                'name': _('Ajouter des produits'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'gpl.installation.add.products',
                'target': 'new',
                'context': {
                    'default_installation_id': self.id,
                    'default_client_id': self.client_id.id if self.client_id else False,
                }
            }

        if not self.client_id:
            raise UserError(_("Aucun client associé au véhicule. Veuillez définir un client."))

        picking_type = self.env['stock.picking.type'].search([('code', '=', 'outgoing')], limit=1)
        if not picking_type:
            raise UserError(_("Aucun type de picking 'Delivery Orders' configuré."))

        # Trouver l'emplacement source et destination
        location_src_id = picking_type.default_location_src_id or self.env.ref('stock.stock_location_stock',
                                                                               raise_if_not_found=False)
        if not location_src_id:
            raise UserError(
                _("Aucun emplacement source trouvé. Veuillez configurer un emplacement source dans le type d'opération ou dans le stock par défaut."))

        # Pour l'emplacement de destination, essayons plusieurs options
        location_dest_id = picking_type.default_location_dest_id
        if not location_dest_id:
            # Essayer de trouver l'emplacement "Client" par défaut
            location_dest_id = self.env.ref('stock.stock_location_customers', raise_if_not_found=False)
            if not location_dest_id:
                # Sinon chercher tout emplacement qui pourrait être une destination externe
                location_dest_id = self.env['stock.location'].search([
                    ('usage', '=', 'customer'),
                    '|', ('company_id', '=', self.env.company.id), ('company_id', '=', False)
                ], limit=1)
                if not location_dest_id:
                    raise UserError(
                        _("Aucun emplacement destination trouvé. Veuillez configurer un emplacement destination dans le type d'opération ou créer un emplacement 'Client'."))

        try:
            move_vals = []
            for line in self.installation_line_ids:
                # Créer le dictionnaire de valeurs avec une vérification des champs disponibles
                vals = {
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'product_uom': line.product_id.uom_id.id,
                    'location_id': location_src_id.id,
                    'location_dest_id': location_dest_id.id,
                }

                # Ajouter le champ de quantité avec le bon nom selon la version d'Odoo
                # Essayer d'abord 'quantity' (Odoo 17), puis 'product_uom_qty' (versions antérieures)
                StockMove = self.env['stock.move']
                if 'quantity' in StockMove._fields:
                    vals['quantity'] = line.product_uom_qty
                else:
                    vals['product_uom_qty'] = line.product_uom_qty

                move_vals.append((0, 0, vals))

            picking = self.env['stock.picking'].create({
                'picking_type_id': picking_type.id,
                'partner_id': self.client_id.id,
                'origin': self.name,
                'location_id': location_src_id.id,
                'location_dest_id': location_dest_id.id,
                'move_ids': move_vals,
            })

            # Confirmer le bon de livraison
            picking.action_confirm()

            # Pour chaque ligne d'installation, associer le lot au mouvement correspondant
            for line in self.installation_line_ids:
                if line.lot_id and line.product_id:
                    # Trouver le mouvement correspondant à cette ligne
                    move = picking.move_ids.filtered(lambda m: m.product_id.id == line.product_id.id)

                    if move:
                        # Utiliser les API appropriées selon la version d'Odoo
                        if hasattr(move, 'move_line_ids'):
                            # Pour Odoo 15+
                            for move_line in move.move_line_ids:
                                move_line.lot_id = line.lot_id.id
                                # Mettre à jour également le numéro de série si c'est un champ disponible
                                if hasattr(move_line, 'lot_name'):
                                    move_line.lot_name = line.serial_number
                        else:
                            # Fallback pour les versions antérieures
                            for move_line in move.move_line_nosuggest_ids:
                                move_line.lot_id = line.lot_id.id
                                if hasattr(move_line, 'lot_name'):
                                    move_line.lot_name = line.serial_number

            # Réserver les produits
            picking.action_assign()

            # Si après réservation, certains lots n'ont pas été assignés, les forcer
            for move in picking.move_ids:
                if move.state != 'assigned':
                    for move_line in move.move_line_ids:
                        # Trouver la ligne d'installation correspondante
                        install_line = self.installation_line_ids.filtered(
                            lambda l: l.product_id.id == move.product_id.id)

                        if install_line and install_line.lot_id:
                            move_line.lot_id = install_line.lot_id.id
                            if hasattr(move_line, 'lot_name'):
                                move_line.lot_name = install_line.serial_number

                            # Dans Odoo 17, le champ quantity s'appelle peut-être qty_done
                            if hasattr(move_line, 'qty_done'):
                                move_line.qty_done = install_line.product_uom_qty
                            elif hasattr(move_line, 'quantity'):
                                move_line.quantity = install_line.product_uom_qty

            self.write({
                'picking_id': picking.id,
                'state': 'in_progress'
            })

            msg = _("Bon de livraison %s créé et matériel réservé. Installation en cours.") % picking.name
            self.message_post(body=msg)

            return {
                'name': _('Bon de Livraison'),
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'view_mode': 'form',
                'res_id': picking.id,
            }
        except Exception as e:
            raise UserError(_("Erreur lors de la création du bon de livraison: %s") % str(e))

    def action_complete_installation(self):
        for record in self:
            if not record.picking_id:
                raise UserError(_("Aucun bon de livraison associé à cette installation."))

            try:
                # 1. Valider le bon de livraison s'il n'est pas déjà validé
                if record.picking_id.state != 'done':
                    # Code existant pour valider le bon de livraison
                    for move in record.picking_id.move_ids.filtered(lambda m: m.state not in ['done', 'cancel']):
                        for move_line in move.move_line_ids:
                            # Définir les quantités...
                            reserved_qty = 0
                            if hasattr(move_line, 'product_uom_qty'):
                                reserved_qty = move_line.product_uom_qty
                            elif hasattr(move_line, 'quantity'):
                                reserved_qty = move_line.quantity
                            elif hasattr(move_line, 'reserved_qty'):
                                reserved_qty = move_line.reserved_qty
                            elif hasattr(move, 'product_uom_qty'):
                                reserved_qty = move.product_uom_qty
                            elif hasattr(move, 'quantity'):
                                reserved_qty = move.quantity
                            else:
                                reserved_qty = 1

                            # Appliquer les quantités
                            if hasattr(move_line, 'qty_done'):
                                move_line.qty_done = reserved_qty
                            elif hasattr(move_line, 'quantity'):
                                move_line.quantity = reserved_qty
                            else:
                                try:
                                    move_line.write({'quantity': reserved_qty})
                                except Exception:
                                    try:
                                        move_line.write({'qty_done': reserved_qty})
                                    except Exception:
                                        pass

                    # Valider le bon de livraison
                    record.picking_id.button_validate()

                # 2. Marquer l'installation comme terminée
                record.write({
                    'state': 'done',
                    'date_completion': fields.Date.today()
                })

                # 3. Mettre à jour le véhicule avec le réservoir
                if record.vehicle_id:
                    # MODIFICATION ICI: Définir directement les statuts sans utiliser env.ref
                    # Mettre à jour le statut et le prochain service
                    vehicle_values = {
                        'status_id': 4,  # ID du statut "En attente de validation"
                        'next_service_type': 'inspection'  # Contrôle technique
                    }

                    # Si on a un réservoir, l'associer au véhicule
                    reservoir_line = False
                    for line in record.installation_line_ids:
                        if line.product_id.is_gpl_reservoir and line.serial_number:
                            reservoir_line = line
                            lot = self.env['stock.lot'].search([
                                ('name', '=', line.serial_number),
                                ('product_id', '=', line.product_id.id)
                            ], limit=1)

                            if lot:
                                vehicle_values.update({
                                    'reservoir_lot_id': lot.id,
                                    'installation_id': record.id
                                })

                                # Message de traçabilité
                                vehicle_msg = _(
                                    "Réservoir GPL (numéro de série: %s) installé via l'installation %s. Véhicule en attente de contrôle technique.") % (
                                                  lot.name, record.name)
                                record.vehicle_id.message_post(body=vehicle_msg)

                    # Mettre à jour le véhicule
                    record.vehicle_id.write(vehicle_values)

                # 4. Facturation automatique si configurée
                auto_invoice = self.env['ir.config_parameter'].sudo().get_param('gpl_fleet.auto_invoice',
                                                                                'False').lower() == 'true'
                if auto_invoice and not record.invoice_id:
                    invoice = record._create_automatic_invoice()
                    if invoice:
                        msg = _("Facturation automatique: Facture %s créée.") % invoice.name
                        record.message_post(body=msg)

                # 5. Message de confirmation
                msg = _(
                    "Installation terminée par %s. Véhicule mis en attente de contrôle technique.") % self.env.user.name
                record.message_post(body=msg)

            except Exception as e:
                raise UserError(_("Erreur lors de la finalisation de l'installation: %s") % str(e))

        return True

    def _create_automatic_invoice(self):
        """Crée automatiquement une facture quand l'option auto_invoice est activée"""
        self.ensure_one()

        if not self.client_id:
            raise UserError(_("Aucun client lié à l'installation."))

        if not self.installation_line_ids:
            raise UserError(_("Aucun produit utilisé dans l'installation."))

        try:
            # Créer la facture
            invoice_vals = {
                'move_type': 'out_invoice',
                'partner_id': self.client_id.id,
                'invoice_date': fields.Date.today(),
                'invoice_origin': self.name,
                'invoice_line_ids': [],
            }

            # Ajouter les lignes de facture
            for line in self.installation_line_ids:
                # Trouver le compte de revenu approprié
                account = False

                # 1. D'abord essayer le compte de revenu du produit
                if line.product_id.property_account_income_id:
                    account = line.product_id.property_account_income_id
                # 2. Sinon, essayer le compte de revenu de la catégorie de produit
                elif line.product_id.categ_id.property_account_income_categ_id:
                    account = line.product_id.categ_id.property_account_income_categ_id
                # 3. Si toujours pas de compte, récupérer le compte de revenu par défaut
                else:
                    account_journal = self.env['account.journal'].search(
                        [('type', '=', 'sale'), ('company_id', '=', self.company_id.id)], limit=1)
                    if account_journal and account_journal.default_account_id:
                        account = account_journal.default_account_id
                    else:
                        # Chercher un compte de revenus générique
                        account = self.env['account.account'].search([
                            ('company_id', '=', self.company_id.id),
                            ('account_type', '=', 'income')
                        ], limit=1)

                if not account:
                    raise UserError(
                        _("Impossible de déterminer un compte de revenus pour le produit %s.") % line.product_id.name)

                line_vals = {
                    'product_id': line.product_id.id,
                    'quantity': line.product_uom_qty,
                    'name': f"{self.name}: {line.product_id.name}",
                    'price_unit': line.price_unit if line.price_unit > 0 else line.product_id.list_price,
                    'account_id': account.id
                }
                invoice_vals['invoice_line_ids'].append((0, 0, line_vals))

            # Créer la facture avec toutes les lignes en une seule opération
            invoice = self.env['account.move'].create(invoice_vals)

            # Valider la facture
            try:
                invoice.action_post()  # Pour Odoo 13+
            except Exception as e:
                _logger.warning("Impossible de valider la facture: %s", str(e))
                # Ne pas bloquer si la validation échoue

            # Mettre à jour l'installation avec la référence à la facture
            self.write({'invoice_id': invoice.id})

            return invoice
        except Exception as e:
            _logger.error("Erreur lors de la création automatique de la facture: %s", str(e))
            return False

    def action_view_installation_lines(self):
        self.ensure_one()

        return {
            'name': _('Produits utilisés'),
            'type': 'ir.actions.act_window',
            'res_model': 'gpl.installation.line',
            'view_mode': 'tree,form',
            'views': [(self.env.ref('gpl_fleet.view_gpl_installation_line_tree').id, 'tree')],
            'domain': [('installation_id', '=', self.id)],
            'target': 'current',
            'context': {
                'default_installation_id': self.id,
                'create': True
            }
        }

    def action_invoice(self):
        self.ensure_one()

        if self.state != 'done':
            raise UserError(_("L'installation doit être terminée avant de pouvoir facturer."))

        if not self.client_id:
            raise UserError(_("Aucun client lié à l'installation."))

        if not self.installation_line_ids:
            raise UserError(_("Aucun produit utilisé dans l'installation."))

        if self.invoice_id:
            raise UserError(_("Une facture existe déjà pour cette installation."))

        try:
            invoice = self._create_automatic_invoice()

            if not invoice:
                raise UserError(_("Impossible de créer la facture. Vérifiez la configuration des comptes."))

            msg = _("Facture créée : %s") % invoice.name
            self.message_post(body=msg)

            return {
                'name': _('Facture'),
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': invoice.id,
            }
        except Exception as e:
            raise UserError(_("Erreur lors de la création de la facture: %s") % str(e))

    def action_cancel(self):
        for record in self:
            try:
                # Annuler le bon de livraison associé s'il existe
                if record.picking_id and record.picking_id.state != 'cancel':
                    if record.picking_id.state == 'done':
                        raise UserError(
                            _("Impossible d'annuler une installation avec un bon de livraison déjà validé."))
                    record.picking_id.action_cancel()

                record.write({'state': 'cancel'})
                msg = _("Installation annulée par %s") % self.env.user.name
                record.message_post(body=msg)
            except Exception as e:
                if "Impossible d'annuler" not in str(e):
                    raise UserError(_("Erreur lors de l'annulation: %s") % str(e))
                else:
                    raise

        return True

    def action_draft(self):
        for record in self:
            if record.picking_id and record.picking_id.state == 'done':
                raise UserError(
                    _("Impossible de remettre en brouillon une installation avec un bon de livraison validé."))

            record.write({'state': 'draft'})
            msg = _("Installation remise en préparation par %s") % self.env.user.name
            record.message_post(body=msg)
        return True

    def action_add_products(self):
        self.ensure_one()
        return {
            'name': _('Ajouter des produits'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'gpl.installation.add.products',
            'target': 'new',
            'context': {
                'default_installation_id': self.id,
                'default_client_id': self.client_id.id if self.client_id else False,

            }
        }

    def action_view_picking(self):
        self.ensure_one()
        if not self.picking_id:
            return

        return {
            'name': _('Bon de livraison'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': self.picking_id.id,
            'target': 'current',
            'context': {'create': False}
        }

    def action_view_invoice(self):
        """Open the related invoice form view."""
        self.ensure_one()
        if not self.invoice_id:
            return

        return {
            'name': _('Facture'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.invoice_id.id,
            'target': 'current',
            'context': {'create': False}
        }

class GplInstallationLine(models.Model):
    _name = 'gpl.installation.line'
    _description = "Lignes de produits utilisés pour l'installation"

    installation_id = fields.Many2one('gpl.service.installation', string="Installation", required=True,
                                      ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Produit", required=True)
    product_uom_qty = fields.Float(string="Quantité", default=1.0)
    qty_available = fields.Float(string="Stock dispo", compute="_compute_qty_available", store=False)
    status_color = fields.Char(compute="_compute_status_color", store=False)
    forecast_availability = fields.Float(
        related='product_id.virtual_available',
        string='Disponibilité prévue',
        readonly=True,
        store=False
    )
    price_unit = fields.Float(string="Prix unitaire", compute="_compute_price", store=True)
    price_subtotal = fields.Float(string="Sous-total", compute="_compute_price", store=True)
    serial_number = fields.Char(string='Numéro de série')

    lot_id = fields.Many2one('stock.lot', string='Numéro de lot/série')

    # Champ calculé pour déterminer si le produit est un réservoir GPL
    is_gpl_reservoir = fields.Boolean(string='Est un réservoir GPL',
                                      related='product_id.is_gpl_reservoir',
                                      store=True)

    available_lot_ids = fields.Many2many('stock.lot', compute='_compute_available_lots', string='Lots disponibles')

    @api.depends('product_id', 'installation_id.company_id')
    def _compute_available_lots(self):
        for line in self:
            if line.product_id and line.product_id.tracking != 'none':
                # Trouver les lots disponibles pour ce produit
                # qui sont en stock interne et pas dans l'emplacement client (ID=5)
                quants_domain = [
                    ('product_id', '=', line.product_id.id),
                    ('location_id.usage', '=', 'internal'),
                    ('location_id.id', '!=', 5),
                    ('quantity', '>', 0)
                ]

                # Récupérer les quants qui correspondent aux critères
                quants = self.env['stock.quant'].search(quants_domain)

                # Récupérer uniquement les lots associés à ces quants
                lot_ids = quants.mapped('lot_id').ids

                # Rechercher les lots qui correspondent aux IDs récupérés
                lots = self.env['stock.lot'].search([
                    ('id', 'in', lot_ids),
                    '|',
                    ('company_id', '=', line.installation_id.company_id.id),
                    ('company_id', '=', False)
                ])

                line.available_lot_ids = lots
            else:
                line.available_lot_ids = False
    @api.depends('product_id', 'product_uom_qty')
    def _compute_price(self):
        for line in self:
            if line.product_id:
                line.price_unit = line.product_id.list_price
                line.price_subtotal = line.price_unit * line.product_uom_qty
            else:
                line.price_unit = 0.0
                line.price_subtotal = 0.0

    @api.depends('product_uom_qty', 'qty_available')
    def _compute_status_color(self):
        for line in self:
            if line.qty_available >= line.product_uom_qty:
                line.status_color = 'success'
            else:
                line.status_color = 'danger'

    @api.depends('product_id')
    def _compute_qty_available(self):
        for line in self:
            if line.product_id:
                line.qty_available = line.product_id.qty_available
            else:
                line.qty_available = 0.0


    @api.model
    def create(self, values):
        line = super(GplInstallationLine, self).create(values)

        # Si c'est un produit de type réservoir, mettre à jour l'installation
        if (line.product_id and line.product_id.is_gpl_reservoir and
            line.installation_id and line.serial_number):
            # Rechercher un lot existant
            lot = self.env['stock.lot'].search([
                ('name', '=', line.serial_number),
                ('product_id', '=', line.product_id.id)
            ], limit=1)

            if lot:
                # Si le lot existe, l'assigner à l'installation
                line.installation_id.write({
                    'reservoir_lot_id': lot.id
                })
            else:
                # Si le lot n'existe pas, le créer
                lot_vals = {
                    'name': line.serial_number,
                    'product_id': line.product_id.id,
                    'company_id': line.installation_id.company_id.id,
                }
                # Si l'installation a des informations de certification, les appliquer au lot
                if hasattr(line.installation_id, 'certification_number') and line.installation_id.certification_number:
                    lot_vals.update({
                        'certification_number': line.installation_id.certification_number,
                        'certification_date': line.installation_id.certification_date,
                    })
                new_lot = self.env['stock.lot'].create(lot_vals)

                # Assigner le nouveau lot à l'installation
                line.installation_id.write({
                    'reservoir_lot_id': new_lot.id,
                    'serial_number': new_lot.name,
                })

                # Mettre à jour la ligne avec le lot créé
                line.lot_id = new_lot.id

        return line
    @api.onchange('product_id', 'serial_number')
    def _onchange_product_id_update_reservoir_info(self):
        if self.product_id and self.product_id.is_gpl_reservoir and self.serial_number:
            # Check if we have a matching reservoir in the system
            reservoir = self.env['stock.lot'].search([
                ('name', '=', self.serial_number),
                ('product_id', '=', self.product_id.id)
            ], limit=1)

            # If found, update installation with reservoir details
            if reservoir and self.installation_id:
                self.installation_id.reservoir_lot_id = reservoir.id


    @api.onchange('lot_id')
    def onchange_lot_id(self):
        """Mettre à jour le numéro de série lorsqu'un lot est sélectionné"""
        if self.lot_id:
            # Lorsqu'un lot est sélectionné, mettre à jour le numéro de série et le produit
            self.serial_number = self.lot_id.name
            self.product_id = self.lot_id.product_id.id

            # Si c'est un réservoir GPL, mettre à jour l'installation
            if self.lot_id.product_id.is_gpl_reservoir and self.installation_id:
                self.installation_id.reservoir_lot_id = self.lot_id.id



class GplInstallationAddProducts(models.TransientModel):
    _name = 'gpl.installation.add.products'
    _description = 'Assistant d\'ajout de produits pour installation GPL'

    installation_id = fields.Many2one('gpl.service.installation', string='Installation', required=True,
                                      default=lambda self: self.env.context.get('active_id'))
    product_ids = fields.Many2many('product.product', string='Produits à ajouter',
                                   domain="[('type', 'in', ['product', 'consu'])]")

    @api.model
    def default_get(self, fields):
        res = super(GplInstallationAddProducts, self).default_get(fields)
        if 'installation_id' in fields and not res.get('installation_id') and self.env.context.get('active_id'):
            res['installation_id'] = self.env.context.get('active_id')
        return res


class GplInstallationProductLine(models.Model):
    _name = 'gpl.installation.product.line'
    _description = "Ligne de produit pour installation GPL"

    installation_id = fields.Many2one('gpl.service.installation', string="Installation", required=True,
                                      ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Produit", required=True,
                                 domain="[('purchase_ok', '=', True)]")
    product_uom_qty = fields.Float(string="Quantité", default=1.0)
    price_unit = fields.Float(string="Prix unitaire", compute="_compute_price", store=True)
    price_subtotal = fields.Float(string="Sous-total", compute="_compute_subtotal", store=True)

    # Champs spécifiques pour les réservoirs GPL
    is_gpl_reservoir = fields.Boolean(related="product_id.is_gpl_reservoir", string="Est un réservoir GPL", store=True)
    lot_selection = fields.Selection([
        ('existing', 'Utiliser un réservoir existant'),
        ('new', 'Commander un nouveau réservoir')
    ], string="Type de réservoir")
    new_reservoir = fields.Boolean(string="Nouveau réservoir", default=False)
    serial_number = fields.Char(string="Numéro de série")

    @api.depends('product_id')
    def _compute_price(self):
        for line in self:
            if line.product_id:
                line.price_unit = line.product_id.list_price
            else:
                line.price_unit = 0.0

    @api.depends('product_uom_qty', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.price_subtotal = line.product_uom_qty * line.price_unit

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id and self.product_id.is_gpl_reservoir:
            # Si c'est un réservoir GPL, définir lot_selection par défaut
            self.lot_selection = 'new'
            self.new_reservoir = True
        else:
            self.lot_selection = False
            self.new_reservoir = False
            self.serial_number = False

    @api.onchange('lot_selection')
    def _onchange_lot_selection(self):
        if self.lot_selection == 'new':
            self.new_reservoir = True
        else:
            self.new_reservoir = False
