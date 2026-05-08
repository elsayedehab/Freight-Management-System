    # -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
class FreightTripSendMail(models.TransientModel):
    _name = 'freight.trip.send.mail'
    _description = 'Send Waybill by Email'

    trip_id = fields.Many2one('freight.trip', string='Trip', required=True)

    # ── customer data ──────────────────────────────────────────────
    email_from = fields.Char(
        string='From',
        default=lambda self: self.env.company.email or ''
    )
    email_to = fields.Char(string='To (Customer Email)')
    subject   = fields.Char(string='Subject')
    body      = fields.Html(string='Body')

    @api.onchange('trip_id')
    def _onchange_trip_id(self):
        if self.trip_id:
            template = self.env.ref(
                'Freight_Management_System.email_template_freight_waybill',
                raise_if_not_found=False
            )
            if template:
                self.email_to = self.trip_id.partner_id.email
                self.email_from = self.env.company.email or self.env.user.email
                self.subject = template._render_field('subject', self.trip_id.ids)[self.trip_id.id]
                self.body = template._render_field('body_html', self.trip_id.ids)[self.trip_id.id]

    def action_send(self):
        self.ensure_one()
        if not self.email_to:
            raise UserError(_("Customer has no email address!"))

        # ── PDF Attachment ──
        report_xml_id = 'Freight_Management_System.action_report_waybill'
        pdf_content, _mime = self.env['ir.actions.report']._render_qweb_pdf(
            report_xml_id, self.trip_id.ids
        )

        attachment = self.env['ir.attachment'].create({
            'name': f'Waybill-{self.trip_id.name}.pdf',
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': 'freight.trip',
            'res_id': self.trip_id.id,
            'mimetype': 'application/pdf',
        })

        # ── send mail ──
        mail = self.env['mail.mail'].create({
            'subject':         self.subject,
            'body_html':       self.body,
            'email_from':      self.email_from,
            'email_to':        self.email_to,
            'attachment_ids':  [(6, 0, [attachment.id])],
            'res_id':          self.trip_id.id,
            'model':           'freight.trip',
        })

        mail.send()

        # ── Log chatter ──
        self.trip_id.message_post(
            body=_("Waybill sent by email to %s") % self.email_to,
            subject=self.subject,
        )

        return {'type': 'ir.actions.act_window_close'}