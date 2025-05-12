import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta
import logging
_logger = logging.getLogger(__name__)

class GplRepair(models.Model):
    _name = 'gpl.service.repair'
    _description = 'Réparation GPL'
    _inherit = ['mail.thread', 'mail.activity.mixin']  # Ajout des fonctionnalités de messagerie pour le suivi

    name = fields.Char(string="Référence", required=True, default="New", copy=False, readonly=True)

    # Champ pour le réservoir GPL
    reservoir_lot_id = fields.Many2one('stock.lot', string="Réservoir GPL",
                                      domain="[('product_id.is_gpl_reservoir', '=', True)]", tracking=True)

    # Champs liés au réservoir
    certification_number = fields.Char(related="reservoir_lot_id.certification_number",
                                      string="N° certification", readonly=True)
    certification_date = fields.Date(related="reservoir_lot_id.certification_date",
                                    string="Date certification", readonly=True)
    expiry_date = fields.Date(related="reservoir_lot_id.expiry_date",
                             string="Date expiration", readonly=True)
    reservoir_state = fields.Selection(related="reservoir_lot_id.state",
                                      string="État du réservoir", readonly=True)
    serial_number = fields.Char(related="reservoir_lot_id.name", string="N° série réservoir", readonly=True)

    # Nouvelle référence pour le réservoir en cas de remplacement
    new_reservoir_lot_id = fields.Many2one('stock.lot', string="Nouveau réservoir",
                                         domain="[('product_id.is_gpl_reservoir', '=', True)]", tracking=True)
    replace_reservoir = fields.Boolean(string="Remplacer le réservoir", default=False, tracking=True)

    # Dates spécifiques à la réparation
    date_request = fields.Date(string="Date de demande", default=fields.Date.today, required=True)
    date_planned = fields.Date(string="Date planifiée")
    date_start = fields.Date(string="Date de début")
    date_completion = fields.Date(string="Date de finalisation")
    engineer_validation_date = fields.Date(string="Date validation ingénieur", tracking=True,
                                         help="Date à laquelle l'ingénieur a validé la réparation")

    # Relations avec d'autres modèles
    vehicle_id = fields.Many2one('gpl.vehicle', string="Véhicule", required=True)
    client = fields.Many2one(related='vehicle_id.client_id', string="Client", store=True)
    technician_id = fields.Many2one('hr.employee', string="Technicien")


    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmé'),
        ('planned', 'Planifié'),
        ('in_progress', 'En cours'),
        ('to_validate', 'À valider'),
        ('done', 'Terminé'),
        ('cancel', 'Annulé')
    ], string="État", default='draft', tracking=True)

    # Diagnostic et notes
    diagnostic = fields.Text(string="Diagnostic", tracking=True)
    repair_notes = fields.Text(string="Notes de réparation", tracking=True)
    internal_notes = fields.Text(string="Notes internes")

    # Lignes de produits et services
    repair_line_ids = fields.One2many('gpl.repair.line', 'repair_id', string="Produits et services")

    # Documents associés
    picking_id = fields.Many2one('stock.picking', string="Bon de livraison")
    invoice_id = fields.Many2one('account.move', string="Facture")

    # Statistiques pour tableau de bord
    products_count = fields.Integer(string="Nombre de produits", compute="_compute_products_count")
    total_amount = fields.Float(string="Montant total", compute="_compute_total_amount")
    company_id = fields.Many2one('res.company', string='Société',
                                default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    @api.depends('repair_line_ids')
    def _compute_products_count(self):
        for record in self:
            record.products_count = len(record.repair_line_ids)

    @api.depends('repair_line_ids', 'repair_line_ids.product_id', 'repair_line_ids.product_uom_qty')
    def _compute_total_amount(self):
        for record in self:
            total = 0.0
            for line in record.repair_line_ids:
                total += line.product_id.list_price * line.product_uom_qty
            record.total_amount = total

    @api.model
    def create(self, vals):
        if isinstance(vals, dict) and vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('gpl.service.repair') or 'New'

        # Si le véhicule contient un réservoir, l'assigner dès la création
        if vals.get('vehicle_id'):
            vehicle = self.env['gpl.vehicle'].browse(vals['vehicle_id'])
            if vehicle and vehicle.reservoir_lot_id:
                vals['reservoir_lot_id'] = vehicle.reservoir_lot_id.id

        return super().create(vals)

    @api.onchange('vehicle_id')
    def onchange_vehicle_id(self):
        if self.vehicle_id:
            # Si le véhicule a un réservoir, l'assigner à la réparation
            if self.vehicle_id.reservoir_lot_id:
                self.reservoir_lot_id = self.vehicle_id.reservoir_lot_id.id

            # Définir le client à partir du véhicule
            if self.vehicle_id.client_id:
                self.client = self.vehicle_id.client_id

    def action_confirm(self):
        for record in self:
            if not record.vehicle_id:
                raise UserError(_("Veuillez sélectionner un véhicule avant de continuer."))

            record.write({'state': 'confirmed'})
            msg = _("Réparation confirmée par %s") % self.env.user.name
            record.message_post(body=msg)
        return True

    def action_plan(self):
        for record in self:
            if not record.technician_id:
                raise UserError(_("Veuillez assigner un technicien avant de planifier."))

            record.write({
                'state': 'planned',
                'date_planned': fields.Date.today()
            })
            msg = _("Réparation planifiée par %s") % self.env.user.name
            record.message_post(body=msg)
        return True

    def action_start_repair(self):
        self.ensure_one()
        self.write({
            'state': 'in_progress',
            'date_start': fields.Date.today()
        })
        msg = _("Réparation démarrée par %s") % self.env.user.name
        self.message_post(body=msg)
        return True

    def action_create_picking(self):
        self.ensure_one()

        if not self.repair_line_ids:
            # Si aucune ligne n'existe, permettre à l'utilisateur d'en ajouter
            return {
                'name': _('Ajouter des produits'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'gpl.repair.add.products',
                'target': 'new',
                'context': {
                    'default_repair_id': self.id,
                    'default_client_id': self.client.id if self.client else False,
                }
            }

        if not self.client:
            raise UserError(_("Aucun client associé au véhicule. Veuillez définir un client."))

        picking_type = self.env['stock.picking.type'].search([('code', '=', 'outgoing')], limit=1)
        if not picking_type:
            raise UserError(_("Aucun type de picking 'Delivery Orders' configuré."))

        # Trouver l'emplacement source et destination
        location_src_id = picking_type.default_location_src_id or self.env.ref('stock.stock_location_stock',
                                                                               raise_if_not_found=False)
        if not location_src_id:
            raise UserError(
                _("Aucun emplacement source trouvé. Veuillez configurer un emplacement source."))

        location_dest_id = picking_type.default_location_dest_id
        if not location_dest_id:
            location_dest_id = self.env.ref('stock.stock_location_customers', raise_if_not_found=False)
            if not location_dest_id:
                location_dest_id = self.env['stock.location'].search([
                    ('usage', '=', 'customer'),
                    '|', ('company_id', '=', self.env.company.id), ('company_id', '=', False)
                ], limit=1)
                if not location_dest_id:
                    raise UserError(_("Aucun emplacement destination trouvé."))

        try:
            # Filtrer uniquement les lignes avec des produits physiques (pas les services)
            product_lines = self.repair_line_ids.filtered(lambda l: l.product_id.type in ['product', 'consu'])

            if not product_lines:
                self.write({'state': 'to_validate'})
                msg = _("Aucun produit physique à livrer, passage directement à l'étape de validation.")
                self.message_post(body=msg)
                return True

            move_vals = []
            for line in product_lines:
                vals = {
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'product_uom': line.product_id.uom_id.id,
                    'location_id': location_src_id.id,
                    'location_dest_id': location_dest_id.id,
                }

                # Ajouter le champ de quantité avec le bon nom selon la version d'Odoo
                StockMove = self.env['stock.move']
                if 'quantity' in StockMove._fields:
                    vals['quantity'] = line.product_uom_qty
                else:
                    vals['product_uom_qty'] = line.product_uom_qty

                move_vals.append((0, 0, vals))

            picking = self.env['stock.picking'].create({
                'picking_type_id': picking_type.id,
                'partner_id': self.client.id,
                'origin': self.name,
                'location_id': location_src_id.id,
                'location_dest_id': location_dest_id.id,
                'move_ids': move_vals,
            })

            # Confirmer le bon de livraison
            picking.action_confirm()

            # Pour chaque ligne, associer le lot au mouvement correspondant
            for line in product_lines:
                if line.lot_id and line.product_id:
                    move = picking.move_ids.filtered(lambda m: m.product_id.id == line.product_id.id)
                    if move:
                        if hasattr(move, 'move_line_ids'):
                            for move_line in move.move_line_ids:
                                move_line.lot_id = line.lot_id.id
                                if hasattr(move_line, 'lot_name'):
                                    move_line.lot_name = line.serial_number
                        else:
                            for move_line in move.move_line_nosuggest_ids:
                                move_line.lot_id = line.lot_id.id
                                if hasattr(move_line, 'lot_name'):
                                    move_line.lot_name = line.serial_number

            # Réserver les produits
            picking.action_assign()

            self.write({
                'picking_id': picking.id,
                'state': 'to_validate'
            })

            msg = _("Bon de livraison %s créé. En attente de validation.") % picking.name
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

    def action_validate_engineer(self):
        self.ensure_one()

        self.write({
            'engineer_validation_date': fields.Date.today(),
            'state': 'done',
            'date_completion': fields.Date.today()
        })

        # Traiter le bon de livraison si existant
        if self.picking_id and self.picking_id.state != 'done':
            try:
                for move in self.picking_id.move_ids.filtered(lambda m: m.state not in ['done', 'cancel']):
                    for move_line in move.move_line_ids:
                        # Déterminer la quantité réservée
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

                        # Mettre à jour la quantité traitée
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
                self.picking_id.button_validate()
            except Exception as e:
                raise UserError(_("Erreur lors de la validation du bon de livraison: %s") % str(e))

        # Mettre à jour le réservoir sur le véhicule si nécessaire
        if self.replace_reservoir and self.new_reservoir_lot_id:
            self.vehicle_id.write({
                'reservoir_lot_id': self.new_reservoir_lot_id.id,
                'repair_id': self.id,
            })

            msg = _("Réservoir GPL remplacé par un nouveau (numéro de série: %s) via la réparation %s") % (
                self.new_reservoir_lot_id.name, self.name)
            self.vehicle_id.message_post(body=msg)

        msg = _("Réparation validée ")
        self.message_post(body=msg)
        return True

    def action_invoice(self):
        self.ensure_one()

        if self.state != 'done':
            raise UserError(_("La réparation doit être terminée avant de pouvoir facturer."))

        if not self.client:
            raise UserError(_("Aucun client lié à la réparation."))

        if not self.repair_line_ids:
            raise UserError(_("Aucun produit ou service utilisé dans cette réparation."))

        if self.invoice_id:
            raise UserError(_("Une facture existe déjà pour cette réparation."))

        try:
            # Créer la facture
            invoice_vals = {
                'move_type': 'out_invoice',
                'partner_id': self.client.id,
                'invoice_date': fields.Date.today(),
                'invoice_origin': self.name,
                'invoice_line_ids': [],
            }

            # Ajouter les lignes de facture
            for line in self.repair_line_ids:
                if not line.product_id.categ_id.property_account_income_categ_id:
                    raise UserError(_("Le produit %s n'a pas de compte de vente configuré.") % line.product_id.name)

                line_vals = {
                    'product_id': line.product_id.id,
                    'quantity': line.product_uom_qty,
                    'name': line.product_id.name,
                    'price_unit': line.product_id.list_price,
                    'account_id': line.product_id.categ_id.property_account_income_categ_id.id
                }
                invoice_vals['invoice_line_ids'].append((0, 0, line_vals))

            # Créer la facture
            invoice = self.env['account.move'].create(invoice_vals)
            invoice.action_post()

            self.write({'invoice_id': invoice.id})

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
                            _("Impossible d'annuler une réparation avec un bon de livraison déjà validé."))
                    record.picking_id.action_cancel()

                record.write({'state': 'cancel'})
                msg = _("Réparation annulée par %s") % self.env.user.name
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
                    _("Impossible de remettre en brouillon une réparation avec un bon de livraison validé."))

            record.write({'state': 'draft'})
            msg = _("Réparation remise en brouillon par %s") % self.env.user.name
            record.message_post(body=msg)
        return True

    def action_add_products(self):
        self.ensure_one()
        return {
            'name': _('Ajouter des produits'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'gpl.repair.add.products',
            'target': 'new',
            'context': {
                'default_repair_id': self.id,
                'default_client_id': self.client.id if self.client else False,
            }
        }

    def action_view_repair_lines(self):
        self.ensure_one()
        return {
            'name': _('Produits et services'),
            'type': 'ir.actions.act_window',
            'res_model': 'gpl.repair.line',
            'view_mode': 'tree,form',
            'domain': [('repair_id', '=', self.id)],
            'target': 'current',
            'context': {
                'default_repair_id': self.id,
                'create': True
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




class GplRepairLine(models.Model):
    _name = 'gpl.repair.line'
    _description = "Lignes de produits et services utilisés pour la réparation"

    repair_id = fields.Many2one('gpl.service.repair', string="Réparation", required=True,
                               ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Produit/Service", required=True,
                               domain="['|', ('type', 'in', ['product', 'consu']), ('type', '=', 'service')]")
    product_uom_qty = fields.Float(string="Quantité", default=1.0)
    qty_available = fields.Float(string="Stock dispo", compute="_compute_qty_available")
    is_service = fields.Boolean(string="Est un service", compute="_compute_is_service", store=True)
    price_unit = fields.Float(string="Prix unitaire", compute="_compute_price", store=True)
    price_subtotal = fields.Float(string="Sous-total", compute="_compute_price", store=True)

    serial_number = fields.Char(string='Numéro de série')
    lot_id = fields.Many2one('stock.lot', string='Numéro de lot/série')

    # Champ calculé pour déterminer si le produit est un réservoir GPL
    is_gpl_reservoir = fields.Boolean(string='Est un réservoir GPL',
                                     related='product_id.is_gpl_reservoir',
                                     store=True)

    available_lot_ids = fields.Many2many('stock.lot', compute='_compute_available_lots', string='Lots disponibles')

    @api.depends('product_id', 'repair_id.company_id')
    def _compute_available_lots(self):
        for line in self:
            if line.product_id and line.product_id.tracking != 'none':
                # Trouver les lots disponibles pour ce produit
                quants_domain = [
                    ('product_id', '=', line.product_id.id),
                    ('location_id.usage', '=', 'internal'),
                    ('location_id.id', '!=', 5),
                    ('quantity', '>', 0)
                ]

                quants = self.env['stock.quant'].search(quants_domain)
                lot_ids = quants.mapped('lot_id').ids

                lots = self.env['stock.lot'].search([
                    ('id', 'in', lot_ids),
                    '|',
                    ('company_id', '=', line.repair_id.company_id.id),
                    ('company_id', '=', False)
                ])

                line.available_lot_ids = lots
            else:
                line.available_lot_ids = False

    @api.depends('product_id')
    def _compute_is_service(self):
        for line in self:
            line.is_service = line.product_id.type == 'service' if line.product_id else False

    @api.depends('product_id', 'product_uom_qty')
    def _compute_price(self):
        for line in self:
            if line.product_id:
                line.price_unit = line.product_id.list_price
                line.price_subtotal = line.price_unit * line.product_uom_qty
            else:
                line.price_unit = 0.0
                line.price_subtotal = 0.0

    @api.depends('product_id')
    def _compute_qty_available(self):
        for line in self:
            if line.product_id and line.product_id.type in ['product', 'consu']:
                line.qty_available = line.product_id.qty_available
            else:
                line.qty_available = 0.0

    @api.onchange('lot_id')
    def onchange_lot_id(self):
        if self.lot_id:
            self.serial_number = self.lot_id.name
            self.product_id = self.lot_id.product_id.id

            # Si c'est un réservoir GPL, mettre à jour la réparation
            if self.lot_id.product_id.is_gpl_reservoir and self.repair_id:
                # Si nous sommes en train de remplacer le réservoir
                if self.repair_id.replace_reservoir:
                    self.repair_id.new_reservoir_lot_id = self.lot_id.id
                else:
                    self.repair_id.reservoir_lot_id = self.lot_id.id


class GplRepairAddProducts(models.TransientModel):
    _name = 'gpl.repair.add.products'
    _description = 'Assistant d\'ajout de produits pour réparation GPL'

    repair_id = fields.Many2one('gpl.service.repair', string='Réparation', required=True,
                              default=lambda self: self.env.context.get('active_id'))
    product_ids = fields.Many2many('product.product', string='Produits à ajouter',
                                  domain="['|', ('type', 'in', ['product', 'consu']), ('type', '=', 'service')]")
    include_services = fields.Boolean(string="Inclure les services", default=True,
                                     help="Cochez pour inclure également les produits de type service")

    @api.model
    def default_get(self, fields):
        res = super(GplRepairAddProducts, self).default_get(fields)
        if 'repair_id' in fields and not res.get('repair_id') and self.env.context.get('active_id'):
            res['repair_id'] = self.env.context.get('active_id')
        return res

    def action_add_products(self):
        self.ensure_one()
        if not self.product_ids:
            raise UserError(_("Veuillez sélectionner au moins un produit."))

        for product in self.product_ids:
            # Créer une ligne pour chaque produit
            self.env['gpl.repair.line'].create({
                'repair_id': self.repair_id.id,
                'product_id': product.id,
                'product_uom_qty': 1.0,
            })

        return {'type': 'ir.actions.act_window_close'}

    @api.onchange('include_services')
    def _onchange_include_services(self):
        domain = [('type', 'in', ['product', 'consu'])]
        if self.include_services:
            domain = ['|'] + domain + [('type', '=', 'service')]
        return {'domain': {'product_ids': domain}}
