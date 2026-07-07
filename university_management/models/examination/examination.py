# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Examination(models.Model):
    _name = 'examination.examination'
    _description = 'Exam Schedule'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc'

    name = fields.Char(string='Examination Name', required=True, tracking=True)
    code = fields.Char(string='Exam Code', required=True)
    active = fields.Boolean(string='Active', default=True, store=True)

    # Exam Type
    exam_type = fields.Selection([
        ('internal', 'Internal/Mid-term'),
        ('external', 'External/End-term'),
        ('final', 'Final Examination'),
        ('supplementary', 'Supplementary'),
        ('improvement', 'Improvement'),
        ('practical', 'Practical'),
        ('online', 'Online / MCQ'),
    ], string='Examination Type', required=True, default='internal', tracking=True)

    # Academic Details
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year',
                                       required=True, tracking=True, index=True)
    semester_id = fields.Many2one('university.semester', string='Semester',
                                  required=True, tracking=True, index=True)
    program_ids = fields.Many2many('university.program', string='Applicable Programs')
    department_ids = fields.Many2many('university.department', string='Applicable Departments')

    # Exam Schedule
    start_date = fields.Date(string='Start Date', required=True, tracking=True)
    end_date = fields.Date(string='End Date', required=True, tracking=True)

    # Timetable
    timetable_ids = fields.One2many('examination.timetable', 'examination_id',
                                    string='Exam Timetable')

    # Hall Tickets
    hall_ticket_ids = fields.One2many('examination.hall.ticket', 'examination_id',
                                      string='Hall Tickets')
    hall_tickets_generated = fields.Boolean(string='Hall Tickets Generated',
                                            compute='_compute_hall_tickets', store=True)

    # Results
    result_ids = fields.One2many('examination.result', 'examination_id', string='Results')
    results_published = fields.Boolean(string='Results Published',
                                       compute='_compute_results', store=True)

    # Seating Arrangement
    seating_ids = fields.One2many('examination.seating', 'examination_id',
                                  string='Seating Arrangements')

    # Online Exams (MCQ)
    online_exam_ids = fields.One2many('online.exam', 'examination_id', string='Online Exams')
    online_exam_count = fields.Integer(string='Online Exams',
                                       compute='_compute_online_exam_count', store=True)

    # Registration
    registration_start_date = fields.Date(string='Registration Start Date')
    registration_end_date = fields.Date(string='Registration End Date')

    # Fees
    exam_fee = fields.Monetary(string='Examination Fee', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Instructions
    instructions = fields.Html(string='Exam Instructions')

    # Company
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company, index=True)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('registration_open', 'Registration Open'),
        ('registration_closed', 'Registration Closed'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('results_published', 'Results Published'),
    ], string='Status', default='draft', tracking=True)

    # Description
    description = fields.Html(string='Description')

    _sql_constraints = [
        ('code_unique', 'unique(code, academic_year_id)',
         'Examination Code must be unique per academic year!'),
    ]

    @api.depends('hall_ticket_ids')
    def _compute_hall_tickets(self):
        for record in self:
            record.hall_tickets_generated = bool(record.hall_ticket_ids)

    @api.depends('result_ids', 'result_ids.state')
    def _compute_results(self):
        for record in self:
            if record.result_ids:
                record.results_published = all(r.state == 'published'
                                               for r in record.result_ids)
            else:
                record.results_published = False

    @api.depends('online_exam_ids')
    def _compute_online_exam_count(self):
        for record in self:
            record.online_exam_count = len(record.online_exam_ids)

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date >= record.end_date:
                raise ValidationError(_('End date must be after start date!'))

    def action_schedule(self):
        self.write({'state': 'scheduled'})

    def action_open_registration(self):
        self.write({'state': 'registration_open'})

    def action_close_registration(self):
        self.write({'state': 'registration_closed'})

    def action_start_exam(self):
        self.write({'state': 'ongoing'})

    def action_complete_exam(self):
        self.write({'state': 'completed'})

    def action_publish_results(self):
        self.write({'state': 'results_published'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def action_generate_hall_tickets(self):
        """Generate hall tickets for all eligible students"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generate Hall Tickets'),
            'res_model': 'generate.examination.hall.ticket.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_examination_id': self.id}
        }

    def action_generate_seating(self):
        """Generate seating arrangement"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generate Seating Arrangement'),
            'res_model': 'generate.examination.seating.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_examination_id': self.id}
        }

    def action_exam_timetable(self):
        """Open exam timetable filtered to this examination."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Exam Timetable'),
            'res_model': 'examination.timetable',
            'view_mode': 'list,form',
            'domain': [('examination_id', '=', self.id)],
            'context': {'default_examination_id': self.id},
        }

    def action_examination_hall_ticket(self):
        """Open hall tickets filtered to this examination."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Hall Tickets'),
            'res_model': 'examination.hall.ticket',
            'view_mode': 'list,form',
            'domain': [('examination_id', '=', self.id)],
            'context': {'default_examination_id': self.id},
        }

    def action_exam_result(self):
        """Open exam results filtered to this examination."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Exam Results'),
            'res_model': 'examination.result',
            'view_mode': 'list,form',
            'domain': [('examination_id', '=', self.id)],
            'context': {'default_examination_id': self.id},
        }

    def action_exam_seating(self):
        """Open seating arrangements filtered to this examination."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Seating Arrangement'),
            'res_model': 'examination.seating',
            'view_mode': 'list,form',
            'domain': [('examination_id', '=', self.id)],
            'context': {'default_examination_id': self.id},
        }

    def action_view_online_exams(self):
        """Open online exams filtered to this examination."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Online Exams'),
            'res_model': 'online.exam',
            'view_mode': 'list,form',
            'domain': [('examination_id', '=', self.id)],
            'context': {'default_examination_id': self.id},
        }
