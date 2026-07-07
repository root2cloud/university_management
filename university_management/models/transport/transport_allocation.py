# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TransportAllocation(models.Model):
    _name = 'transport.allocation'
    _description = 'Student Transport Allocation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'allocation_date desc'

    name = fields.Char(string='Allocation Number', required=True, readonly=True,
                       copy=False, default='/')

    # Student
    student_id = fields.Many2one('student.student', string='Student',
                                 required=True, tracking=True, index=True)
    registration_number = fields.Char(related='student_id.registration_number',
                                      string='Registration Number')

    # Route & Stop
    route_id = fields.Many2one('transport.route', string='Route',
                               required=True, tracking=True, index=True)
    stop_id = fields.Many2one('transport.stop', string='Boarding Point',
                              required=True, tracking=True,
                              domain="[('route_id', '=', route_id)]")

    # Vehicle
    vehicle_id = fields.Many2one('transport.vehicle', string='Vehicle',
                                 domain="[('route_ids', 'in', [route_id])]")

    # Allocation Period
    allocation_date = fields.Date(string='Allocation Date', default=fields.Date.today(),
                                  required=True, tracking=True)
    from_date = fields.Date(string='From Date', required=True)
    to_date = fields.Date(string='To Date')

    # Academic Year
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year')

    # Fee
    monthly_fee = fields.Monetary(string='Monthly Fee', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    # Remarks
    remarks = fields.Text(string='Remarks')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Allocation Number must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('transport.allocation') or '/'
        record = super(TransportAllocation, self).create(vals)
        if record.student_id:
            record.student_id.sudo().transport_allocation_id = record.id
            record.student_id.sudo().uses_transport = True
        return record

    def write(self, vals):
        res = super(TransportAllocation, self).write(vals)
        for record in self:
            if record.student_id:
                record.student_id.sudo().transport_allocation_id = record.id
                record.student_id.sudo().uses_transport = True
        return res

    def unlink(self):
        students = self.filtered(lambda r: r.student_id).mapped('student_id')
        res = super(TransportAllocation, self).unlink()
        for student in students:
            if not self.env['transport.allocation'].search([('student_id', '=', student.id)], limit=1):
                student.sudo().write({'transport_allocation_id': False, 'uses_transport': False})
        return res

    @api.onchange('route_id')
    def _onchange_route_fee(self):
        if self.route_id:
            self.monthly_fee = self.route_id.monthly_fee

    def action_activate(self):
        self.write({'state': 'active'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})