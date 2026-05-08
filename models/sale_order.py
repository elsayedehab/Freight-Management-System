from odoo import models, fields, api, _


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    freight_trip_id = fields.Many2one(
        'freight.trip',
        string='Freight Trip',
        readonly=True,
        copy=False,
        ondelete='set null'
    )


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    freight_trip_id = fields.Many2one(
        'freight.trip',
        string='Freight Trip',
        related='order_id.freight_trip_id',
        store=True,
        readonly=True
    )