# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HostelAllocation(models.Model):
    _name = 'hostel.allocation'
    _description = 'Student Hostel Room Allocation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'allocation_date desc'

    name = fields.Char(string='Allocation Number', required=True, readonly=True,
                       copy=False, default='/')

    # Student
    student_id = fields.Many2one('student.student', string='Student',
                                 required=True, tracking=True, index=True)
    registration_number = fields.Char(related='student_id.registration_number',
                                      string='Registration Number')
    program_id = fields.Many2one(related='student_id.program_id', string='Program', store=True)

    # Hostel & Room
    hostel_id = fields.Many2one('hostel.hostel', string='Hostel',
                                required=True, tracking=True, index=True)
    room_id = fields.Many2one('hostel.room', string='Room',
                              required=True, tracking=True, index=True,
                              domain="[('hostel_id', '=', hostel_id), ('available_beds', '>', 0)]")
    bed_number = fields.Char(string='Bed Number')

    # Allocation Period
    allocation_date = fields.Date(string='Allocation Date', default=fields.Date.today(),
                                  required=True, tracking=True)
    from_date = fields.Date(string='From Date', required=True, default=fields.Date.today())
    to_date = fields.Date(string='To Date', tracking=True)

    # Academic Year
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year')

    # Fees
    monthly_rent = fields.Monetary(string='Monthly Rent', currency_field='currency_id')
    security_deposit = fields.Monetary(string='Security Deposit', currency_field='currency_id')
    total_paid = fields.Monetary(string='Total Paid', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Inventory/Assets Given (using stock module integration)
    asset_ids = fields.Many2many('product.product', string='Assets Issued',
                                 help='Mattress, Pillow, Blanket, etc.')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('allocated', 'Allocated'),
        ('vacated', 'Vacated'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    # Vacate Details
    vacate_date = fields.Date(string='Vacate Date')
    vacate_reason = fields.Text(string='Vacate Reason')

    # Remarks
    remarks = fields.Text(string='Remarks')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Allocation Number must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('hostel.allocation') or '/'
        record = super(HostelAllocation, self).create(vals)
        if record.student_id:
            record.student_id.sudo().hostel_allocation_id = record.id
            record.student_id.sudo().is_hosteller = True
        return record

    def write(self, vals):
        res = super(HostelAllocation, self).write(vals)
        for record in self:
            if record.student_id:
                record.student_id.sudo().hostel_allocation_id = record.id
                record.student_id.sudo().is_hosteller = True
        return res

    def unlink(self):
        students = self.filtered(lambda r: r.student_id).mapped('student_id')
        res = super(HostelAllocation, self).unlink()
        for student in students:
            if not self.env['hostel.allocation'].search([('student_id', '=', student.id)], limit=1):
                student.sudo().write({'hostel_allocation_id': False, 'is_hosteller': False})
        return res

    @api.onchange('room_id')
    def _onchange_room_rent(self):
        if self.room_id:
            self.monthly_rent = self.room_id.monthly_rent

    def action_allocate(self):
        """Allocate room to student"""
        self.write({'state': 'allocated'})

    def action_vacate(self):
        """Vacate student from room"""
        self.write({
            'state': 'vacated',
            'vacate_date': fields.Date.today()
        })

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})