# -*- coding: utf-8 -*-
{
    "name": "Freight Management System",
    "version": "1.0",
    "category": "Tools",
    "summary": "Freight Management System",
    "description": "This helped to manage freight trips and expenses and profitability analysis",
    "author": "Elsayed Ehab Elsayed",
    "maintainer": "",
    "website": "https://www.yourcompany.com",
    "depends": ["base", "fleet", "mail", "hr", "accountant", "account", "web","sale","sale_management"],
    "data": [
        'data/ir_sequence_data.xml',
        'security/ir.model.access.csv',
        'data/mail_template_data.xml',
        "reports/report_waybill.xml",
        'views/freight_trip_view.xml',
        "wizard/send_mail_view.xml",
        'views/driver_advance_view.xml',
    ],
    "assets": {
        
        
    },
    "license": "LGPL-3",
    "installable": True,
    "auto_install": False,
    "application": True,
}