# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ProjectPresentation(models.Model):
    _name = 'project.presentation'
    _description = 'Project Viva/Presentation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'presentation_date desc'

    name = fields.Char(string='Presentation Number', compute='_compute_name', store=True)

    # Project
    project_id = fields.Many2one('student.project', string='Project',
                                 required=True, tracking=True, index=True)

    # Presentation Type
    presentation_type = fields.Selection([
        ('progress', 'Progress Presentation'),
        ('viva', 'Viva Voce'),
        ('final', 'Final Presentation'),
    ], string='Presentation Type', required=True, tracking=True)

    # Schedule
    presentation_date = fields.Date(string='Presentation Date', required=True, tracking=True)
    presentation_time = fields.Float(string='Time', help='Time in 24-hour format')
    duration = fields.Float(string='Duration (Minutes)', default=20.0)

    # Venue
    venue = fields.Char(string='Venue')

    # Panel Members
    panel_member_ids = fields.Many2many('faculty.faculty', string='Panel Members')

    # Attendance
    students_present = fields.Many2many('student.student', string='Students Present')

    # Evaluation
    evaluation_id = fields.Many2one('project.evaluation', string='Evaluation')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    # Remarks
    remarks = fields.Text(string='Remarks')

    @api.depends('project_id', 'presentation_date')
    def _compute_name(self):
        for record in self:
            record.name = f"{record.project_id.project_code} - {record.presentation_date}"

    # Workflow actions
    def action_schedule_presentation(self):
        """Schedule the presentation (move from draft to scheduled)."""
        self.write({'state': 'scheduled'})

    def action_mark_completed(self):
        """Mark the presentation as completed."""
        self.write({'state': 'completed'})

    def action_cancel(self):
        """Cancel the presentation."""
        self.write({'state': 'cancelled'})

    def action_reschedule(self):
        """Prepare the record for rescheduling (keep 'scheduled' state)."""
        # If you need extra logic, add it here; keeping state as 'scheduled'
        self.write({'state': 'scheduled'})

    def action_reset_to_draft(self):
        """Reset the presentation to draft state."""
        self.write({'state': 'draft'})

    def action_view_project(self):
        """Open the related student project."""
        self.ensure_one()
        if not self.project_id:
            return False
        return {
            'name': _('Project'),
            'type': 'ir.actions.act_window',
            'res_model': 'student.project',
            'view_mode': 'form',
            'res_id': self.project_id.id,
            'target': 'current',
        }

    def action_view_evaluation(self):
        """Open the linked project evaluation, if any."""
        self.ensure_one()
        if not self.evaluation_id:
            return False
        return {
            'name': _('Evaluation'),
            'type': 'ir.actions.act_window',
            'res_model': 'project.evaluation',
            'view_mode': 'form',
            'res_id': self.evaluation_id.id,
            'target': 'current',
        }
