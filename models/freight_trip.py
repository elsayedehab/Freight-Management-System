# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import requests
import urllib.parse
import logging
_logger = logging.getLogger(__name__)


class FreightTrip(models.Model):
    _name = 'freight.trip'
    _description = 'Freight Trip Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Trip Reference',
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: 'New'
    )

    # ── Route Info ───────────────────────────────────────────────
    starting_point_id = fields.Many2one('res.country.state', string='Starting Point', ondelete='set null', domain="[('country_id', 'in', [192])]")
    destination_id    = fields.Many2one('res.country.state', string='Destination', ondelete='set null', domain="[('country_id', 'in', [192])]")
    distance_km       = fields.Float(string='Distance (KM)')

    # ── Carrier Info ─────────────────────────────────────────────
    driver_id  = fields.Many2one('hr.employee', string='Driver')
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle')

  

    # ── Status ───────────────────────────────────────────────────
    state = fields.Selection([
        ('draft',     'Draft'),
        ('confirmed', 'Confirmed'),
        ('in_transit','In Transit'),
        ('delivered', 'Delivered'),
        ('invoiced',  'Invoiced'),
    ], string='Status', default='draft', tracking=True)

    # ── Safety & Compliance — Vehicle Checks ─────────────────────
    tyre_pressure_check_doc = fields.Many2many(
        'ir.attachment',
        'freight_trip_tyre_doc_rel',
        'trip_id', 'attachment_id',
        string='Tyre Pressure Check'
    )
    brake_lights_doc = fields.Many2many(
        'ir.attachment',
        'freight_trip_brake_doc_rel',
        'trip_id', 'attachment_id',
        string='Brake Lights'
    )
    oil_level_doc = fields.Many2many(
        'ir.attachment',
        'freight_trip_oil_doc_rel',
        'trip_id', 'attachment_id',
        string='Oil Level'
    )

    # ── Safety & Compliance — Safety Gear ────────────────────────
    fire_extinguisher_doc = fields.Many2many(
        'ir.attachment',
        'freight_trip_fire_doc_rel',
        'trip_id', 'attachment_id',
        string='Fire Extinguisher'
    )
    emergency_triangle_doc = fields.Many2many(
        'ir.attachment',
        'freight_trip_triangle_doc_rel',
        'trip_id', 'attachment_id',
        string='Emergency Triangle'
    )
    first_aid_kit_doc = fields.Many2many(
        'ir.attachment',
        'freight_trip_firstaid_doc_rel',
        'trip_id', 'attachment_id',
        string='First Aid Kit'
    )
    barriers_doc = fields.Many2many(
        'ir.attachment',
        'freight_trip_barriers_doc_rel',
        'trip_id', 'attachment_id',
        string='Barriers'
    )
    cargo_cover_doc = fields.Many2many(
        'ir.attachment',
        'freight_trip_cargo_cover_doc_rel',
        'trip_id', 'attachment_id',
        string='Cargo Cover'
    )


    # ── Carrier Info Extra ───────────────────────────────────────
    driver_phone   = fields.Char(
        string='Driver Phone',
        related='driver_id.mobile_phone',
        readonly=True
    )
    license_plate  = fields.Char(
        string='License Plate',
        related='vehicle_id.license_plate',
        readonly=True
    )

    # ── Shipment Info ────────────────────────────────────────────
    cargo_type     = fields.Char(string='Cargo Type')
    weight_kg      = fields.Float(string='Weight (KG)')
    container_no   = fields.Char(string='Container No')

   
    # ── Smart Buttons ────────────────────────────────────────────
 
    # ── Customer Billing ─────────────────────────────────────────
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        tracking=True,
        domain="[('customer_rank', '>', 0)]"
    )
    company_id  = fields.Many2one('res.company', 'Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', 'Currency', related="company_id.currency_id")

    freight_charge = fields.Monetary(
        string='Freight Charge (Nawlon)',
        required=True,
        tracking=True,
        currency_field='currency_id'
    )
    additional_services_amount = fields.Monetary(
        string='Additional Services',
        default=0.0,
        tracking=True
    )
    total_invoice_amount = fields.Monetary(
        string='Total Invoice Amount',
        compute='_compute_total_invoice',
        store=True
    )
    invoice_ids = fields.One2many(
        'account.move',
        'freight_trip_id',
        string='Customer Invoices',
        readonly=True,
        copy=False
    )
    invoice_count = fields.Integer(
        string='Invoices Count',
        compute='_compute_invoice_count'
    )
    invoice_state = fields.Selection([
        ('not_created', 'Not Created'),
        ('draft',       'Draft Invoice'),
        ('posted',      'Posted'),
        ('cancel',      'Cancelled'),
    ], string='Invoice Status', default='not_created',
       compute='_compute_invoice_state')

    # ── Sales Order ───────────────────────────────────────────────
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        readonly=True,
        copy=False,
        ondelete='set null'
    )

    supervisor_signature = fields.Binary(string='Supervisor Signature')
    supervisor_signature_date = fields.Datetime(string='Supervisor Signature Date', readonly=True)

    # ── ORM ──────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('freight.trip') or 'New'
                )
        return super().create(vals_list)

    # ── Actions ──────────────────────────────────────────────────
    def action_in_transit(self):
        # ── send email to customer and driver ──────────────────────
        transit_template = self.env.ref(
            'Freight_Management_System.email_template_trip_in_transit',
            raise_if_not_found=False
        )
        for rec in self:
            if transit_template:
                if rec.partner_id.email:
                    transit_template.send_mail(rec.id, force_send=True)
                if rec.driver_id and rec.driver_id.work_email:
                    transit_template.send_mail(
                        rec.id,
                        email_values={'email_to': rec.driver_id.work_email},
                        force_send=True
                    )

        # ── change state ───────────────────────────────────────────
        self.write({'state': 'in_transit'})

       

    def action_delivered(self):
        self.write({'state': 'delivered'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_confirm(self):
        for rec in self:
            missing = []
            if not rec.tyre_pressure_check_doc:   missing.append('- Tyre Pressure Check')
            if not rec.brake_lights_doc:           missing.append('- Brake Lights')
            if not rec.oil_level_doc:              missing.append('- Oil Level')
            if not rec.fire_extinguisher_doc:      missing.append('- Fire Extinguisher')
            if not rec.emergency_triangle_doc:     missing.append('- Emergency Triangle')
            if not rec.first_aid_kit_doc:          missing.append('- First Aid Kit')
            if not rec.barriers_doc:               missing.append('- Barriers')
            if not rec.cargo_cover_doc:            missing.append('- Cargo Cover')

            if missing:
                raise UserError(
                    _("Cannot confirm trip!\n"
                    "Please upload documents for:\n") +
                    "\n".join(missing)
                )

        # ── send email to customer and driver ──────────────────────
        confirm_template = self.env.ref(
            'Freight_Management_System.email_template_trip_confirmed',
            # raise_if_not_found=False
        )
        for rec in self:
            if confirm_template:
                if rec.partner_id.email:
                    confirm_template.send_mail(rec.id, force_send=True)
                if rec.driver_id and rec.driver_id.work_email:
                    confirm_template.send_mail(
                        rec.id,
                        email_values={'email_to': rec.driver_id.work_email},
                        force_send=True
                    )

        # ── change state ───────────────────────────────────────────
        self.write({'state': 'confirmed'})

       
    @api.onchange('supervisor_signature')
    def _onchange_supervisor_signature(self):
        if self.supervisor_signature:
            self.supervisor_signature_date = fields.Datetime.now()
        else:
            self.supervisor_signature_date = False


    # ── Computes ─────────────────────────────────────────────────
 


    @api.depends('freight_charge', 'additional_services_amount')
    def _compute_total_invoice(self):
        for rec in self:
            rec.total_invoice_amount = rec.freight_charge + rec.additional_services_amount

    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for rec in self:
            rec.invoice_count = len(rec.invoice_ids)

    @api.depends('invoice_ids.state')
    def _compute_invoice_state(self):
        for rec in self:
            if not rec.invoice_ids:
                rec.invoice_state = 'not_created'
            else:
                last = rec.invoice_ids.sorted('id', reverse=True)[0]
                rec.invoice_state = last.state if last.state in ['draft', 'posted', 'cancel'] else 'not_created'

    

    # ── Smart Button Actions ──────────────────────────────────────
  
    def action_view_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Customer Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('freight_trip_id', '=', self.id)],
            'context': {'default_freight_trip_id': self.id},
        }

    def action_view_sale_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sales Order'),
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    

    

    # ── Freight Product Helper ────────────────────────────────────
    def _get_freight_product(self):
        product = self.env['product.product'].search([
            ('name', '=', 'Freight Service'),
            ('type', '=', 'service'),
        ], limit=1)
        if not product:
            product = self.env['product.product'].create({
                'name': 'Freight Service',
                'type': 'service',
                'invoice_policy': 'order',
            })
        return product

    # ── Invoice ───────────────────────────────────────────────────
    def action_create_customer_invoice(self):
        self.ensure_one()

        if not self.partner_id:
            raise UserError(_("Please select a Customer first!"))
        if self.state != 'delivered':
            raise UserError(_("You can only create invoice after marking the trip as Delivered!"))

        # 1. create new sales order for each invoice to avoid odoo constraints
        product = self._get_freight_product()
        order_lines = [(0, 0, {
            'product_id': product.id,
            'name': f'Freight Charge - {self.name}',
            'product_uom_qty': 1,
            'price_unit': self.freight_charge,
        })]
        
        if self.additional_services_amount > 0:
            order_lines.append((0, 0, {
                'product_id': product.id,
                'name': f'Additional Services - {self.name}',
                'product_uom_qty': 1,
                'price_unit': self.additional_services_amount,
            }))

        # create new sales order
        new_sale_order = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'origin': f"{self.name} (Extra Invoice)",
            'order_line': order_lines,
        })
        new_sale_order.action_confirm()

        # 2. create new invoice from the new sales order
        invoice = new_sale_order._create_invoices(final=True)
        
        if not invoice:
            raise UserError(_("Could not generate a new invoice. Please check product settings."))

        # 3. link invoice to the current trip to show it in the smart button
        invoice.write({'freight_trip_id': self.id})
        
        # update the sale_order_id in the trip to be the last one
        self.write({
            'sale_order_id': new_sale_order.id,
            'state': 'invoiced'
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Customer Invoice'),
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_send_email_customer(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_("Please select a Customer first!"))
        if not self.partner_id.email:
            raise UserError(_("Customer has no email address!"))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Send Waybill by Email'),
            'res_model': 'freight.trip.send.mail',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_trip_id': self.id,
            }
        }

   