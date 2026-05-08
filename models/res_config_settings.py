# -*- coding: utf-8 -*-
from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    driver_advance_account_id = fields.Many2one(
        'account.account',
        string='Driver Advance Account',
        config_parameter='freight_management_system.driver_advance_account_id',
    )
    driver_advance_journal_id = fields.Many2one(
        'account.journal',
        string='Driver Advance Journal',
        config_parameter='freight_management_system.driver_advance_journal_id',
    )