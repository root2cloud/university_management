# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class StudentDiscipline(models.Model):
    _name = 'student.discipline'
    _description = 'Student Discipline Records'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'incident_date desc'

    name = fields.Char(string='Incident Number', required=True, readonly=True,
                       copy=False, default='/')

    # Student
    student_id = fields.Many2one('student.student', string='Student',
                                 required=True, tracking=True, index=True)
    registration_number = fields.Char(related='student_id.registration_number',
                                      string='Registration Number')
    program_id = fields.Many2one(related='student_id.program_id', string='Program', store=True)
    department_id = fields.Many2one(related='student_id.department_id',
                                    string='Department', store=True)

    # Incident Details
    incident_date = fields.Date(string='Incident Date', required=True,
                                default=fields.Date.today(), tracking=True)
    incident_time = fields.Float(string='Incident Time')
    incident_location = fields.Char(string='Location')

    # Incident Type
    incident_type = fields.Selection([
        ('attendance', 'Poor Attendance'),
        ('misbehavior', 'Misbehavior'),
        ('cheating', 'Cheating/Malpractice'),
        ('late_coming', 'Late Coming'),
        ('uniform', 'Uniform Violation'),
        ('violence', 'Violence/Fighting'),
        ('substance', 'Substance Abuse'),
        ('property_damage', 'Property Damage'),
        ('harassment', 'Harassment'),
        ('ragging', 'Ragging'),
        ('other', 'Other'),
    ], string='Incident Type', required=True, tracking=True)

    # Severity
    severity = fields.Selection([
        ('minor', 'Minor'),
        ('moderate', 'Moderate'),
        ('major', 'Major'),
        ('critical', 'Critical'),
    ], string='Severity', required=True, tracking=True)

    # Description
    description = fields.Html(string='Incident Description', required=True)

    # Reported By
    reported_by = fields.Many2one('res.users', string='Reported By',
                                  default=lambda self: self.env.user,
                                  required=True, tracking=True)
    faculty_id = fields.Many2one('faculty.faculty', string='Faculty Involved')

    # Witnesses
    witness_ids = fields.Many2many('student.student', 'discipline_witness_rel',
                                   'discipline_id', 'witness_id',
                                   string='Witnesses')

    # Action Taken
    action_type = fields.Selection([
        ('warning', 'Verbal Warning'),
        ('written_warning', 'Written Warning'),
        ('fine', 'Fine/Penalty'),
        ('suspension', 'Suspension'),
        ('expulsion', 'Expulsion'),
        ('counseling', 'Counseling'),
        ('community_service', 'Community Service'),
        ('other', 'Other Action'),
    ], string='Action Taken', tracking=True)

    action_description = fields.Text(string='Action Description')

    # Fine/Penalty
    fine_amount = fields.Monetary(string='Fine Amount', currency_field='currency_id')
    fine_paid = fields.Boolean(string='Fine Paid')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Suspension
    suspension_start = fields.Date(string='Suspension Start Date')
    suspension_end = fields.Date(string='Suspension End Date')
    suspension_days = fields.Integer(string='Suspension Days', compute='_compute_suspension_days')

    # Parent Notification
    parent_notified = fields.Boolean(string='Parent Notified', tracking=True)
    parent_meeting_date = fields.Date(string='Parent Meeting Date')
    parent_response = fields.Text(string='Parent Response')

    # Follow-up
    follow_up_required = fields.Boolean(string='Follow-up Required')
    follow_up_date = fields.Date(string='Follow-up Date')
    follow_up_notes = fields.Text(string='Follow-up Notes')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('reported', 'Reported'),
        ('under_review', 'Under Review'),
        ('action_taken', 'Action Taken'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ], string='Status', default='draft', tracking=True)

    # Approval
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    approval_date = fields.Date(string='Approval Date', readonly=True)

    # Attachments
    attachment_ids = fields.Many2many('ir.attachment', string='Evidence/Attachments')

    # Notes
    notes = fields.Text(string='Additional Notes')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Incident Number must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('student.discipline') or '/'
        return super(StudentDiscipline, self).create(vals)

    @api.depends('suspension_start', 'suspension_end')
    def _compute_suspension_days(self):
        for record in self:
            if record.suspension_start and record.suspension_end:
                record.suspension_days = (record.suspension_end - record.suspension_start).days + 1
            else:
                record.suspension_days = 0

    def action_report(self):
        self.write({'state': 'reported'})

    def action_review(self):
        self.write({'state': 'under_review'})

    def action_take_action(self):
        self.write({'state': 'action_taken'})

    def action_resolve(self):
        self.write({'state': 'resolved'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def action_notify_parent(self):
        """Send notification to parent"""
        self.write({'parent_notified': True})
        template = self.env.ref('university_management.email_template_discipline_notification',
                                raise_if_not_found=False)
        if template:
            for parent in self.student_id.parent_ids:
                if parent.email:
                    template.with_context(parent=parent).send_mail(self.id, force_send=True)
