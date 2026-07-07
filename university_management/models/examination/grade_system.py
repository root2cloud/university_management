# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ExaminationGradeSystem(models.Model):
    _name = 'examination.grade.system'
    _description = 'Grading System (CGPA/Percentage)'
    _order = 'min_percentage desc'

    name = fields.Char(string='Grade Name', required=True)
    grade = fields.Char(string='Grade Letter', required=True, size=3,
                        help='e.g., O, A+, A, B+, B, C, D, F', store=True)
    grade_point = fields.Float(string='Grade Point', required=True,
                               help='e.g., 10, 9, 8, 7, etc.')

    # Percentage Range
    min_percentage = fields.Float(string='Minimum Percentage', required=True)
    max_percentage = fields.Float(string='Maximum Percentage', required=True)

    # Marks Range (alternative)
    min_marks = fields.Integer(string='Minimum Marks')
    max_marks = fields.Integer(string='Maximum Marks')

    # Status
    is_pass = fields.Boolean(string='Passing Grade', default=True)

    # Color for display
    color = fields.Integer(string='Color Index')

    # Description
    description = fields.Text(string='Description')

    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('grade_unique', 'unique(grade)', 'Grade Letter must be unique!'),
        ('grade_point_unique', 'unique(grade_point)', 'Grade Point must be unique!'),
    ]

    @api.constrains('min_percentage', 'max_percentage')
    def _check_percentage_range(self):
        for record in self:
            if record.min_percentage < 0 or record.max_percentage > 100:
                raise ValidationError(_('Percentage must be between 0 and 100!'))
            if record.min_percentage >= record.max_percentage:
                raise ValidationError(_('Maximum percentage must be greater than minimum percentage!'))

    @api.constrains('min_percentage', 'max_percentage')
    def _check_overlapping_ranges(self):
        for record in self:
            overlapping = self.search([
                ('id', '!=', record.id),
                '|',
                '&', ('min_percentage', '<=', record.min_percentage),
                ('max_percentage', '>=', record.min_percentage),
                '&', ('min_percentage', '<=', record.max_percentage),
                ('max_percentage', '>=', record.max_percentage),
            ])
            if overlapping:
                raise ValidationError(_('Grade ranges cannot overlap!'))
