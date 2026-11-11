# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ExaminationTimetable(models.Model):
    _name = 'examination.timetable'
    _description = 'Exam Timetable'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'exam_date, start_time'

    name = fields.Char(string='Reference', compute='_compute_name', store=True)

    # Examination
    examination_id = fields.Many2one('examination.examination', string='Examination',
                                     required=True, tracking=True, index=True,
                                     ondelete='cascade')

    # Subject & Course
    course_id = fields.Many2one('university.course', string='Course',
                                required=True, tracking=True)
    subject_id = fields.Many2one(related='course_id.subject_id', string='Subject',
                                 store=True, readonly=True)
    program_id = fields.Many2one(related='course_id.program_id', string='Program',
                                 store=True, readonly=True)
    department_id = fields.Many2one(related='course_id.department_id', string='Department',
                                    store=True, readonly=True)
    semester_id = fields.Many2one(related='course_id.semester_id', string='Semester',
                                  store=True, readonly=True)

    # Exam Schedule
    exam_date = fields.Date(string='Exam Date', required=True, tracking=True, index=True)
    start_time = fields.Float(string='Start Time', required=True,
                              help='Time in 24-hour format (e.g., 9.0 for 9:00 AM)')
    end_time = fields.Float(string='End Time', required=True)
    duration = fields.Float(string='Duration (Hours)', compute='_compute_duration', store=True)

    # Exam Details
    max_marks = fields.Integer(string='Maximum Marks', required=True, default=100)
    passing_marks = fields.Integer(string='Passing Marks', required=True, default=40)

    # Venue
    venue = fields.Char(string='Exam Venue')
    room_numbers = fields.Char(string='Room Numbers')

    # Instructions
    instructions = fields.Html(string='Specific Instructions')

    # Supervisors/Invigilators
    invigilator_ids = fields.Many2many('faculty.faculty', 'exam_invigilator_rel',
                                       'timetable_id', 'faculty_id',
                                       string='Invigilators')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='scheduled', tracking=True)

    # Notes
    notes = fields.Text(string='Notes')

    # Question Paper Preparation Reminder
    paper_reminder_days = fields.Integer(
        string='Reminder Before (Days)', default=10,
        help='Faculty teaching this course are reminded to prepare the question paper '
             'this many days before the exam date.')
    paper_faculty_ids = fields.Many2many(
        'faculty.faculty', string='Question Paper Faculty',
        compute='_compute_paper_faculty_ids',
        help='Faculty who have this course in their Courses Taught list.')
    paper_reminder_sent = fields.Boolean(string='Paper Reminder Sent', copy=False, readonly=True)
    paper_reminder_date = fields.Datetime(string='Paper Reminder Sent On', copy=False, readonly=True)
    question_paper_ready = fields.Boolean(
        string='Question Paper Prepared', compute='_compute_question_paper_ready',
        help='True when a question paper already exists for this subject and examination.')

    _sql_constraints = [
        ('unique_exam', 'unique(examination_id, course_id)',
         'Exam already scheduled for this course!'),
    ]

    def _compute_paper_faculty_ids(self):
        Faculty = self.env['faculty.faculty']
        for record in self:
            if record.course_id:
                record.paper_faculty_ids = Faculty.search([
                    ('courses_taught_ids', 'in', record.course_id.id),
                ])
            else:
                record.paper_faculty_ids = Faculty

    def _compute_question_paper_ready(self):
        Paper = self.env['exam.question.paper']
        for record in self:
            record.question_paper_ready = bool(record.subject_id) and bool(Paper.search_count([
                ('subject_id', '=', record.subject_id.id),
                ('examination_id', '=', record.examination_id.id),
            ]))

    @api.depends('subject_id', 'exam_date')
    def _compute_name(self):
        for record in self:
            record.name = f"{record.subject_id.name if record.subject_id else ''} - {record.exam_date}"

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for record in self:
            record.duration = record.end_time - record.start_time

    @api.constrains('start_time', 'end_time')
    def _check_times(self):
        for record in self:
            if record.start_time >= record.end_time:
                raise ValidationError(_('End time must be after start time!'))
            if record.start_time < 0 or record.end_time > 24:
                raise ValidationError(_('Time must be between 0 and 24!'))

    @api.constrains('exam_date', 'examination_id')
    def _check_exam_date(self):
        for record in self:
            if record.examination_id:
                if (record.exam_date < record.examination_id.start_date or
                        record.exam_date > record.examination_id.end_date):
                    raise ValidationError(_('Exam date must be within examination period!'))

    def action_schedule(self):
        self.write({'state': 'scheduled'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def action_start(self):
        self.write({'state': 'ongoing'})

    def action_complete(self):
        self.write({'state': 'completed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    # ------------------------------------------------------------------
    # Question Paper Preparation Reminder
    # ------------------------------------------------------------------
    def write(self, vals):
        if 'exam_date' in vals or 'course_id' in vals:
            vals = dict(vals, paper_reminder_sent=False, paper_reminder_date=False)
        return super().write(vals)

    def _send_paper_reminder(self):
        """Remind each faculty who teaches the course of this exam to prepare the
        question paper (to-do activity + email). Returns number of reminders sent."""
        sent = 0
        for record in self:
            faculties = record.paper_faculty_ids
            if not faculties:
                record.message_post(body=_(
                    'Question paper reminder could not be sent: no faculty has course '
                    '<b>%s</b> in their Courses Taught list.') % record.course_id.display_name)
                continue
            days_left = (record.exam_date - fields.Date.context_today(record)).days
            for faculty in faculties:
                subject = _('Reminder: Prepare Question Paper - %s') % record.subject_id.display_name
                body = _(
                    '<p>Dear %(faculty)s,</p>'
                    '<p>The exam for <b>%(subject)s</b> (%(course)s) is scheduled on '
                    '<b>%(date)s</b> (%(days)s day(s) left). Please prepare and submit '
                    'the question paper.</p>'
                    '<p><b>Examination:</b> %(exam)s<br/>'
                    '<b>Max Marks:</b> %(marks)s</p>'
                ) % {
                    'faculty': faculty.name,
                    'subject': record.subject_id.display_name,
                    'course': record.course_id.display_name,
                    'date': record.exam_date,
                    'days': max(days_left, 0),
                    'exam': record.examination_id.display_name,
                    'marks': record.max_marks,
                }
                if faculty.user_id:
                    record.activity_schedule(
                        'mail.mail_activity_data_todo',
                        date_deadline=record.exam_date - timedelta(days=2) if days_left > 2 else record.exam_date,
                        summary=subject,
                        note=body,
                        user_id=faculty.user_id.id,
                    )
                email = faculty.work_email or faculty.personal_email
                if email:
                    self.env['mail.mail'].sudo().create({
                        'subject': subject,
                        'body_html': body,
                        'email_to': email,
                        'email_from': self.env.company.email or self.env.user.email_formatted,
                        'auto_delete': True,
                    }).send()
                sent += 1
            record.write({
                'paper_reminder_sent': True,
                'paper_reminder_date': fields.Datetime.now(),
            })
            record.message_post(body=_('Question paper reminder sent to: %s') %
                                ', '.join(faculties.mapped('name')))
        return sent

    def action_send_paper_reminder(self):
        for record in self:
            record._send_paper_reminder()
        return True

    @api.model
    def _cron_send_paper_reminders(self):
        """Daily: for exams that are N days away (default 10) and have no question
        paper yet, remind the faculty teaching that course."""
        today = fields.Date.context_today(self)
        candidates = self.search([
            ('state', 'in', ['draft', 'scheduled']),
            ('paper_reminder_sent', '=', False),
            ('exam_date', '>=', today),
        ])
        due = candidates.filtered(
            lambda t: (t.exam_date - today).days <= (t.paper_reminder_days or 10)
            and not t.question_paper_ready)
        due._send_paper_reminder()