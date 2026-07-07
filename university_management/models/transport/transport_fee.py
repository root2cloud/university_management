# -*- coding: utf-8 -*-

from odoo import models, fields, api


class TransportFee(models.Model):
    _name = 'transport.fee'
    _description = 'Transport Fee Payment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'payment_date desc'

    name = fields.Char(string='Receipt Number', required=True, readonly=True,
                       copy=False, default='/')

    # Student
    student_id = fields.Many2one('student.student', string='Student',
                                 required=True, tracking=True, index=True)
    allocation_id = fields.Many2one('transport.allocation', string='Transport Allocation')

    # Route
    route_id = fields.Many2one(related='allocation_id.route_id', string='Route', store=True)

    # Fee Details
    amount = fields.Monetary(string='Amount', required=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Payment Date
    payment_date = fields.Date(string='Payment Date', default=fields.Date.today(),
                               required=True)

    # For Month
    month = fields.Selection([
        ('1', 'January'), ('2', 'February'), ('3', 'March'),
        ('4', 'April'), ('5', 'May'), ('6', 'June'),
        ('7', 'July'), ('8', 'August'), ('9', 'September'),
        ('10', 'October'), ('11', 'November'), ('12', 'December'),
    ], string='For Month', required=True)
    year = fields.Integer(string='Year', default=lambda self: fields.Date.today().year)

    # Payment Method
    payment_method = fields.Selection([
        ('cash', 'Cash'),
        ('online', 'Online'),
        ('cheque', 'Cheque'),
    ], string='Payment Method', default='cash')

    # Status
    state = fields.Selection([
        ('paid', 'Paid'),
        ('pending', 'Pending'),
    ], string='Status', default='paid', tracking=True)

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Receipt Number must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('transport.fee') or '/'
        return super(TransportFee, self).create(vals)
