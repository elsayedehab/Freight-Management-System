from odoo import models, fields, api, _

class AccountMove(models.Model):
    _inherit = 'account.move'

    freight_trip_id = fields.Many2one(
        'freight.trip',
        string='Freight Trip',
        readonly=True,
        ondelete='set null'
    )