# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class IICEventReport(models.Model):
    _name = 'iic.event.report'
    _description = 'IIC Event Report'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Report Title', required=True, tracking=True)
    event_id = fields.Many2one('iic.event', string='Event', required=True, ondelete='cascade', tracking=True)

    # Auto-populated from event
    event_title = fields.Char(related='event_id.name', string='Event Title', store=True)
    event_date = fields.Datetime(related='event_id.event_date', string='Event Date', store=True)
    venue = fields.Char(related='event_id.venue', string='Venue', store=True)
    activity_type = fields.Selection(related='event_id.activity_type', string='Activity Type', store=True)
    quarter = fields.Selection(related='event_id.quarter', string='Quarter', store=True)
    academic_year_id = fields.Many2one('university.academic.year', related='event_id.academic_year_id', string='Academic Year', store=True)
    department_id = fields.Many2one('university.department', related='event_id.department_id', string='Department', store=True)
    faculty_incharge_id = fields.Many2one('hr.employee', related='event_id.faculty_incharge_id', string='Faculty In-Charge', store=True)
    speaker_id = fields.Many2one('iic.speaker', related='event_id.speaker_id', string='Speaker', store=True)
    total_attendees = fields.Integer(related='event_id.total_attendees', string='Total Attendees', store=True)
    present_count = fields.Integer(related='event_id.present_count', string='Present', store=True)
    attendance_count = fields.Integer(related='event_id.attendance_count', string='Attendance Count', store=True)
    actual_participants = fields.Integer(related='event_id.actual_participants', string='Actual Participants', store=True)
    participation_percentage = fields.Float(related='event_id.participation_percentage', string='Participation %', store=True)

    # Report content
    event_description = fields.Html(related='event_id.description', string='Event Description', store=True)
    objectives = fields.Text(related='event_id.objectives', string='Objectives', store=True)
    outcomes = fields.Html(string='Outcomes / Impact')
    report_summary = fields.Html(string='Report Summary')
    photo_ids = fields.Many2many('iic.media', 'report_photo_rel', 'report_id', 'media_id', string='Photos',
                                  domain="[('event_id', '=', event_id)]")
    event_summary = fields.Html(string='Event Summary')
    key_outcomes = fields.Html(string='Key Outcomes / Highlights')
    student_feedback = fields.Text(string='Student Feedback Summary')
    faculty_remarks = fields.Text(string='Faculty Remarks')

    # Photos linked from media
    media_ids = fields.Many2many('iic.media', string='Attached Media',
                                  domain="[('event_id', '=', event_id)]")

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted for Approval'),
        ('approved', 'Approved'),
        ('revision', 'Revision Required'),
        ('rejected', 'Rejected'),
    ], string='Report Status', default='draft', tracking=True)

    submitted_by = fields.Many2one('res.users', string='Submitted By')
    submitted_date = fields.Datetime(string='Submitted Date')
    approved_by = fields.Many2one('res.users', string='Approved By')
    approved_date = fields.Datetime(string='Approved Date')
    revision_remarks = fields.Text(string='Revision Remarks')

    msme_submitted = fields.Boolean(string='Submitted to MSME', tracking=True)
    msme_submission_date = fields.Date(string='MSME Submission Date')

    def action_submit(self):
        self.state = 'submitted'
        self.submitted_by = self.env.user.id
        self.submitted_date = fields.Datetime.now()

    def action_approve(self):
        self.state = 'approved'
        self.approved_by = self.env.user.id
        self.approved_date = fields.Datetime.now()
        self.event_id.report_submitted = True

    def action_request_revision(self):
        self.state = 'revision'

    def action_reject(self):
        self.state = 'rejected'

    def action_print_pdf(self):
        return self.env.ref('university_management.action_report_iic_event_report').report_action(self)

    def action_reset_draft(self):
        self.state = 'draft'

    def action_print_report(self):
        return self.env.ref('university_management.action_report_iic_event_report').report_action(self)