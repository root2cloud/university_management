# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class UniversitySubject(models.Model):
    _name = 'university.subject'
    _description = 'University Subject Master'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Subject Name', required=True, tracking=True)
    code = fields.Char(string='Subject Code', required=True, tracking=True)
    active = fields.Boolean(string='Active', default=True)
    image_128 = fields.Image(string='Image', max_width=128, max_height=128)

    # Department
    department_id = fields.Many2one('university.department', string='Department',
                                    required=True, tracking=True)
    semester_number = fields.Integer(string='Semester Number', help='Which semester this subject is taught in')

    # Subject Type
    subject_type = fields.Selection([
        ('core', 'Core Subject'),
        ('elective', 'Elective'),
        ('open_elective', 'Open Elective'),
        ('mandatory', 'Mandatory'),
        ('lab', 'Laboratory'),
    ], string='Subject Type', required=True, default='core')

    # Credits
    credits = fields.Integer(string='Credits', required=True, default=3)
    theory_credits = fields.Integer(string='Theory Credits')
    practical_credits = fields.Integer(string='Practical Credits')

    # Duration
    total_hours = fields.Integer(string='Total Hours', compute='_compute_total_hours', store=True)
    theory_hours = fields.Integer(string='Theory Hours')
    practical_hours = fields.Integer(string='Practical Hours')

    # Courses
    course_ids = fields.One2many('university.course', 'subject_id', string='Courses')
    course_count = fields.Integer(
        string='Total Courses',
        compute='_compute_course_count',
        store=True
    )

    # Faculty
    faculty_ids = fields.Many2many('faculty.faculty', 'subject_faculty_rel',
                                   'subject_id', 'faculty_id',
                                   string='Faculty Teaching')

    # Syllabus
    syllabus_ids = fields.One2many('university.syllabus', 'subject_id', string='Syllabus')

    # Description
    description = fields.Html(string='Subject Description')
    learning_outcomes = fields.Html(string='Learning Outcomes')
    textbooks = fields.Text(string='Textbooks & References')

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Subject Code must be unique!'),
    ]

    @api.depends('theory_hours', 'practical_hours')
    def _compute_total_hours(self):
        for record in self:
            record.total_hours = (record.theory_hours or 0) + (record.practical_hours or 0)

    @api.depends('course_ids')
    def _compute_course_count(self):
        for record in self:
            record.course_count = len(record.course_ids)

    def action_view_courses(self):
        """Open courses list filtered by this subject"""
        return {
            'name': _('Courses'),
            'type': 'ir.actions.act_window',
            'res_model': 'university.course',
            'view_mode': 'list,form,kanban',
            'domain': [('subject_id', '=', self.id)],
            'context': {'default_subject_id': self.id}
        }


