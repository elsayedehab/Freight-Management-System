# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class TripExpense(models.Model):
    _name = 'trip.expense'
    _description = 'Trip Expense'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Reference',
        required=True, copy=False,
        readonly=True, index=True,
        default=lambda self: 'New'
    )

    # ── Links ────────────────────────────────────────────────────
    advance_id = fields.Many2one(
        'driver.advance', string='Driver Advance',
        required=True, ondelete='restrict',
        tracking=True,
        domain="[('state', 'in', ['issued', 'partial'])]"
    )
    trip_id = fields.Many2one(
        'freight.trip', string='Trip',
        related='advance_id.trip_id',
        store=True, readonly=True
    )
    driver_id = fields.Many2one(
        'hr.employee', string='Driver',
        related='advance_id.driver_id',
        store=True, readonly=True
    )

    # ── Expense Details ──────────────────────────────────────────
    expense_type = fields.Selection([
        ('fuel',        'Fuel / Diesel'),
        ('road_fees',   'Road Fees / Tolls'),
        ('accommodation', 'Accommodation'),
        ('fines',       'Fines / Penalties'),
        ('maintenance', 'Vehicle Maintenance'),
        ('loading',     'Loading / Unloading'),
        ('other',       'Other'),
    ], string='Expense Type', required=True, tracking=True)

    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.today,
        tracking=True
    )
    amount = fields.Monetary(
        string='Amount',
        required=True, tracking=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='advance_id.currency_id',
        store=True
    )
    notes = fields.Char(string='Notes / Description')

    # ── Invoice Attachment ───────────────────────────────────────
    invoice_image = fields.Many2many(
        'ir.attachment',
        'trip_expense_attachment_rel',
        'expense_id', 'attachment_id',
        string='Invoice / Receipt'
    )

    # ── Status ───────────────────────────────────────────────────
    state = fields.Selection([
        ('draft',     'Draft'),
        ('confirmed', 'Confirmed'),
        ('canceled',  'Canceled'),
    ], string='Status', default='draft',
       tracking=True, copy=False)

    confirmed_by = fields.Many2one(
        'res.users', string='Confirmed By',
        readonly=True
    )

    account_id = fields.Many2one(
        'account.account',
        string='Account',
        related='advance_id.payment_account_id',
        store=True,
        readonly=True,
        tracking=True
    )

    move_id = fields.Many2one(
        'account.move',
        string='Journal Entry',
        readonly=True,
        copy=False,
        ondelete='set null'
    )

    # ── ORM ──────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('trip.expense') or 'New'
                )
        return super().create(vals_list)

    # ── Constraints ──────────────────────────────────────────────
    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise UserError(_("Expense amount must be greater than zero!"))

    # ── Actions ──────────────────────────────────────────────────
    def action_confirm(self):
        for rec in self:
            if not rec.invoice_image:
                raise UserError(_("Please attach an invoice or receipt before confirming!"))

            ICP = self.env['ir.config_parameter'].sudo()
            advance_account_id = int(ICP.get_param('freight_management_system.driver_advance_account_id', 0))
            journal_id = int(ICP.get_param('freight_management_system.driver_advance_journal_id', 0))

            if not advance_account_id or not journal_id:
                raise UserError(_("Please configure Driver Advance Account and Journal in Settings!"))

            advance_account = self.env['account.account'].browse(advance_account_id)
            journal = self.env['account.journal'].browse(journal_id)

            expense_account = rec.account_id
            if not expense_account:
                raise UserError(_("No payment account found on the related advance!"))

            move = self.env['account.move'].create({
                'journal_id': journal.id,
                'date': rec.date,
                'ref': f"{rec.advance_id.name} - {rec.name}",
                'line_ids': [
                    # Debit: Actual Expense Account (Road Fees, Fuel, etc.)
                    (0, 0, {
                        'account_id': expense_account.id,
                        'name': rec.notes or rec.expense_type,
                        'debit': rec.amount,
                        'credit': 0.0,
                        'partner_id': getattr(rec.driver_id, 'address_home_id', rec.driver_id.user_id.partner_id).id if (hasattr(rec.driver_id, 'address_home_id') and rec.driver_id.address_home_id) or rec.driver_id.user_id.partner_id else False,
                    }),
                    # Credit: Driver Advance Account (Asset reduction)
                    (0, 0, {
                        'account_id': advance_account.id,
                        'name': rec.notes or rec.expense_type,
                        'debit': 0.0,
                        'credit': rec.amount,
                        'partner_id': getattr(rec.driver_id, 'address_home_id', rec.driver_id.user_id.partner_id).id if (hasattr(rec.driver_id, 'address_home_id') and rec.driver_id.address_home_id) or rec.driver_id.user_id.partner_id else False,
                    }),
                ],
            })

            move.action_post()

            rec.move_id = move
            rec.confirmed_by = self.env.user
            rec.write({'state': 'confirmed'})
            rec.advance_id._compute_expense_totals()

            advance = rec.advance_id
            if advance.state == 'draft':
                advance.write({'state': 'in_settlement'})

    def action_cancel(self):
        for rec in self:
            if rec.move_id:
                rec.move_id.button_cancel()
                rec.move_id.unlink()
        self.write({'state': 'canceled'})
        for rec in self:
            rec.advance_id._compute_expense_totals()

    def action_draft(self):
        self.write({'state': 'draft'})

    def unlink(self):
        advances = self.mapped('advance_id')
        
        for rec in self:
            if rec.move_id:
                if rec.move_id.state == 'posted':
                    rec.move_id.button_draft()
                rec.move_id.unlink()
    
        res = super(TripExpense, self).unlink()
        for advance in advances:
            advance._compute_expense_totals()
            
            if not advance.expense_ids and advance.state == 'in_settlement':
                advance.write({'state': 'draft'})
                
        return res