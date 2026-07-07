# -*- coding: utf-8 -*-

from odoo import models, fields, api


class NAACStudentProgression(models.Model):
    _name = 'naac.student.progression'
    _description = 'NAAC Student Progression'
    _inherit = ['mail.thread']
    _order = 'year desc'

    name = fields.Char(string='Title / Description', required=True)
    student_id = fields.Many2one('student.student', string='Student', index=True)
    department_id = fields.Many2one('university.department', string='Department',
                                     related='student_id.department_id', store=True)
    program_id = fields.Many2one('university.program', string='Program',
                                  related='student_id.program_id', store=True)

    progression_type = fields.Selection([
        ('placement', 'Placement / Employment'),
        ('higher_study', 'Higher Studies'),
        ('entrepreneur', 'Entrepreneurship'),
        ('civil_services', 'Civil Services / Competitive Exams'),
        ('scholarship', 'Scholarship'),
        ('award', 'Award / Achievement'),
        ('sports', 'Sports / Cultural Achievement'),
        ('other', 'Other'),
    ], string='Progression Type', required=True, tracking=True)

    year = fields.Char(string='Year / Academic Year', required=True)

    # Placement fields
    company_name = fields.Char(string='Company / Organization')
    designation = fields.Char(string='Designation / Role')
    salary_package = fields.Monetary(string='CTC / Package (INR)',
                                      currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Higher Studies
    institution_name = fields.Char(string='Institution Name')
    program_name = fields.Char(string='Program / Course')
    entrance_exam = fields.Char(string='Entrance Exam (GATE/GRE/GMAT etc)')
    entrance_rank = fields.Char(string='Rank / Score')

    # Scholarship / Award
    scholarship_name = fields.Char(string='Scholarship / Award Name')
    awarding_body = fields.Char(string='Awarding Body')
    amount = fields.Monetary(string='Amount (if applicable)', currency_field='currency_id')

    # NAAC link
    criterion_id = fields.Many2one('naac.criterion', string='NAAC Criterion',
                                    default=lambda self: self.env['naac.criterion'].search(
                                        [('criterion_number', '=', 5)], limit=1))
    metric_id = fields.Many2one('naac.metric', string='Metric',
                                 domain="[('criterion_id', '=', criterion_id)]")

    evidence_document = fields.Binary(string='Supporting Document', attachment=True)
    evidence_filename = fields.Char(string='Filename')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('verified', 'Verified'),
    ], string='Status', default='draft', tracking=True)

    notes = fields.Text(string='Notes')

    def action_verify(self):
        self.write({'state': 'verified'})
