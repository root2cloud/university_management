# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class LibraryFine(models.Model):
    _name = 'library.fine'
    _description = 'Library Fine Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    name = fields.Char(string='Fine Number', required=True, readonly=True,
                       copy=False, default='/')

    # Member
    member_id = fields.Many2one('library.member', string='Member',
                                required=True, tracking=True, index=True)
    member_name = fields.Char(related='member_id.member_name', string='Member Name')

    # Issue (if fine is for overdue)
    issue_id = fields.Many2one('library.issue', string='Book Issue')
    book_id = fields.Many2one(related='issue_id.book_id', string='Book')

    # Fine Details
    fine_type = fields.Selection([
        ('overdue', 'Overdue Fine'),
        ('damage', 'Damage Fine'),
        ('lost', 'Lost Book Fine'),
        ('other', 'Other'),
    ], string='Fine Type', required=True, tracking=True)

    amount = fields.Monetary(string='Fine Amount', required=True,
                             currency_field='currency_id', tracking=True)

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Date
    date = fields.Date(string='Fine Date', default=fields.Date.today(), required=True)

    # Payment
    payment_date = fields.Date(string='Payment Date')
    payment_reference = fields.Char(string='Payment Reference')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('waived', 'Waived'),
    ], string='Status', default='pending', tracking=True)

    # Reason
    reason = fields.Text(string='Reason')

    # Waiver
    waived_by = fields.Many2one('res.users', string='Waived By', readonly=True)
    waiver_reason = fields.Text(string='Waiver Reason')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Fine Number must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('library.fine') or '/'
        return super(LibraryFine, self).create(vals)

    def action_submit(self):
        """Submit fine (move from draft to pending)"""
        self.write({'state': 'pending'})

    def action_mark_paid(self):
        self.write({
            'state': 'paid',
            'payment_date': fields.Date.today()
        })

    def action_waive(self):
        self.write({
            'state': 'waived',
            'waived_by': self.env.user.id
        })

    def action_reset_to_draft(self):
        """Reset fine to draft state"""
        self.write({
            'state': 'draft',
            'payment_date': False,
            'payment_reference': False,
            'waived_by': False,
            'waiver_reason': False
        })
