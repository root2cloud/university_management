# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HostelVisitor(models.Model):
    _name = 'hostel.visitor'
    _description = 'Hostel Visitor Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'visit_date desc, visit_time desc'

    name = fields.Char(string='Visitor Name', required=True)

    # Visitor Details
    visitor_type = fields.Selection([
        ('parent', 'Parent/Guardian'),
        ('relative', 'Relative'),
        ('friend', 'Friend'),
        ('other', 'Other'),
    ], string='Visitor Type', required=True)

    phone = fields.Char(string='Phone Number', required=True)

    id_proof_type = fields.Selection([
        ('aadhar', 'Aadhar Card'),
        ('pan', 'PAN Card'),
        ('driving_license', 'Driving License'),
        ('voter_id', 'Voter ID'),
    ], string='ID Proof Type')

    id_proof_number = fields.Char(string='ID Proof Number')

    # Student Being Visited
    student_id = fields.Many2one('student.student', string='Visiting Student',
                                 required=True, index=True)

    # Fixed: Get hostel_id and room_id through hostel_allocation_id
    hostel_allocation_id = fields.Many2one(related='student_id.hostel_allocation_id',
                                           string='Hostel Allocation', store=True)
    hostel_id = fields.Many2one(related='hostel_allocation_id.hostel_id',
                                string='Hostel', store=True)
    room_id = fields.Many2one(related='hostel_allocation_id.room_id',
                              string='Room', store=True)

    # Visit Details
    visit_date = fields.Date(string='Visit Date', default=fields.Date.today(), required=True)
    visit_time = fields.Datetime(string='Check-in Time', default=fields.Datetime.now)
    exit_time = fields.Datetime(string='Check-out Time')
    purpose = fields.Text(string='Purpose of Visit')

    # Approval
    approved_by = fields.Many2one('res.users', string='Approved By')

    # Remarks
    remarks = fields.Text(string='Remarks')
