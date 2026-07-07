# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class UniversityCourse(models.Model):
    _name = 'university.course'
    _description = 'University Course Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'semester_id, name'

    name = fields.Char(string='Course Name', required=True, tracking=True)
    code = fields.Char(string='Course Code', required=True, tracking=True)
    active = fields.Boolean(string='Active', default=True)

    # Academic Links
    program_id = fields.Many2one('university.program', string='Program',
                                 required=True, tracking=True)
    department_id = fields.Many2one('university.department', string='Department',
                                    required=True, tracking=True)
    semester_id = fields.Many2one('university.semester', string='Semester',
                                  required=True, tracking=True)
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year',
                                       required=True, tracking=True)
    batch_id = fields.Many2one('university.batch', string='Batch')

    # Subject
    subject_id = fields.Many2one('university.subject', string='Subject',
                                 required=True, tracking=True)

    # Course Type
    course_type = fields.Selection([
        ('theory', 'Theory'),
        ('practical', 'Practical'),
        ('project', 'Project'),
        ('lab', 'Laboratory'),
        ('seminar', 'Seminar'),
        ('elective', 'Elective'),
    ], string='Course Type', required=True, default='theory', tracking=True)

    # Credits
    credits = fields.Integer(string='Credits', required=True, default=3)
    theory_credits = fields.Integer(string='Theory Credits')
    practical_credits = fields.Integer(string='Practical Credits')

    # Duration
    total_hours = fields.Integer(string='Total Hours', required=True)
    hours_per_week = fields.Integer(string='Hours per Week')

    # Faculty
    faculty_id = fields.Many2one('faculty.faculty', string='Faculty In-charge',
                                 tracking=True)
    co_faculty_ids = fields.Many2many('faculty.faculty', 'course_faculty_rel',
                                      'course_id', 'faculty_id',
                                      string='Co-Faculty')

    # Students
    student_ids = fields.Many2many('student.student', 'course_student_rel',
                                   'course_id', 'student_id', string='Enrolled Students')
    total_enrolled = fields.Integer(string='Total Enrolled', compute='_compute_enrolled', store=True)
    max_students = fields.Integer(string='Max Students', default=60)
    is_full = fields.Boolean(string='Is Full', compute='_compute_capacity_flags', store=True)
    has_available_seats = fields.Boolean(string='Has Available Seats', compute='_compute_capacity_flags', store=True)

    # Classroom
    classroom_id = fields.Many2one('university.classroom', string='Assigned Classroom')

    # Timetable
    timetable_ids = fields.One2many('university.timetable', 'course_id',
                                    string='Class Schedule')

    # Syllabus
    syllabus_id = fields.Many2one('university.syllabus', string='Syllabus')
    learning_outcomes = fields.Html(string='Learning Outcomes')

    # Prerequisites
    prerequisite_course_ids = fields.Many2many('university.course',
                                               'course_prerequisite_rel',
                                               'course_id', 'prerequisite_id',
                                               string='Prerequisites')

    # Examination
    has_internal_exam = fields.Boolean(string='Has Internal Exam', default=True)
    internal_marks = fields.Integer(string='Internal Marks', default=30)
    external_marks = fields.Integer(string='External Marks', default=70)
    total_marks = fields.Integer(string='Total Marks', default=100)
    passing_marks = fields.Integer(string='Passing Marks', default=40)

    # Attendance
    minimum_attendance = fields.Float(string='Minimum Attendance %', default=75.0)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    # Dates
    start_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='End Date')

    # Kept color field for the working of the faculty workload of courses assigned
    color = fields.Integer(string='Color Index', default=0)

    # Description
    description = fields.Html(string='Course Description')
    objectives = fields.Html(string='Course Objectives')

    _sql_constraints = [
        ('code_unique', 'unique(code, academic_year_id)',
         'Course Code must be unique per academic year!'),
    ]

    @api.depends('student_ids')
    def _compute_enrolled(self):
        for record in self:
            record.total_enrolled = len(record.student_ids)

    @api.depends('total_enrolled', 'max_students')
    def _compute_capacity_flags(self):
        for record in self:
            record.is_full = record.total_enrolled >= record.max_students
            record.has_available_seats = record.total_enrolled < record.max_students

    @api.constrains('total_enrolled', 'max_students')
    def _check_enrollment(self):
        for record in self:
            if record.total_enrolled > record.max_students:
                raise ValidationError(_('Cannot enroll more than %s students!') % record.max_students)

    def action_schedule_course(self):
        self.write({'state': 'scheduled'})

    def action_start_course(self):
        self.write({'state': 'ongoing', 'start_date': fields.Date.today()})

    def action_complete_course(self):
        self.write({'state': 'completed', 'end_date': fields.Date.today()})

    def action_cancel_course(self):
        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def action_view_students(self):
        return {
            'name': _('Enrolled Students'),
            'type': 'ir.actions.act_window',
            'res_model': 'student.student',
            'view_mode': 'kanban,list,form',
            'domain': [('id', 'in', self.student_ids.ids)],
        }