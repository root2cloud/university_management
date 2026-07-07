# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class PlacementTraining(models.Model):
    _name = 'placement.training'
    _description = 'Pre-Placement Training Programs'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc'

    name = fields.Char(string='Training Program Name', required=True, tracking=True)

    # Training Type
    training_type = fields.Selection([
        ('aptitude', 'Aptitude Training'),
        ('technical', 'Technical Skills'),
        ('soft_skills', 'Soft Skills'),
        ('communication', 'Communication Skills'),
        ('group_discussion', 'Group Discussion'),
        ('mock_interview', 'Mock Interviews'),
        ('resume_building', 'Resume Building'),
    ], string='Training Type', required=True)

    # Duration
    start_date = fields.Date(string='Start Date', required=True, tracking=True)
    end_date = fields.Date(string='End Date', required=True, tracking=True)
    duration_days = fields.Integer(string='Duration (Days)', compute='_compute_duration')

    # Trainer
    trainer_id = fields.Many2one('faculty.faculty', string='Trainer/Faculty')
    external_trainer = fields.Char(string='External Trainer Name')

    # Students
    student_ids = fields.Many2many('student.student', string='Students Enrolled')
    total_students = fields.Integer(string='Total Students', compute='_compute_students')

    # Venue
    venue = fields.Char(string='Venue')

    # Description
    description = fields.Html(string='Description')
    syllabus = fields.Html(string='Syllabus/Topics Covered')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='scheduled', tracking=True)

    @api.depends('start_date', 'end_date')
    def _compute_duration(self):
        for record in self:
            if record.start_date and record.end_date:
                record.duration_days = (record.end_date - record.start_date).days + 1
            else:
                record.duration_days = 0

    @api.depends('student_ids')
    def _compute_students(self):
        for record in self:
            record.total_students = len(record.student_ids)

    def action_schedule_training(self):
        self.write({'state': 'scheduled'})

    def action_start(self):
        """Start the training."""
        self.write({'state': 'ongoing'})

    def action_complete(self):
        """Mark training as completed."""
        self.write({'state': 'completed'})

    def action_cancel(self):
        """Cancel the training."""
        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def action_placement_training(self):
        """Open students enrolled in this training."""
        self.ensure_one()
        return {
            'name': 'Students',
            'type': 'ir.actions.act_window',
            'res_model': 'student.student',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.student_ids.ids)],
            'context': {},
        }



