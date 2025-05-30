import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class GplService(models.Model):
    _name = 'gpl.service.installation'
    _description = 'Installation GPL'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Nom du service", required=True, default="New", copy=False, readonly=True)

    # Réservoir GPL
    reservoir_lot_id = fields.Many2one('stock.lot', string="Suivi Réservoir GPL",
                                       domain="[('product_id.is_gpl_reservoir', '=', True)]", tracking=True)
    certification_number = fields.Char(related="reservoir_lot_id.certification_number",
                                       string="N° certification", readonly=True)
    certification_date = fields.Date(related="reservoir_lot_id.certification_date",
                                     string="Date certification", readonly=True)
    expiry_date = fields.Date(related="reservoir_lot_id.expiry_date",
                              string="Date expiration", readonly=True)
    reservoir_state = fields.Selection(related="reservoir_lot_id.state",
                                       string="État du réservoir", readonly=True)
    serial_number = fields.Char(related="reservoir_lot_id.name", string="N° série réservoir", readonly=True)

    # Dates
    date_service = fields.Date(string="Date du service")
    date_planned = fields.Date(string="Date planifiée")
    date_completion = fields.Date(string="Date de finalisation")

    # Relations
    vehicle_id = fields.Many2one('gpl.vehicle', string="Vehicule")
    client_id = fields.Many2one(related='vehicle_id.client_id', string="Client", store=True)
    technician_ids = fields.Many2many(
        'hr.employee',
        'gpl_installation_technician_rel',
        'installation_id',
        'employee_id',
        string="Techniciens",
        required=True,
        help="Équipe de techniciens assignée à cette installation"
    )

    # État
    state = fields.Selection([
        ('draft', 'Préparation'),
        ('planned', 'Planifié'),
        ('in_progress', 'En cours'),
        ('done', 'Terminé'),
        ('cancel', 'Annulé')
    ], string="État", default='draft', tracking=True)

    # Lignes et documents
    installation_line_ids = fields.One2many('gpl.installation.line', 'installation_id', string="Produits utilisés")
    picking_id = fields.Many2one('stock.picking', string="Bon de livraison")
    invoice_id = fields.Many2one('account.move', string="Facture")
    sale_order_id = fields.Many2one('sale.order', string="Bon de commande client", copy=False)
    notes = fields.Text(string="Notes")

    # Statistiques
    products_count = fields.Integer(string="Nombre de produits", compute="_compute_products_count", store=True)
    total_amount = fields.Float(string="Montant total", compute="_compute_total_amount", store=True)

    # Société et devise
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')

    # Configuration
    etancheite_pressure = fields.Float(string="Pression test étanchéité (bars)", default=10.0,
                                       help="Pression utilisée pour le test d'étanchéité du système GPL")
    use_simplified_flow = fields.Boolean(string="Flux simplifié", compute='_compute_use_simplified_flow')

    @api.depends('company_id')
    def _compute_use_simplified_flow(self):
        simplified_flow = self.env['ir.config_parameter'].sudo().get_param('gpl_fleet.simplified_flow',
                                                                           'False').lower() == 'true'
        for record in self:
            record.use_simplified_flow = simplified_flow

    @api.depends('installation_line_ids')
    def _compute_products_count(self):
        for record in self:
            record.products_count = len(record.installation_line_ids)

    @api.depends('installation_line_ids', 'installation_line_ids.price_subtotal')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = sum(record.installation_line_ids.mapped('price_subtotal'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Correction: test plus robuste pour le nom
            if not vals.get('name') or vals.get('name') in ['New', _('New'), 'Nouveau']:
                vals['name'] = self.env['ir.sequence'].next_by_code('gpl.service.installation') or _('New')

            # Techniciens par défaut - correction de la logique
            if not vals.get('technician_ids'):
                use_default_technician = self.env['ir.config_parameter'].sudo().get_param(
                    'gpl_fleet.use_default_technician', 'False').lower() == 'true'
                if use_default_technician:
                    default_technician_ids_json = self.env['ir.config_parameter'].sudo().get_param(
                        'gpl_fleet.default_technician_ids_json', '[]')
                    try:
                        import json
                        default_technician_ids = json.loads(default_technician_ids_json)
                        if default_technician_ids:
                            vals['technician_ids'] = [(6, 0, default_technician_ids)]
                    except Exception as e:
                        _logger.warning("Erreur lors de l'assignation des techniciens par défaut: %s", str(e))

            # Réservoir du véhicule - correction de la logique
            if vals.get('vehicle_id'):
                vehicle = self.env['gpl.vehicle'].browse(vals['vehicle_id'])
                if vehicle.exists() and vehicle.reservoir_lot_id:
                    vals['reservoir_lot_id'] = vehicle.reservoir_lot_id.id

        return super().create(vals_list)

    @api.onchange('vehicle_id')
    def onchange_vehicle_id(self):
        if self.vehicle_id:
            if self.vehicle_id.reservoir_lot_id:
                self.reservoir_lot_id = self.vehicle_id.reservoir_lot_id.id
            if self.vehicle_id.client_id:
                self.client_id = self.vehicle_id.client_id

    def action_validate_preparation(self):
        """Valide la préparation - version corrigée"""
        for record in self:
            # Validations de base renforcées
            errors = []

            if not record.vehicle_id:
                errors.append(_("Veuillez sélectionner un véhicule avant de continuer."))
            if not record.technician_ids:
                errors.append(_("Veuillez assigner au moins un technicien avant de continuer."))
            if not record.date_service:
                errors.append(_("Veuillez définir une date de service avant de continuer."))
            if not record.installation_line_ids:
                errors.append(_("Veuillez ajouter au moins un produit avant de continuer."))

            if errors:
                raise UserError("\n".join(errors))

            # Éclater les kits en composants
            record._explode_kits()

            # Validation des lots pour les produits avec tracking
            record._validate_lots_required()

            simplified_flow = record.use_simplified_flow

            if simplified_flow:
                # Mode simplifié : créer BC confirmé + BL prêt
                try:
                    sale_order = record._create_and_confirm_sale_order()
                    picking = record._create_picking_for_simplified_flow()

                    record.write({
                        'state': 'in_progress',
                        'date_planned': fields.Date.today(),
                        'sale_order_id': sale_order.id if sale_order else False,
                        'picking_id': picking.id if picking else False,
                    })

                    msg = _("Mode simplifié - Préparation validée : BC %s confirmé et BL %s préparé par %s") % (
                        sale_order.name if sale_order else "ERREUR",
                        picking.name if picking else "ERREUR",
                        self.env.user.name
                    )
                    record.message_post(body=msg)

                except Exception as e:
                    _logger.error("Erreur en mode simplifié: %s", str(e))
                    raise UserError(_("Erreur en mode simplifié: %s") % str(e))
            else:
                # Mode standard : créer seulement le BC
                if not record.sale_order_id and record.installation_line_ids:
                    record._create_sale_order()

                record.write({'state': 'planned', 'date_planned': fields.Date.today()})
                msg = _("Préparation validée par %s") % self.env.user.name
                record.message_post(body=msg)

        return True

    def _validate_lots_required(self):
        """Valide que tous les produits nécessitant un tracking ont un lot assigné"""
        self.ensure_one()

        missing_lots = []
        for line in self.installation_line_ids:
            if line.product_id.tracking in ['lot', 'serial']:
                if not line.lot_id:
                    missing_lots.append(f"• {line.product_id.name}")

        if missing_lots:
            raise UserError(_(
                "Les produits suivants nécessitent un numéro de lot/série.\n"
                "Veuillez les sélectionner dans la colonne 'Numéro de lot/série' :\n\n%s"
            ) % "\n".join(missing_lots))

    def _explode_kits(self):
        """Éclate les kits en leurs composants"""
        self.ensure_one()
        lines_to_unlink = self.env['gpl.installation.line']
        lines_to_create = []

        for line in self.installation_line_ids:
            if line.product_id.is_gpl_kit:
                components = self._get_kit_components(line.product_id, line.product_uom_qty)
                if components:
                    lines_to_unlink |= line
                    for component in components:
                        lines_to_create.append({
                            'installation_id': self.id,
                            'product_id': component['product_id'],
                            'product_uom_qty': component['qty'],
                            'price_unit': line.price_unit / len(components) if components else line.price_unit,
                        })

        if lines_to_unlink:
            lines_to_unlink.unlink()
        for vals in lines_to_create:
            self.env['gpl.installation.line'].create(vals)

    def _get_kit_components(self, kit_product, quantity=1.0):
        """Récupère les composants d'un kit"""
        result = []
        boms = self.env['mrp.bom'].sudo().search([
            '|',
            ('product_id', '=', kit_product.id),
            '&',
            ('product_id', '=', False),
            ('product_tmpl_id', '=', kit_product.product_tmpl_id.id),
        ], limit=1)

        if boms:
            for line in boms[0].bom_line_ids:
                result.append({
                    'product_id': line.product_id.id,
                    'qty': line.product_qty * quantity,
                })
        return result

    def _create_and_confirm_sale_order(self):
        """Crée et confirme un bon de commande client"""
        self.ensure_one()
        if not self.installation_line_ids or not self.client_id:
            return False

        try:
            so_vals = {
                'partner_id': self.client_id.id,
                'date_order': fields.Datetime.now(),
                'origin': self.name,
                'company_id': self.company_id.id,
                'order_line': [],
            }

            for line in self.installation_line_ids:
                so_vals['order_line'].append((0, 0, {
                    'product_id': line.product_id.id,
                    'name': line.product_id.name,
                    'product_uom_qty': line.product_uom_qty,
                    'product_uom': line.product_id.uom_id.id,
                    'price_unit': line.price_unit,
                }))

            sale_order = self.env['sale.order'].create(so_vals)
            if sale_order:
                sale_order.action_confirm()
            return sale_order

        except Exception as e:
            _logger.error("Erreur création BC: %s", str(e))
            raise UserError(_("Erreur lors de la création du bon de commande: %s") % str(e))

    def _create_picking_for_simplified_flow(self):
        """Crée un bon de livraison prêt pour le mode simplifié"""
        self.ensure_one()
        if not self.installation_line_ids or not self.client_id:
            return False

        try:
            picking_type = self.env['stock.picking.type'].search([('code', '=', 'outgoing')], limit=1)
            if not picking_type:
                raise UserError(_("Aucun type de picking configuré."))

            location_src_id = picking_type.default_location_src_id or self.env.ref('stock.stock_location_stock',
                                                                                   raise_if_not_found=False)
            location_dest_id = picking_type.default_location_dest_id or self.env.ref('stock.stock_location_customers',
                                                                                     raise_if_not_found=False)

            if not location_src_id or not location_dest_id:
                raise UserError(_("Emplacements source ou destination non configurés."))

            move_vals = []
            for line in self.installation_line_ids:
                vals = {
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'product_uom': line.product_id.uom_id.id,
                    'location_id': location_src_id.id,
                    'location_dest_id': location_dest_id.id,
                }

                # Gestion compatibilité version Odoo pour quantité
                if 'quantity' in self.env['stock.move']._fields:
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

            # Confirmer et assigner
            picking.action_confirm()
            picking.action_assign()

            # Assigner les lots spécifiés
            self._assign_lots_to_picking(picking)

            return picking

        except Exception as e:
            _logger.error("Erreur création BL: %s", str(e))
            raise UserError(_("Erreur lors de la création du bon de livraison: %s") % str(e))

    def _assign_lots_to_picking(self, picking):
        """Assigne les lots choisis aux mouvements du picking"""
        for line in self.installation_line_ids:
            if line.lot_id and line.product_id:
                move = picking.move_ids.filtered(lambda m: m.product_id.id == line.product_id.id)
                if move:
                    # Supprimer les move_lines existantes
                    move.move_line_ids.unlink()

                    # Créer la move_line avec le lot
                    move_line_vals = {
                        'move_id': move.id,
                        'product_id': move.product_id.id,
                        'product_uom_id': move.product_uom.id,
                        'location_id': move.location_id.id,
                        'location_dest_id': move.location_dest_id.id,
                        'lot_id': line.lot_id.id,
                    }

                    # Ajouter la quantité selon la version
                    qty_fields = ['reserved_uom_qty', 'product_uom_qty', 'quantity']
                    for field in qty_fields:
                        if field in self.env['stock.move.line']._fields:
                            move_line_vals[field] = line.product_uom_qty

                    self.env['stock.move.line'].create(move_line_vals)

    def _create_sale_order(self):
        """Crée un bon de commande client standard"""
        self.ensure_one()
        if not self.installation_line_ids or not self.client_id:
            return False

        so_vals = {
            'partner_id': self.client_id.id,
            'date_order': fields.Datetime.now(),
            'origin': self.name,
            'company_id': self.company_id.id,
            'order_line': [],
        }

        for line in self.installation_line_ids:
            so_vals['order_line'].append((0, 0, {
                'product_id': line.product_id.id,
                'name': line.product_id.name,
                'product_uom_qty': line.product_uom_qty,
                'product_uom': line.product_id.uom_id.id,
                'price_unit': line.price_unit,
            }))

        sale_order = self.env['sale.order'].create(so_vals)
        self.write({'sale_order_id': sale_order.id})

        msg = _("Bon de commande client %s créé.") % sale_order.name
        self.message_post(body=msg)
        return sale_order

    def action_create_picking(self):
        """Crée un bon de livraison en mode standard"""
        self.ensure_one()
        if not self.installation_line_ids:
            return {
                'name': _('Ajouter des produits'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'gpl.installation.add.products',
                'target': 'new',
                'context': {'default_installation_id': self.id,
                            'default_client_id': self.client_id.id if self.client_id else False}
            }

        if not self.client_id:
            raise UserError(_("Aucun client associé au véhicule."))

        try:
            picking = self._create_picking_for_simplified_flow()  # Réutilise la même méthode
            if picking:
                self.write({'picking_id': picking.id, 'state': 'in_progress'})
                msg = _("Bon de livraison %s créé et matériel réservé.") % picking.name
                self.message_post(body=msg)

                return {
                    'name': _('Bon de Livraison'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'stock.picking',
                    'view_mode': 'form',
                    'res_id': picking.id,
                }
        except Exception as e:
            raise UserError(_("Erreur: %s") % str(e))

    def action_complete_installation(self):
        """Termine l'installation - version corrigée"""
        for record in self:
            try:
                simplified_flow = record.use_simplified_flow

                # Valider le bon de livraison
                if record.picking_id and record.picking_id.state != 'done':
                    record._validate_picking()

                # Créer facture si auto-facturation activée
                auto_invoice = self.env['ir.config_parameter'].sudo().get_param('gpl_fleet.auto_invoice',
                                                                                'False').lower() == 'true'
                invoice = None
                if auto_invoice and not record.invoice_id:
                    try:
                        invoice = record._create_invoice()
                    except Exception as e:
                        _logger.warning("Impossible de créer la facture automatiquement: %s", str(e))

                # Marquer comme terminé
                record.write({'state': 'done', 'date_completion': fields.Date.today()})

                # Mettre à jour le véhicule
                record._update_vehicle_after_installation()

                # Message de confirmation
                msg_parts = ["Installation terminée"]
                if record.picking_id and record.picking_id.state == 'done':
                    msg_parts.append(f"bon de livraison {record.picking_id.name} validé")
                if invoice:
                    msg_parts.append(f"facture {invoice.name} créée")

                msg = _("%s par %s") % (", ".join(msg_parts), self.env.user.name)
                record.message_post(body=msg)

                return True

            except Exception as e:
                _logger.error("Erreur lors de la finalisation de l'installation %s: %s", record.name, str(e))
                raise UserError(_("Erreur lors de la finalisation: %s") % str(e))

    def _validate_picking(self):
        """Valide le bon de livraison en s'assurant que tous les lots sont assignés"""
        self.ensure_one()
        if not self.picking_id:
            return False

        try:
            _logger.info("=== DÉBUT VALIDATION PICKING %s ===", self.picking_id.name)

            # Étape 1: Vérifier et forcer l'assignation des lots
            self._force_assign_lots_to_picking_moves()

            # Étape 2: Définir les quantités traitées
            for move in self.picking_id.move_ids.filtered(lambda m: m.state not in ['done', 'cancel']):
                install_line = self.installation_line_ids.filtered(lambda l: l.product_id.id == move.product_id.id)
                qty_to_process = install_line.product_uom_qty if install_line else 1.0

                _logger.info(f"Traitement mouvement {move.name} - Produit: {move.product_id.name}")
                _logger.info(f"Quantité à traiter: {qty_to_process}")

                # S'assurer qu'il y a des move_lines
                if not move.move_line_ids:
                    _logger.warning(f"Aucune move_line pour {move.name}, création...")
                    self._create_move_line_for_move(move, install_line)

                # Définir les quantités sur les move_lines
                for move_line in move.move_line_ids:
                    # Correction: gestion robuste des champs de quantité
                    qty_fields = ['qty_done', 'quantity_done', 'product_uom_qty']
                    for field_name in qty_fields:
                        if hasattr(move_line, field_name):
                            setattr(move_line, field_name, qty_to_process)
                            break

                    _logger.info(
                        f"Move_line {move_line.id} - Lot: {move_line.lot_id.name if move_line.lot_id else 'AUCUN'}")

            # Étape 3: Valider le picking
            _logger.info("Validation du picking...")
            if hasattr(self.picking_id, 'button_validate'):
                self.picking_id.button_validate()
            else:
                # Fallback pour anciennes versions
                self.picking_id.action_done()

            _logger.info("=== PICKING VALIDÉ AVEC SUCCÈS ===")
            return True

        except Exception as e:
            _logger.error("Erreur validation BL: %s", str(e))
            raise UserError(_("Erreur lors de la validation du bon de livraison: %s") % str(e))

    def _force_assign_lots_to_picking_moves(self):
        """Force l'assignation des lots depuis les lignes d'installation vers les mouvements du picking"""
        self.ensure_one()

        _logger.info("=== ASSIGNATION FORCÉE DES LOTS ===")

        for move in self.picking_id.move_ids:
            install_line = self.installation_line_ids.filtered(lambda l: l.product_id.id == move.product_id.id)

            if not install_line:
                _logger.warning(f"Aucune ligne d'installation trouvée pour {move.product_id.name}")
                continue

            _logger.info(f"Traitement produit: {move.product_id.name}")
            _logger.info(f"Tracking: {move.product_id.tracking}")
            _logger.info(f"Lot choisi: {install_line.lot_id.name if install_line.lot_id else 'AUCUN'}")

            # Si le produit nécessite un tracking et qu'un lot est spécifié
            if move.product_id.tracking in ['lot', 'serial'] and install_line.lot_id:
                # Supprimer toutes les move_lines existantes
                move.move_line_ids.unlink()

                # Créer une nouvelle move_line avec le lot spécifique
                move_line_vals = {
                    'move_id': move.id,
                    'product_id': move.product_id.id,
                    'product_uom_id': move.product_uom.id,
                    'location_id': move.location_id.id,
                    'location_dest_id': move.location_dest_id.id,
                    'lot_id': install_line.lot_id.id,
                }

                # Ajouter les champs de quantité selon la version Odoo
                qty = install_line.product_uom_qty
                StockMoveLine = self.env['stock.move.line']

                for field_name in ['reserved_uom_qty', 'product_uom_qty', 'quantity']:
                    if field_name in StockMoveLine._fields:
                        move_line_vals[field_name] = qty

                # Créer la move_line
                new_move_line = StockMoveLine.create(move_line_vals)
                _logger.info(f"Move_line créée avec lot {install_line.lot_id.name} pour {move.product_id.name}")

                # Vérifier que le lot a bien été assigné
                if not new_move_line.lot_id:
                    raise UserError(_("Échec de l'assignation du lot %s au produit %s") % (
                    install_line.lot_id.name, move.product_id.name))

            elif move.product_id.tracking in ['lot', 'serial'] and not install_line.lot_id:
                raise UserError(
                    _("Le produit %s nécessite un numéro de lot/série mais aucun n'est spécifié dans les lignes d'installation.") % move.product_id.name)

            else:
                # Produit sans tracking - s'assurer qu'il y a une move_line
                if not move.move_line_ids:
                    self._create_move_line_for_move(move, install_line)

    def _create_move_line_for_move(self, move, install_line):
        """Crée une move_line pour un mouvement donné"""
        move_line_vals = {
            'move_id': move.id,
            'product_id': move.product_id.id,
            'product_uom_id': move.product_uom.id,
            'location_id': move.location_id.id,
            'location_dest_id': move.location_dest_id.id,
        }

        # Ajouter le lot si nécessaire
        if install_line and install_line.lot_id:
            move_line_vals['lot_id'] = install_line.lot_id.id

        # Ajouter la quantité - correction pour compatibilité
        qty = install_line.product_uom_qty if install_line else 1.0
        StockMoveLine = self.env['stock.move.line']

        # Définir la quantité avec fallback
        qty_fields = ['reserved_uom_qty', 'product_uom_qty', 'quantity']
        for field_name in qty_fields:
            if field_name in StockMoveLine._fields:
                move_line_vals[field_name] = qty
                break

        return StockMoveLine.create(move_line_vals)

    def _update_vehicle_after_installation(self):
        """Met à jour le véhicule après installation"""
        self.ensure_one()
        if not self.vehicle_id:
            return

        # Récupérer le statut "En attente de validation"
        validation_status = self.env.ref('gpl_fleet.vehicle_status_attente_validation', raise_if_not_found=False)
        if not validation_status:
            # Fallback sur un statut par défaut
            validation_status = self.env['gpl.vehicle.status'].search([('name', 'ilike', 'validation')], limit=1)
            if not validation_status:
                validation_status = self.env['gpl.vehicle.status'].search([], limit=1)

        vehicle_values = {
            'status_id': validation_status.id if validation_status else False,
            'next_service_type': 'inspection',
            'installation_id': self.id
        }

        # Associer le réservoir installé
        reservoir_line = self.installation_line_ids.filtered(lambda l: l.product_id.is_gpl_reservoir and l.lot_id)
        if reservoir_line:
            vehicle_values['reservoir_lot_id'] = reservoir_line[0].lot_id.id
            # Mettre à jour aussi le lot pour qu'il pointe vers le véhicule
            reservoir_line[0].lot_id.write({'vehicle_id': self.vehicle_id.id})
            msg = _("Réservoir GPL %s installé.") % reservoir_line[0].lot_id.name
            self.vehicle_id.message_post(body=msg)

        self.vehicle_id.write(vehicle_values)

    def _create_invoice(self):
        """Crée une facture"""
        self.ensure_one()
        if not self.client_id or not self.installation_line_ids:
            return False

        try:
            invoice_vals = {
                'move_type': 'out_invoice',
                'partner_id': self.client_id.id,
                'invoice_date': fields.Date.today(),
                'invoice_origin': self.name,
                'invoice_line_ids': [],
            }

            for line in self.installation_line_ids:
                account = self._get_income_account(line.product_id)
                invoice_vals['invoice_line_ids'].append((0, 0, {
                    'product_id': line.product_id.id,
                    'quantity': line.product_uom_qty,
                    'name': f"{self.name}: {line.product_id.name}",
                    'price_unit': line.price_unit if line.price_unit > 0 else line.product_id.list_price,
                    'account_id': account.id
                }))

            invoice = self.env['account.move'].create(invoice_vals)
            try:
                invoice.action_post()
            except:
                pass  # Ne pas bloquer si la validation échoue

            self.write({'invoice_id': invoice.id})
            return invoice

        except Exception as e:
            _logger.error("Erreur création facture: %s", str(e))
            return False

    def _get_income_account(self, product):
        """Trouve le compte de revenu pour un produit"""
        if product.property_account_income_id:
            return product.property_account_income_id
        elif product.categ_id.property_account_income_categ_id:
            return product.categ_id.property_account_income_categ_id
        else:
            account_journal = self.env['account.journal'].search(
                [('type', '=', 'sale'), ('company_id', '=', self.company_id.id)], limit=1)
            if account_journal and account_journal.default_account_id:
                return account_journal.default_account_id
            else:
                account = self.env['account.account'].search(
                    [('company_id', '=', self.company_id.id), ('account_type', '=', 'income')], limit=1)
                if not account:
                    raise UserError(
                        _("Impossible de déterminer un compte de revenus pour le produit %s.") % product.name)
                return account

    # Actions pour les vues
    def action_view_sale_order(self):
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
            'context': {'default_installation_id': self.id, 'create': True}
        }

    def action_invoice(self):
        self.ensure_one()
        if self.state != 'done':
            raise UserError(_("L'installation doit être terminée avant de pouvoir facturer."))
        if self.invoice_id:
            raise UserError(_("Une facture existe déjà pour cette installation."))

        try:
            invoice = self._create_invoice()
            if not invoice:
                raise UserError(_("Impossible de créer la facture."))

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
            if record.picking_id and record.picking_id.state != 'cancel':
                if record.picking_id.state == 'done':
                    raise UserError(_("Impossible d'annuler une installation avec un bon de livraison déjà validé."))
                record.picking_id.action_cancel()

            record.write({'state': 'cancel'})
            msg = _("Installation annulée par %s") % self.env.user.name
            record.message_post(body=msg)
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
            'context': {'default_installation_id': self.id,
                        'default_client_id': self.client_id.id if self.client_id else False}
        }

    def get_certification_text(self):
        """Récupère le texte de certification depuis les paramètres"""
        return self.env['ir.config_parameter'].sudo().get_param(
            'gpl_fleet.certification_text',
            """Certifions que le véhicule décrit ci-dessous a été équipé conformément aux prescriptions de l'arrêté
du 31 Août 1983 relatif aux conditions d'équipement de surveillance et d'exploitation des installations
de GPL équipant les véhicules automobiles."""
        )


class GplInstallationLine(models.Model):
    _name = 'gpl.installation.line'
    _description = "Lignes de produits utilisés pour l'installation"

    installation_id = fields.Many2one('gpl.service.installation', string="Installation", required=True,
                                      ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Produit", required=True)
    product_uom_qty = fields.Float(string="Quantité", default=1.0)
    qty_available = fields.Float(string="Stock dispo", compute="_compute_qty_available", store=False)
    price_unit = fields.Float(string="Prix unitaire", compute="_compute_price", store=True)
    price_subtotal = fields.Float(string="Sous-total", compute="_compute_price", store=True)
    serial_number = fields.Char(string='Numéro de série')
    lot_id = fields.Many2one('stock.lot', string='Numéro de lot/série')
    is_gpl_reservoir = fields.Boolean(string='Est un réservoir GPL', related='product_id.is_gpl_reservoir', store=True)
    available_lot_ids = fields.Many2many('stock.lot', compute='_compute_available_lots', string='Lots disponibles')

    # Champs pour améliorer l'interface utilisateur
    tracking_required = fields.Boolean(string='Lot requis', compute='_compute_tracking_info', store=False)
    tracking_info = fields.Char(string='Info tracking', compute='_compute_tracking_info', store=False)

    @api.depends('product_id')
    def _compute_tracking_info(self):
        for line in self:
            if line.product_id:
                if line.product_id.tracking == 'serial':
                    line.tracking_required = True
                    line.tracking_info = "Numéro de série requis"
                elif line.product_id.tracking == 'lot':
                    line.tracking_required = True
                    line.tracking_info = "Numéro de lot requis"
                else:
                    line.tracking_required = False
                    line.tracking_info = ""
            else:
                line.tracking_required = False
                line.tracking_info = ""

    @api.depends('product_id', 'installation_id.company_id')
    def _compute_available_lots(self):
        for line in self:
            if line.product_id and line.product_id.tracking != 'none':
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', line.product_id.id),
                    ('location_id.usage', '=', 'internal'),
                    ('quantity', '>', 0)
                ])
                lot_ids = quants.mapped('lot_id').ids
                lots = self.env['stock.lot'].search([
                    ('id', 'in', lot_ids),
                    '|', ('company_id', '=', line.installation_id.company_id.id), ('company_id', '=', False)
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

    @api.depends('product_id')
    def _compute_qty_available(self):
        for line in self:
            line.qty_available = line.product_id.qty_available if line.product_id else 0.0

    @api.onchange('lot_id')
    def onchange_lot_id(self):
        """Mettre à jour le numéro de série et le produit quand un lot est sélectionné"""
        if self.lot_id:
            self.serial_number = self.lot_id.name
            if not self.product_id:
                self.product_id = self.lot_id.product_id.id

            # Si c'est un réservoir GPL, mettre à jour l'installation
            if self.lot_id.product_id.is_gpl_reservoir and self.installation_id:
                self.installation_id.reservoir_lot_id = self.lot_id.id

    @api.onchange('product_id')
    def onchange_product_id(self):
        """Actions à effectuer quand le produit change"""
        if self.product_id:
            # Réinitialiser le lot si le produit change
            if self.lot_id and self.lot_id.product_id.id != self.product_id.id:
                self.lot_id = False
                self.serial_number = False

            # Si c'est un produit avec tracking, informer l'utilisateur
            if self.product_id.tracking in ['lot', 'serial']:
                # Le message sera affiché via la décoration dans la vue
                pass

    @api.model
    def create(self, values):
        line = super().create(values)

        # Gestion automatique des réservoirs GPL
        if line.product_id and line.product_id.is_gpl_reservoir and line.installation_id:
            if line.lot_id:
                line.installation_id.write({'reservoir_lot_id': line.lot_id.id})
            elif line.serial_number:
                # Rechercher ou créer le lot
                lot = self.env['stock.lot'].search([
                    ('name', '=', line.serial_number),
                    ('product_id', '=', line.product_id.id)
                ], limit=1)

                if not lot:
                    lot = self.env['stock.lot'].create({
                        'name': line.serial_number,
                        'product_id': line.product_id.id,
                        'company_id': line.installation_id.company_id.id,
                    })

                line.write({'lot_id': lot.id})
                line.installation_id.write({'reservoir_lot_id': lot.id})

        return line


class GplInstallationAddProducts(models.TransientModel):
    _name = 'gpl.installation.add.products'
    _description = 'Assistant d\'ajout de produits pour installation GPL'

    installation_id = fields.Many2one('gpl.service.installation', string='Installation', required=True,
                                      default=lambda self: self.env.context.get('active_id'))
    product_ids = fields.Many2many('product.product', string='Produits à ajouter',
                                   domain="[('type', 'in', ['product', 'consu'])]")

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        if 'installation_id' in fields and not res.get('installation_id') and self.env.context.get('active_id'):
            res['installation_id'] = self.env.context.get('active_id')
        return res

# Supprimer les modèles non utilisés GplInstallationProductLine - ils créent de la confusion
