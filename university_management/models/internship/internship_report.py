# -*- coding: utf-8 -*-

from odoo import models, fields, api


class InternshipReport(models.Model):
    _name = 'internship.report'
    _description = 'Internship Progress Reports'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'report_date desc'

    name = fields.Char(string='Report Number', compute='_compute_name', store=True)

    # Internship
    internship_id = fields.Many2one('internship.internship', string='Internship',
                                    required=True, index=True, ondelete='cascade')
    student_id = fields.Many2one(related='internship_id.student_id', string='Student', store=True)

    # Report Type
    report_type = fields.Selection([
        ('weekly', 'Weekly Report'),
        ('monthly', 'Monthly Report'),
        ('final', 'Final Report'),
    ], string='Report Type', required=True)

    # Report Date
    report_date = fields.Date(string='Report Date', default=fields.Date.today(), required=True)
    report_period = fields.Char(string='Reporting Period', help='e.g., Week 1, Month 1')

    # Work Summary
    work_summary = fields.Html(string='Work Summary', required=True)
    tasks_completed = fields.Html(string='Tasks Completed')
    challenges_faced = fields.Html(string='Challenges Faced')
    learnings = fields.Html(string='Key Learnings')

    # Documents
    report_document = fields.Binary(string='Report Document', attachment=True)
    report_filename = fields.Char(string='Filename')

    # Mentor Feedback
    faculty_feedback = fields.Text(string='Faculty Mentor Feedback')
    company_feedback = fields.Text(string='Company Supervisor Feedback')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('reviewed', 'Reviewed'),
    ], string='Status', default='draft', tracking=True)

    @api.depends('internship_id', 'report_type', 'report_date')
    def _compute_name(self):
        for record in self:
            record.name = f"{record.internship_id.name} - {record.report_type} - {record.report_date}"

    # Workflow actions
    def action_submit(self):
        """Submit the report for review."""
        self.write({'state': 'submitted'})

    def action_review(self):
        """Mark the report as reviewed."""
        self.write({'state': 'reviewed'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})
