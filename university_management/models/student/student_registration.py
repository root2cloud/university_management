# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class StudentRegistration(models.Model):
    _name = 'student.registration'
    _description = 'Student Course Registration'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'registration_date desc'

    name = fields.Char(string='Registration Number', required=True, readonly=True,
                       copy=False, default='/')

    # Student
    student_id = fields.Many2one('student.student', string='Student',
                                 required=True, tracking=True, index=True)
    registration_number = fields.Char(related='student_id.registration_number',
                                      string='Student Registration')

    # Academic
    program_id = fields.Many2one(related='student_id.program_id', string='Program', store=True)
    department_id = fields.Many2one(related='student_id.department_id',
                                    string='Department', store=True)
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year',
                                       required=True, tracking=True)
    semester_id = fields.Many2one('university.semester', string='Semester',
                                  required=True, tracking=True)

    # Registration
    registration_date = fields.Date(string='Registration Date', default=fields.Date.today(),
                                    required=True, tracking=True)

    # Courses
    course_ids = fields.Many2many('university.course', 'registration_course_rel',
                                  'registration_id', 'course_id',
                                  string='Registered Courses', tracking=True, store=True)
    total_credits = fields.Integer(string='Total Credits', compute='_compute_credits', store=True)

    # Approval
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    approval_date = fields.Date(string='Approval Date', readonly=True)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('registered', 'Registered'),
        ('approved', 'Approved'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    # Notes
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Registration Number must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('student.registration') or '/'
        return super(StudentRegistration, self).create(vals)

    @api.depends('course_ids', 'course_ids.credits')
    def _compute_credits(self):
        for record in self:
            record.total_credits = sum(record.course_ids.mapped('credits'))

    @api.constrains('total_credits')
    def _check_credits(self):
        for record in self:
            if record.total_credits > 30:  # Example: max 30 credits per semester
                raise ValidationError(_('Total credits cannot exceed 30 per semester!'))

    def action_register(self):
        """Register for courses"""
        # Add student to courses
        for course in self.course_ids:
            course.write({'student_ids': [(4, self.student_id.id)]})

        self.write({'state': 'registered'})

    def action_approve(self):
        """Approve registration"""
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
            'approval_date': fields.Date.today()
        })

    def action_cancel(self):
        """Cancel registration"""
        # Remove student from courses
        for course in self.course_ids:
            course.write({'student_ids': [(3, self.student_id.id)]})

        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})
