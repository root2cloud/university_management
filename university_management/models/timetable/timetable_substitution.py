# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class TimetableSubstitution(models.Model):
    _name = 'timetable.substitution'
    _description = 'Substitute Teacher Assignment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    name = fields.Char(string='Substitution Number', required=True, readonly=True,
                       copy=False, default='/')

    # Original Class
    timetable_id = fields.Many2one('class.timetable', string='Original Class',
                                   required=True, tracking=True)

    subject_id = fields.Many2one(related='timetable_id.subject_id', string='Subject', store=True)
    original_faculty_id = fields.Many2one(related='timetable_id.faculty_id',
                                          string='Original Faculty', store=True)

    # Substitution Details
    date = fields.Date(string='Substitution Date', required=True, default=fields.Date.today(),
                       tracking=True)

    # Substitute Faculty
    substitute_faculty_id = fields.Many2one('faculty.faculty', string='Substitute Faculty',
                                            required=True, tracking=True)

    # Reason
    reason = fields.Selection([
        ('leave', 'Faculty on Leave'),
        ('meeting', 'Official Meeting'),
        ('conference', 'Conference/Seminar'),
        ('emergency', 'Emergency'),
        ('other', 'Other'),
    ], string='Reason', required=True)

    reason_details = fields.Text(string='Reason Details')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    # Remarks
    remarks = fields.Text(string='Remarks')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Substitution Number must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('timetable.substitution') or '/'
        return super(TimetableSubstitution, self).create(vals)

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_complete(self):
        self.write({'state': 'completed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})
