from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)


class GplRepairOrder(models.Model):
    _name = 'gpl.repair.order'
    _description = 'Réparation GPL'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Référence',
        required=True,
        default="Nouveau",
        readonly=True,
        copy=False,
        tracking=True
    )
    vehicle_id = fields.Many2one(
        'gpl.vehicle',
        string='Véhicule GPL',
        required=True,
        tracking=True
    )
    client_id = fields.Many2one(
        related='vehicle_id.client_id',
        string='Client',
        store=True,
        readonly=False,
        tracking=True
    )

    repair_type = fields.Selection([
        ('reservoir', 'Réservoir GPL'),
        ('injector', 'Injecteurs GPL'),
        ('tube', 'Tuyauterie GPL'),
        ('pressure', 'Pression et étanchéité'),
        ('electronic', 'Système électronique'),
        ('control', 'Contrôle périodique'),
        ('other', 'Autre composant GPL')
    ], string="Type de réparation GPL")

    # Dates
    date_repair = fields.Date(string="Date de réparation", default=fields.Date.today, tracking=True)
    date_planned = fields.Date(string="Date planifiée", tracking=True)
    date_completion = fields.Date(string="Date de finalisation", tracking=True)
    scheduled_date = fields.Datetime(string="Date programmée", tracking=True)

    # Technicien
    technician_id = fields.Many2one(
        'hr.employee',
        string='Technicien',
        tracking=True
    )

    # État et statut
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('scheduled', 'Planifié'),
        ('preparation', 'Préparation produits'),
        ('in_progress', 'En cours'),
        ('done', 'Terminé'),
        ('cancel', 'Annulé')
    ], string='État', default='draft', tracking=True)

    # Diagnostic
    diagnostic = fields.Text(
        string="Diagnostic GPL",
        tracking=True,
        help="Diagnostic spécifique au système GPL"
    )
    notes = fields.Text(string="Notes internes")

    # Liens avec d'autres documents
    repair_line_ids = fields.One2many(
        'gpl.repair.line',
        'repair_id',
        string="Pièces et services"
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string="Bon de commande client",
        copy=False,
        tracking=True
    )
    picking_id = fields.Many2one(
        'stock.picking',
        string="Bon de livraison",
        copy=False,
        tracking=True
    )
    return_picking_id = fields.Many2one(
        'stock.picking',
        string="Bon de retour",
        copy=False,
        tracking=True
    )
    invoice_id = fields.Many2one(
        'account.move',
        string="Facture",
        copy=False,
        tracking=True
    )

    # Statistiques
    products_count = fields.Integer(
        string="Nombre de produits",
        compute="_compute_products_count"
    )
    total_amount = fields.Float(
        string="Montant total",
        compute="_compute_total_amount"
    )
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id'
    )

    # Configuration
    use_simplified_flow = fields.Boolean(
        string="Flux simplifié",
        compute='_compute_use_simplified_flow'
    )

    # Réservoir remplacé
    new_reservoir_lot_id = fields.Many2one(
        'stock.lot',
        string="Nouveau réservoir",
        domain="[('product_id.is_gpl_reservoir', '=', True)]",
        tracking=True
    )
    has_reservoir_replacement = fields.Boolean(
        string="Remplacement réservoir",
        compute="_compute_has_reservoir_replacement",
        store=True
    )

    # Champs pour contrôler les boutons (au lieu des invisibles avec lambda)
    has_deliverable_products = fields.Boolean(
        string="Produits à livrer",
        compute="_compute_product_categories",
        store=True
    )
    has_returnable_products = fields.Boolean(
        string="Produits à retourner",
        compute="_compute_product_categories",
        store=True
    )

    @api.depends('repair_line_ids', 'repair_line_ids.operation_type')
    def _compute_product_categories(self):
        for repair in self:
            repair.has_deliverable_products = False
            repair.has_returnable_products = False

            for line in repair.repair_line_ids:
                if line.operation_type == 'add':
                    repair.has_deliverable_products = True
                elif line.operation_type == 'remove':
                    repair.has_returnable_products = True
    @api.depends('repair_line_ids.product_id.is_gpl_reservoir', 'repair_line_ids.operation_type')
    def _compute_has_reservoir_replacement(self):
        for repair in self:
            repair.has_reservoir_replacement = False
            for line in repair.repair_line_ids:
                if line.product_id.is_gpl_reservoir and line.operation_type == 'add':
                    repair.has_reservoir_replacement = True
                    break

    @api.depends('company_id')
    def _compute_use_simplified_flow(self):
        simplified_flow = self.env['ir.config_parameter'].sudo().get_param(
            'gpl_fleet.simplified_flow', 'False').lower() == 'true'
        for record in self:
            record.use_simplified_flow = simplified_flow

    @api.depends('repair_line_ids')
    def _compute_products_count(self):
        for record in self:
            record.products_count = len(record.repair_line_ids)

    @api.depends('repair_line_ids.product_id', 'repair_line_ids.product_uom_qty', 'repair_line_ids.price_unit',
                 'repair_line_ids.operation_type')
    def _compute_total_amount(self):
        for record in self:
            total = 0.0
            for line in record.repair_line_ids:
                if line.operation_type == 'add':
                    total += line.price_subtotal
                # Les produits retournés ne sont pas comptés dans le total
            record.total_amount = total

    @api.model
    def create(self, vals):
        if vals.get('name', 'Nouveau') == 'Nouveau':
            vals['name'] = self.env['ir.sequence'].next_by_code('gpl.repair.order') or 'Nouveau'
        return super(GplRepairOrder, self).create(vals)

    @api.onchange('vehicle_id')
    def onchange_vehicle_id(self):
        if self.vehicle_id:
            self.client_id = self.vehicle_id.client_id

    @api.onchange('repair_type')
    def _onchange_repair_type(self):
        """Met à jour la description en fonction du type de réparation"""
        if self.repair_type and self.vehicle_id:
            repair_types = dict(self._fields['repair_type'].selection)
            repair_type_name = repair_types.get(self.repair_type)

            # Définir un texte de diagnostic initial en fonction du type
            diagnostic_templates = {
                'reservoir': "Inspection du réservoir GPL et accessoires",
                'injector': "Vérification des injecteurs et système d'alimentation",
                'tube': "Contrôle de l'état des tuyaux et raccords",
                'pressure': "Test d'étanchéité et contrôle de pression",
                'electronic': "Diagnostic du système électronique de gestion GPL",
                'control': "Contrôle périodique du système GPL",
                'other': "Diagnostic du système GPL"
            }

            if not self.diagnostic:  # Ne pas écraser un diagnostic existant
                self.diagnostic = diagnostic_templates.get(self.repair_type, "")

    # Actions de flux de travail
    def action_schedule(self):
        """Planifie la réparation"""
        for repair in self:
            if not repair.vehicle_id:
                raise UserError(_("Veuillez sélectionner un véhicule avant de continuer."))
            if not repair.technician_id:
                raise UserError(_("Veuillez assigner un technicien avant de continuer."))
            if not repair.date_repair:
                raise UserError(_("Veuillez définir une date de réparation avant de continuer."))

            repair.write({
                'state': 'scheduled',
                'date_planned': fields.Date.today(),
            })

            # Mettre à jour le véhicule
            in_progress_status = self.env.ref('gpl_fleet.vehicle_status_planifie', raise_if_not_found=False)
            if in_progress_status:
                repair.vehicle_id.write({
                    'status_id': in_progress_status.id,
                    'repair_order_id': repair.id,
                    'next_service_type': 'repair'
                })

            msg = _("Réparation planifiée par %s") % self.env.user.name
            repair.message_post(body=msg)

        return True

    def action_prepare_products(self):
        """Prépare les produits pour la réparation"""
        for repair in self:
            # Créer un bon de commande client si ce n'est pas déjà fait
            if not repair.sale_order_id and repair.repair_line_ids:
                self._create_sale_order()

            # Vérifier si le flux simplifié est activé
            if repair.use_simplified_flow:
                # En mode simplifié, créer automatiquement le bon de livraison
                picking = repair._create_simplified_picking()
                if picking:
                    repair.write({
                        'state': 'in_progress',
                        'picking_id': picking.id
                    })
                    msg = _("Mode simplifié : Préparation validée et bon de livraison %s créé par %s") % (
                        picking.name, self.env.user.name)
                    repair.message_post(body=msg)
            else:
                repair.write({'state': 'preparation'})
                msg = _("Préparation des produits par %s") % self.env.user.name
                repair.message_post(body=msg)

            # Mettre à jour le véhicule
            in_progress_status = self.env.ref('gpl_fleet.vehicle_status_en_service', raise_if_not_found=False)
            if in_progress_status:
                repair.vehicle_id.write({
                    'status_id': in_progress_status.id,
                })

        return True

    def action_create_picking(self):
        """Crée un bon de livraison pour les produits"""
        self.ensure_one()

        if not self.repair_line_ids.filtered(lambda l: l.operation_type == 'add'):
            raise UserError(_("Aucun produit à livrer n'a été ajouté."))

        if not self.client_id:
            raise UserError(_("Aucun client associé au véhicule. Veuillez définir un client."))

        picking = self._create_picking('out')

        if picking:
            self.write({
                'state': 'in_progress',
                'picking_id': picking.id
            })

            msg = _("Bon de livraison %s créé et matériel réservé. Réparation en cours.") % picking.name
            self.message_post(body=msg)

            return {
                'name': _('Bon de Livraison'),
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'view_mode': 'form',
                'res_id': picking.id,
            }

    def action_create_return_picking(self):
        """Crée un bon de retour pour les produits à retourner"""
        self.ensure_one()

        if not self.repair_line_ids.filtered(lambda l: l.operation_type == 'remove'):
            raise UserError(_("Aucun produit à retourner n'a été ajouté."))

        if not self.client_id:
            raise UserError(_("Aucun client associé au véhicule. Veuillez définir un client."))

        picking = self._create_picking('in')

        if picking:
            self.write({
                'return_picking_id': picking.id
            })

            msg = _("Bon de retour %s créé pour les produits à retourner.") % picking.name
            self.message_post(body=msg)

            return {
                'name': _('Bon de Retour'),
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'view_mode': 'form',
                'res_id': picking.id,
            }

    def _create_picking(self, picking_type_code):
        """Crée un bon de livraison ou de retour"""
        self.ensure_one()

        # Déterminer s'il s'agit d'une livraison ou d'un retour
        is_return = (picking_type_code == 'in')

        # Rechercher le type d'opération approprié
        # Première tentative avec le code exact
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', picking_type_code),
            '|', ('company_id', '=', self.env.company.id), ('company_id', '=', False)
        ], limit=1)

        # Si aucun type n'est trouvé, recherche plus générique
        if not picking_type:
            # Pour les livraisons
            if picking_type_code == 'outgoing':
                picking_type = self.env['stock.picking.type'].search([
                    ('name', 'ilike', 'livraison'),
                    '|', ('company_id', '=', self.env.company.id), ('company_id', '=', False)
                ], limit=1)
                if not picking_type:
                    picking_type = self.env['stock.picking.type'].search([
                        ('warehouse_id.partner_id', '=', self.env.company.partner_id.id),
                        ('code', '=', 'outgoing')
                    ], limit=1)
            # Pour les réceptions
            elif picking_type_code == 'in':
                picking_type = self.env['stock.picking.type'].search([
                    ('name', 'ilike', 'réception'),
                    '|', ('company_id', '=', self.env.company.id), ('company_id', '=', False)
                ], limit=1)
                if not picking_type:
                    picking_type = self.env['stock.picking.type'].search([
                        ('warehouse_id.partner_id', '=', self.env.company.partner_id.id),
                        ('code', '=', 'incoming')
                    ], limit=1)

        # Si toujours aucun type trouvé, créer un type d'opération par défaut
        if not picking_type:
            # Trouver un entrepôt pour créer les types d'opération
            warehouse = self.env['stock.warehouse'].search([
                '|', ('company_id', '=', self.env.company.id), ('company_id', '=', False)
            ], limit=1)

            if not warehouse:
                raise UserError(_("Aucun entrepôt trouvé pour créer les types d'opération nécessaires."))

            # Créer le type d'opération
            if picking_type_code == 'outgoing':
                # Trouver les emplacements nécessaires
                location_id = self.env['stock.location'].search([
                    ('usage', '=', 'internal'),
                    '|', ('company_id', '=', self.env.company.id), ('company_id', '=', False)
                ], limit=1)
                location_dest_id = self.env['stock.location'].search([
                    ('usage', '=', 'customer'),
                    '|', ('company_id', '=', self.env.company.id), ('company_id', '=', False)
                ], limit=1)

                if not location_id or not location_dest_id:
                    raise UserError(
                        _("Impossible de trouver les emplacements nécessaires pour créer un type d'opération."))

                # Créer le type d'opération de livraison
                picking_type = self.env['stock.picking.type'].create({
                    'name': 'Livraison GPL',
                    'code': 'outgoing',
                    'sequence_code': 'OUT',
                    'default_location_src_id': location_id.id,
                    'default_location_dest_id': location_dest_id.id,
                    'sequence_id': self.env['ir.sequence'].create({
                        'name': 'Séquence Livraison GPL',
                        'code': 'stock.picking.out',
                        'prefix': 'OUT/',
                        'padding': 5,
                    }).id,
                    'warehouse_id': warehouse.id,
                    'company_id': self.env.company.id,
                })
            else:  # 'in'
                # Trouver les emplacements nécessaires pour un retour
                location_id = self.env['stock.location'].search([
                    ('usage', '=', 'customer'),
                    '|', ('company_id', '=', self.env.company.id), ('company_id', '=', False)
                ], limit=1)
                location_dest_id = self.env['stock.location'].search([
                    ('usage', '=', 'internal'),
                    '|', ('company_id', '=', self.env.company.id), ('company_id', '=', False)
                ], limit=1)

                if not location_id or not location_dest_id:
                    raise UserError(
                        _("Impossible de trouver les emplacements nécessaires pour créer un type d'opération."))

                # Créer le type d'opération de réception
                picking_type = self.env['stock.picking.type'].create({
                    'name': 'Réception GPL',
                    'code': 'incoming',
                    'sequence_code': 'IN',
                    'default_location_src_id': location_id.id,
                    'default_location_dest_id': location_dest_id.id,
                    'sequence_id': self.env['ir.sequence'].create({
                        'name': 'Séquence Réception GPL',
                        'code': 'stock.picking.in',
                        'prefix': 'IN/',
                        'padding': 5,
                    }).id,
                    'warehouse_id': warehouse.id,
                    'company_id': self.env.company.id,
                })

        if not picking_type:
            type_name = 'réception' if is_return else 'livraison'
            raise UserError(
                _("Aucun type d'opération de %s configuré. Veuillez créer un type d'opération avec le code %s.") % (
                type_name, picking_type_code))

        # Déterminer les emplacements source et destination
        if is_return:
            # Pour un retour: Client -> Stock
            location_src_id = picking_type.default_location_dest_id or self.env.ref('stock.stock_location_customers',
                                                                                    raise_if_not_found=False)
            location_dest_id = picking_type.default_location_src_id or self.env.ref('stock.stock_location_stock',
                                                                                    raise_if_not_found=False)
        else:
            # Pour une livraison: Stock -> Client
            location_src_id = picking_type.default_location_src_id or self.env.ref('stock.stock_location_stock',
                                                                                   raise_if_not_found=False)
            location_dest_id = picking_type.default_location_dest_id or self.env.ref('stock.stock_location_customers',
                                                                                     raise_if_not_found=False)

        # Créer des emplacements par défaut si nécessaire
        if not location_src_id:
            location_src_id = self.env['stock.location'].search([('usage', '=', 'internal')], limit=1)
            if not location_src_id:
                raise UserError(_("Aucun emplacement source disponible."))

        if not location_dest_id:
            if is_return:
                location_dest_id = self.env['stock.location'].search([('usage', '=', 'internal')], limit=1)
            else:
                location_dest_id = self.env['stock.location'].search([('usage', '=', 'customer')], limit=1)
                if not location_dest_id:
                    # Créer un emplacement client par défaut si nécessaire
                    location_dest_id = self.env['stock.location'].create({
                        'name': 'Clients',
                        'usage': 'customer',
                        'company_id': self.env.company.id,
                    })

            if not location_dest_id:
                raise UserError(_("Impossible de déterminer un emplacement de destination."))

        try:
            # Préparer les lignes de mouvements
            move_vals = []

            # Filtrer les lignes en fonction du type d'opération (add ou remove)
            operation_type = 'remove' if is_return else 'add'
            lines = self.repair_line_ids.filtered(lambda l: l.operation_type == operation_type)

            if not lines:
                return False

            for line in lines:
                vals = {
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'product_uom': line.product_id.uom_id.id,
                    'location_id': location_src_id.id,
                    'location_dest_id': location_dest_id.id,
                }

                # Ajouter la quantité avec le bon nom de champ
                if hasattr(self.env['stock.move'], 'product_uom_qty'):
                    vals['product_uom_qty'] = line.product_uom_qty
                else:
                    vals['quantity'] = line.product_uom_qty

                move_vals.append((0, 0, vals))

            # Créer le bon de livraison/retour
            picking = self.env['stock.picking'].create({
                'picking_type_id': picking_type.id,
                'partner_id': self.client_id.id,
                'origin': self.name,
                'location_id': location_src_id.id,
                'location_dest_id': location_dest_id.id,
                'move_ids': move_vals,
            })

            # Confirmer le picking
            picking.action_confirm()

            # Associer les lots si nécessaire
            for line in lines:
                if line.lot_id and line.product_id:
                    move = picking.move_ids.filtered(lambda m: m.product_id.id == line.product_id.id)
                    if move:
                        for move_line in move.move_line_ids:
                            move_line.lot_id = line.lot_id.id
                            if hasattr(move_line, 'lot_name'):
                                move_line.lot_name = line.lot_id.name

            # Réserver les produits (uniquement pour les livraisons, pas pour les retours)
            if not is_return:
                picking.action_assign()

            return picking

        except Exception as e:
            type_name = 'retour' if is_return else 'livraison'
            raise UserError(_("Erreur lors de la création du bon de %s: %s") % (type_name, str(e)))

    def _create_simplified_picking(self):
        """Crée un bon de livraison en mode simplifié"""
        return self._create_picking('out')

    def _create_sale_order(self):
        """Crée un bon de commande client basé sur les produits utilisés"""
        self.ensure_one()

        if not self.repair_line_ids.filtered(lambda l: l.operation_type == 'add'):
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

        # Ajouter les lignes de commande (uniquement les produits ajoutés, pas retournés)
        for line in self.repair_line_ids.filtered(lambda l: l.operation_type == 'add'):
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

        # Lier la commande client à la réparation
        self.write({'sale_order_id': sale_order.id})

        # Message de confirmation
        msg = _("Bon de commande client %s créé pour cette réparation.") % sale_order.name
        self.message_post(body=msg)

        return sale_order

    def action_complete_repair(self):
        """Termine la réparation"""
        for repair in self:
            validate_delivery = False
            validate_return = False

            # Vérifier et valider le bon de livraison s'il existe
            if repair.picking_id and repair.picking_id.state != 'done':
                validate_delivery = True
                for move in repair.picking_id.move_ids.filtered(lambda m: m.state not in ['done', 'cancel']):
                    for move_line in move.move_line_ids:
                        # Déterminer la quantité à traiter en fonction des champs disponibles
                        # Cette partie a été modifiée pour gérer correctement Odoo 17
                        reserved_qty = 0

                        # Odoo 17+ : utiliser reserved_uom_qty ou product_uom_qty
                        if hasattr(move_line, 'reserved_uom_qty'):
                            reserved_qty = move_line.reserved_uom_qty
                        elif hasattr(move_line, 'product_uom_qty'):
                            reserved_qty = move_line.product_uom_qty
                        elif hasattr(move, 'product_uom_qty'):
                            reserved_qty = move.product_uom_qty
                        elif hasattr(move, 'quantity'):
                            reserved_qty = move.quantity
                        else:
                            # Fallback : utiliser la quantité de la ligne de réparation
                            repair_line = repair.repair_line_ids.filtered(
                                lambda l: l.product_id.id == move.product_id.id and l.operation_type == 'add'
                            )
                            if repair_line:
                                reserved_qty = repair_line[0].product_uom_qty
                            else:
                                reserved_qty = 1

                        # Appliquer la quantité traitée
                        if hasattr(move_line, 'qty_done'):
                            move_line.qty_done = reserved_qty
                        else:
                            # Fallback pour les anciennes versions si nécessaire
                            try:
                                move_line.write({'qty_done': reserved_qty})
                            except Exception as e:
                                _logger.warning(f"Impossible de définir qty_done: {str(e)}")

                try:
                    # Valider le bon de livraison
                    repair.picking_id.button_validate()
                except Exception as e:
                    _logger.warning(f"Impossible de valider le bon de livraison: {str(e)}")
                    # Ne pas bloquer le processus si la validation échoue

            # Vérifier et valider le bon de retour s'il existe
            if repair.return_picking_id and repair.return_picking_id.state != 'done':
                validate_return = True
                for move in repair.return_picking_id.move_ids.filtered(lambda m: m.state not in ['done', 'cancel']):
                    for move_line in move.move_line_ids:
                        # Même logique que pour les livraisons mais pour les retours
                        reserved_qty = 0

                        if hasattr(move_line, 'reserved_uom_qty'):
                            reserved_qty = move_line.reserved_uom_qty
                        elif hasattr(move_line, 'product_uom_qty'):
                            reserved_qty = move_line.product_uom_qty
                        elif hasattr(move, 'product_uom_qty'):
                            reserved_qty = move.product_uom_qty
                        elif hasattr(move, 'quantity'):
                            reserved_qty = move.quantity
                        else:
                            # Fallback : utiliser la quantité de la ligne de réparation
                            repair_line = repair.repair_line_ids.filtered(
                                lambda l: l.product_id.id == move.product_id.id and l.operation_type == 'remove'
                            )
                            if repair_line:
                                reserved_qty = repair_line[0].product_uom_qty
                            else:
                                reserved_qty = 1

                        if hasattr(move_line, 'qty_done'):
                            move_line.qty_done = reserved_qty
                        else:
                            try:
                                move_line.write({'qty_done': reserved_qty})
                            except Exception as e:
                                _logger.warning(f"Impossible de définir qty_done: {str(e)}")

                try:
                    repair.return_picking_id.button_validate()
                except Exception as e:
                    _logger.warning(f"Impossible de valider le bon de retour: {str(e)}")
                    # Ne pas bloquer le processus si la validation échoue

            # Mettre à jour la réparation
            repair.write({
                'state': 'done',
                'date_completion': fields.Date.today()
            })

            # Mise à jour du véhicule - si un réservoir a été remplacé
            if repair.has_reservoir_replacement:
                # Trouver le réservoir ajouté
                reservoir_line = repair.repair_line_ids.filtered(
                    lambda l: l.product_id.is_gpl_reservoir and l.operation_type == 'add' and l.lot_id
                )
                if reservoir_line and reservoir_line.lot_id:
                    repair.vehicle_id.write({
                        'reservoir_lot_id': reservoir_line.lot_id.id
                    })
                    repair.message_post(
                        body=_("Réservoir GPL remplacé. Nouveau numéro: %s") % reservoir_line.lot_id.name)

            # Mettre à jour le statut du véhicule
            completed_status = self.env.ref('gpl_fleet.vehicle_status_termine', raise_if_not_found=False)
            if completed_status:
                repair.vehicle_id.write({
                    'status_id': completed_status.id,
                    'repair_order_id': False,
                    'next_service_type': False
                })

            # Vérifier si facturation automatique activée
            auto_invoice = self.env['ir.config_parameter'].sudo().get_param('gpl_fleet.auto_invoice',
                                                                            'False').lower() == 'true'
            if auto_invoice and not repair.invoice_id:
                invoice = repair._create_invoice()
                if invoice:
                    msg = _("Facturation automatique: Facture %s créée.") % invoice.name
                    repair.message_post(body=msg)

            # Message de confirmation
            msg_parts = []
            if validate_delivery:
                msg_parts.append(_("Bon de livraison validé"))
            if validate_return:
                msg_parts.append(_("Bon de retour validé"))

            msg = _("Réparation terminée par %s. %s") % (
                self.env.user.name,
                " et ".join(msg_parts) if msg_parts else ""
            )
            repair.message_post(body=msg)

        return True

    def action_invoice(self):
        """Crée une facture pour la réparation"""
        self.ensure_one()

        if self.state != 'done':
            raise UserError(_("La réparation doit être terminée avant de pouvoir facturer."))

        if not self.client_id:
            raise UserError(_("Aucun client associé à cette réparation."))

        if not self.repair_line_ids.filtered(lambda l: l.operation_type == 'add'):
            raise UserError(_("Aucun produit ajouté dans cette réparation."))

        if self.invoice_id:
            raise UserError(_("Une facture existe déjà pour cette réparation."))

        invoice = self._create_invoice()

        if invoice:
            msg = _("Facture créée : %s") % invoice.name
            self.message_post(body=msg)

            return {
                'name': _('Facture'),
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': invoice.id,
            }

    def _create_invoice(self):
        """Crée une facture pour la réparation"""
        self.ensure_one()

        try:
            # Créer la facture
            invoice_vals = {
                'move_type': 'out_invoice',
                'partner_id': self.client_id.id,
                'invoice_date': fields.Date.today(),
                'invoice_origin': self.name,
                'invoice_line_ids': [],
            }

            # Ajouter les lignes de facture (uniquement les produits ajoutés)
            for line in self.repair_line_ids.filtered(lambda l: l.operation_type == 'add'):
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
                    'price_unit': line.price_unit,
                    'account_id': account.id
                }
                invoice_vals['invoice_line_ids'].append((0, 0, line_vals))

            # Créer la facture
            invoice = self.env['account.move'].create(invoice_vals)

            # Valider la facture
            try:
                invoice.action_post()  # Pour Odoo 13+
            except Exception as e:
                _logger.warning("Impossible de valider la facture: %s", str(e))
                # Ne pas bloquer si la validation échoue

            # Lier la facture à la réparation
            self.write({'invoice_id': invoice.id})

            return invoice

        except Exception as e:
            raise UserError(_("Erreur lors de la création de la facture: %s") % str(e))

    def action_cancel(self):
        """Annule la réparation"""
        for repair in self:
            # Annuler le bon de livraison s'il existe
            if repair.picking_id and repair.picking_id.state != 'cancel':
                if repair.picking_id.state == 'done':
                    raise UserError(_("Impossible d'annuler une réparation avec un bon de livraison déjà validé."))
                repair.picking_id.action_cancel()

            # Annuler le bon de retour s'il existe
            if repair.return_picking_id and repair.return_picking_id.state != 'cancel':
                if repair.return_picking_id.state == 'done':
                    raise UserError(_("Impossible d'annuler une réparation avec un bon de retour déjà validé."))
                repair.return_picking_id.action_cancel()

            # Mettre à jour l'état
            repair.write({'state': 'cancel'})

            # Mettre à jour le véhicule
            initial_status = self.env.ref('gpl_fleet.vehicle_status_nouveau', raise_if_not_found=False)
            if initial_status:
                repair.vehicle_id.write({
                    'status_id': initial_status.id,
                    'repair_order_id': False,
                    'next_service_type': False
                })

            msg = _("Réparation annulée par %s") % self.env.user.name
            repair.message_post(body=msg)

        return True

    def action_draft(self):
        """Remet la réparation en brouillon"""
        for repair in self:
            if (repair.picking_id and repair.picking_id.state == 'done') or \
                (repair.return_picking_id and repair.return_picking_id.state == 'done'):
                raise UserError(_("Impossible de remettre en brouillon une réparation avec un bon validé."))

            repair.write({'state': 'draft'})
            msg = _("Réparation remise en brouillon par %s") % self.env.user.name
            repair.message_post(body=msg)

        return True

    def action_view_sale_order(self):
        """Ouvre le bon de commande associé"""
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

    def action_view_picking(self):
        """Ouvre le bon de livraison associé"""
        self.ensure_one()
        if not self.picking_id:
            return

        return {
            'name': _('Bon de livraison'),
            'view_mode': 'form',
            'res_model': 'stock.picking',
            'res_id': self.picking_id.id,
            'type': 'ir.actions.act_window',
        }

    def action_view_return_picking(self):
        """Ouvre le bon de retour associé"""
        self.ensure_one()
        if not self.return_picking_id:
            return

        return {
            'name': _('Bon de retour'),
            'view_mode': 'form',
            'res_model': 'stock.picking',
            'res_id': self.return_picking_id.id,
            'type': 'ir.actions.act_window',
        }

    def action_view_invoice(self):
        """Ouvre la facture associée"""
        self.ensure_one()
        if not self.invoice_id:
            return

        return {
            'name': _('Facture'),
            'view_mode': 'form',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'type': 'ir.actions.act_window',
        }

    def action_view_products(self):
        """Ouvre la liste des produits utilisés"""
        self.ensure_one()

        return {
            'name': _('Produits utilisés'),
            'type': 'ir.actions.act_window',
            'res_model': 'gpl.repair.line',
            'view_mode': 'tree,form',
            'domain': [('repair_id', '=', self.id)],
            'context': {'default_repair_id': self.id},
        }

    def action_add_products(self):
        """Ouvre l'assistant pour ajouter des produits"""
        self.ensure_one()

        return {
            'name': _('Ajouter des produits'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'gpl.repair.add.products',
            'target': 'new',
            'context': {
                'default_repair_id': self.id,
                'default_client_id': self.client_id.id if self.client_id else False,
            }
        }

    def print_repair_order(self):
        """Imprime l'ordre de réparation"""
        self.ensure_one()
        return self.env.ref('gpl_fleet.action_report_gpl_repair_order').report_action(self)


class GplRepairLine(models.Model):
    _name = 'gpl.repair.line'
    _description = 'Ligne de réparation GPL'

    repair_id = fields.Many2one(
        'gpl.repair.order',
        string='Réparation',
        required=True,
        ondelete='cascade'
    )
    product_id = fields.Many2one(
        'product.product',
        string='Produit',
        required=True,
        domain="[('type', 'in', ['product', 'consu', 'service'])]"
    )
    name = fields.Char(string='Description', compute='_compute_name', store=True)
    product_uom_qty = fields.Float(string='Quantité', default=1.0)

    # Type d'opération (ajout ou retour)
    operation_type = fields.Selection([
        ('add', 'Ajouter'),
        ('remove', 'Retourner')
    ], string='Opération', default='add', required=True)

    # Informations de stock
    qty_available = fields.Float(
        string='Stock disponible',
        compute='_compute_qty_available',
        store=False
    )
    lot_id = fields.Many2one(
        'stock.lot',
        string='Numéro de lot/série',
        domain="[('product_id', '=', product_id)]"
    )
    available_lot_ids = fields.Many2many(
        'stock.lot',
        compute='_compute_available_lots',
        string='Lots disponibles'
    )

    # Informations de prix
    price_unit = fields.Float(
        string='Prix unitaire',
        compute='_compute_price',
        store=True
    )
    price_subtotal = fields.Float(
        string='Sous-total',
        compute='_compute_price',
        store=True
    )

    # Champs spécifiques aux réservoirs
    is_gpl_reservoir = fields.Boolean(
        string='Est un réservoir GPL',
        related='product_id.is_gpl_reservoir',
        store=True
    )

    @api.depends('product_id')
    def _compute_name(self):
        for line in self:
            line.name = line.product_id.name if line.product_id else ''

    @api.depends('product_id')
    def _compute_qty_available(self):
        for line in self:
            if line.product_id:
                line.qty_available = line.product_id.qty_available
            else:
                line.qty_available = 0.0

    @api.depends('product_id', 'repair_id.company_id')
    def _compute_available_lots(self):
        for line in self:
            if line.product_id and line.product_id.tracking != 'none':
                # Trouver les lots disponibles pour ce produit
                quants_domain = [
                    ('product_id', '=', line.product_id.id),
                    ('location_id.usage', '=', 'internal'),
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
                    ('company_id', '=', line.repair_id.company_id.id),
                    ('company_id', '=', False)
                ])

                line.available_lot_ids = lots
            else:
                line.available_lot_ids = False

    @api.depends('product_id', 'product_uom_qty', 'operation_type')
    def _compute_price(self):
        for line in self:
            if line.product_id:
                if line.operation_type == 'add':
                    line.price_unit = line.product_id.list_price
                    line.price_subtotal = line.price_unit * line.product_uom_qty
                else:
                    # Pour les retours, on utilise un prix négatif
                    line.price_unit = -line.product_id.list_price
                    line.price_subtotal = line.price_unit * line.product_uom_qty
            else:
                line.price_unit = 0.0
                line.price_subtotal = 0.0

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            # Si c'est un service, on définit par défaut comme "ajouter"
            if self.product_id.type == 'service':
                self.operation_type = 'add'
            # Si c'est un réservoir, vérifier s'il s'agit d'un remplacement
            if self.product_id.is_gpl_reservoir and self.repair_id and self.repair_id.vehicle_id and self.repair_id.vehicle_id.reservoir_lot_id:
                # Si le véhicule a déjà un réservoir, proposer de le retourner
                self.operation_type = 'add'
                # Créer une ligne de retour pour l'ancien réservoir
                old_reservoir = self.repair_id.vehicle_id.reservoir_lot_id.product_id
                if old_reservoir:
                    # Vérifier si une ligne de retour pour ce réservoir existe déjà
                    existing_remove_line = self.repair_id.repair_line_ids.filtered(
                        lambda l: l.product_id.id == old_reservoir.id and l.operation_type == 'remove'
                    )
                    if not existing_remove_line:
                        self.env['gpl.repair.line'].create({
                            'repair_id': self.repair_id.id,
                            'product_id': old_reservoir.id,
                            'product_uom_qty': 1.0,
                            'operation_type': 'remove',
                            'lot_id': self.repair_id.vehicle_id.reservoir_lot_id.id
                        })

    @api.onchange('lot_id')
    def onchange_lot_id(self):
        if self.lot_id and self.is_gpl_reservoir and self.operation_type == 'add':
            # Si un lot est sélectionné pour un nouveau réservoir, mettre à jour le véhicule
            if self.repair_id and self.repair_id.vehicle_id:
                # Mise à jour différée - sera faite à la complétion de la réparation
                self.repair_id.new_reservoir_lot_id = self.lot_id


class GplRepairAddProducts(models.TransientModel):
    _name = 'gpl.repair.add.products'
    _description = "Assistant d'ajout de produits pour réparation GPL"

    repair_id = fields.Many2one(
        'gpl.repair.order',
        string='Réparation',
        required=True
    )
    product_ids = fields.Many2many(
        'product.product',
        string='Produits à ajouter',
        domain="[('type', 'in', ['product', 'consu', 'service'])]"
    )
    operation_type = fields.Selection([
        ('add', 'Ajouter'),
        ('remove', 'Retourner')
    ], string='Opération', default='add', required=True)

    def add_products(self):
        self.ensure_one()

        if not self.product_ids:
            raise UserError(_("Veuillez sélectionner au moins un produit."))

        # Ajouter les produits à la réparation
        for product in self.product_ids:
            self.env['gpl.repair.line'].create({
                'repair_id': self.repair_id.id,
                'product_id': product.id,
                'product_uom_qty': 1.0,
                'operation_type': self.operation_type
            })

        return {'type': 'ir.actions.act_window_close'}
