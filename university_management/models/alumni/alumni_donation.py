# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AlumniDonation(models.Model):
    _name = 'alumni.donation'
    _description = 'Alumni Donations/Contributions'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'donation_date desc'

    name = fields.Char(string='Donation Receipt Number', required=True, readonly=True,
                       copy=False, default='/')

    # Alumni
    alumni_id = fields.Many2one('alumni.alumni', string='Alumni',
                                required=True, tracking=True, index=True)
    alumni_name = fields.Char(related='alumni_id.name', string='Alumni Name')

    # Donation Details
    donation_date = fields.Date(string='Donation Date', default=fields.Date.today(),
                                required=True, tracking=True)

    amount = fields.Monetary(string='Donation Amount', required=True,
                             currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Purpose
    donation_purpose = fields.Selection([
        ('infrastructure', 'Infrastructure Development'),
        ('scholarship', 'Student Scholarship'),
        ('research', 'Research & Development'),
        ('library', 'Library'),
        ('sports', 'Sports Facilities'),
        ('general', 'General Fund'),
        ('other', 'Other'),
    ], string='Donation Purpose', required=True, tracking=True)

    purpose_description = fields.Text(string='Purpose Description')

    # Payment Method
    payment_method = fields.Selection([
        ('online', 'Online Transfer'),
        ('cheque', 'Cheque'),
        ('dd', 'Demand Draft'),
        ('cash', 'Cash'),
    ], string='Payment Method', required=True)

    payment_reference = fields.Char(string='Payment Reference/Transaction ID')

    # Tax Exemption
    tax_exemption_certificate = fields.Binary(string='80G Certificate', attachment=True)

    # Acknowledgement
    acknowledgement_sent = fields.Boolean(string='Acknowledgement Sent')
    acknowledgement_date = fields.Date(string='Acknowledgement Date')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('received', 'Received'),
        ('acknowledged', 'Acknowledged'),
    ], string='Status', default='draft', tracking=True)

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Receipt Number must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('alumni.donation') or '/'
        return super(AlumniDonation, self).create(vals)

    def action_acknowledge(self):
        self.write({
            'state': 'acknowledged',
            'acknowledgement_sent': True,
            'acknowledgement_date': fields.Date.today()
        })

    def action_receive(self):
        """Mark donation as received (move from draft to received)"""
        self.write({'state': 'received'})

    def action_reset_to_draft(self):
        """Reset donation to draft state"""
        self.write({
            'state': 'draft',
            'acknowledgement_sent': False,
            'acknowledgement_date': False
        })
