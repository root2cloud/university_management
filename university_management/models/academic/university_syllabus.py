# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class UniversitySyllabus(models.Model):
    _name = 'university.syllabus'
    _description = 'Syllabus Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'program_id, semester_number'

    name = fields.Char(string='Syllabus Title', required=True, tracking=True)
    code = fields.Char(string='Syllabus Code', required=True)
    active = fields.Boolean(string='Active', default=True)

    # Academic
    program_id = fields.Many2one('university.program', string='Program',
                                 required=True, tracking=True)
    department_id = fields.Many2one(related='program_id.department_id',
                                    string='Department', store=True)
    semester_id = fields.Many2one('university.semester', string='Semester')
    semester_number = fields.Integer(string='Semester', required=True)

    # Subject
    subject_id = fields.Many2one('university.subject', string='Subject',
                                 required=True, tracking=True)

    # Academic Year
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year')

    # Credits & Hours
    credits = fields.Integer(string='Credits', required=True)
    theory_hours = fields.Integer(string='Theory Hours')
    practical_hours = fields.Integer(string='Practical Hours')
    total_hours = fields.Integer(string='Total Hours', compute='_compute_total_hours', store=True)
    total_subjects = fields.Integer(
        string='Total Subjects',
        compute='_compute_subject_count',
        store=True
    )
    total_credits = fields.Integer(
        string='Total Credits',
        compute='_compute_total_credits',
        store=True
    )

    # Course Content
    course_objectives = fields.Html(string='Course Objectives')
    course_outcomes = fields.Html(string='Course Outcomes')

    # Syllabus Units
    unit_ids = fields.One2many('university.syllabus.unit', 'syllabus_id', string='Units')

    # Books & References
    textbooks = fields.Text(string='Textbooks')
    reference_books = fields.Text(string='Reference Books')
    online_resources = fields.Text(string='Online Resources')

    # Assessment
    internal_assessment_structure = fields.Html(string='Internal Assessment Structure')
    external_assessment_structure = fields.Html(string='External Assessment Structure')

    # Attachments
    attachment_ids = fields.Many2many('ir.attachment', string='Syllabus Documents')

    # Version
    version = fields.Char(string='Version', default='1.0')
    effective_from = fields.Date(string='Effective From')

    # Approval
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    approval_date = fields.Date(string='Approval Date', readonly=True)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('published', 'Published'),
    ], string='Status', default='draft', tracking=True)

    # Description
    description = fields.Html(string='Description')

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Syllabus Code must be unique!'),
    ]

    @api.depends('theory_hours', 'practical_hours')
    def _compute_total_hours(self):
        for record in self:
            record.total_hours = record.theory_hours + record.practical_hours

    @api.depends('unit_ids')
    def _compute_subject_count(self):
        """Count number of units/topics in the syllabus"""
        for record in self:
            record.total_subjects = len(record.unit_ids)

    @api.depends('credits')
    def _compute_total_credits(self):
        """Total credits for this syllabus"""
        for record in self:
            record.total_credits = record.credits

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
            'approval_date': fields.Date.today()
        })

    def action_publish(self):
        self.write({'state': 'published'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})


class UniversitySyllabusUnit(models.Model):
    _name = 'university.syllabus.unit'
    _description = 'Syllabus Unit'
    _order = 'sequence, name'

    name = fields.Char(string='Unit Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    syllabus_id = fields.Many2one('university.syllabus', string='Syllabus',
                                  required=True, ondelete='cascade')

    # Content
    topics = fields.Html(string='Topics Covered')
    learning_outcomes = fields.Html(string='Learning Outcomes')

    # Duration
    hours = fields.Integer(string='Hours')

    # Description
    description = fields.Text(string='Description')
