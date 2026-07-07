# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HostelComplaint(models.Model):
    _name = 'hostel.complaint'
    _description = 'Hostel Complaint Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'complaint_date desc'

    name = fields.Char(string='Complaint Number', required=True, readonly=True,
                       copy=False, default='/')

    # Student
    student_id = fields.Many2one('student.student', string='Reported By',
                                 required=True, tracking=True)

    # Hostel & Room
    hostel_id = fields.Many2one('hostel.hostel', string='Hostel', required=True)
    room_id = fields.Many2one('hostel.room', string='Room')

    # Complaint Details
    complaint_type = fields.Selection([
        ('maintenance', 'Maintenance Issue'),
        ('cleanliness', 'Cleanliness Issue'),
        ('electricity', 'Electrical Problem'),
        ('plumbing', 'Plumbing Issue'),
        ('wifi', 'WiFi Issue'),
        ('food', 'Food Quality'),
        ('security', 'Security Concern'),
        ('noise', 'Noise Complaint'),
        ('other', 'Other'),
    ], string='Complaint Type', required=True, tracking=True)

    complaint_date = fields.Date(string='Complaint Date', default=fields.Date.today(),
                                 required=True)

    subject = fields.Char(string='Subject', required=True)
    description = fields.Html(string='Description', required=True)

    # Priority
    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ], string='Priority', default='medium', tracking=True)

    # Assignment
    assigned_to = fields.Many2one('res.users', string='Assigned To', tracking=True)

    # Resolution
    resolution_date = fields.Date(string='Resolution Date')
    resolution_details = fields.Html(string='Resolution Details')

    # Status
    state = fields.Selection([
        ('new', 'New'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ], string='Status', default='new', tracking=True)

    # Attachments
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Complaint Number must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('hostel.complaint') or '/'
        return super(HostelComplaint, self).create(vals)

    def action_assign(self):
        self.write({'state': 'in_progress'})

    def action_resolve(self):
        self.write({
            'state': 'resolved',
            'resolution_date': fields.Date.today()
        })

    def action_close(self):
        self.write({'state': 'closed'})

    def action_reset_to_new(self):
        """Reset complaint to new state"""
        for record in self:
            record.write({
                'state': 'new',
                'assigned_to': False,
                'resolution_date': False,
                'resolution_details': False
            })