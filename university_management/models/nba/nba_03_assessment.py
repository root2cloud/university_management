# -*- coding: utf-8 -*-

from odoo import models, fields, api


class NBAC3Assessment(models.Model):
    _name = 'nba.c3.assessment'
    _description = 'NBA Criterion 3 - CO/PO Assessment Records'
    _order = 'sar_id, course_id'

    sar_id = fields.Many2one('nba.sar', string='SAR', required=True,
                             ondelete='cascade', index=True)
    course_id = fields.Many2one('university.course', string='Course', required=True, index=True)
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year')

    # Direct PO attainment (Table 3.8.1)
    po1_direct = fields.Float(string='PO1', digits=(5, 2))
    po2_direct = fields.Float(string='PO2', digits=(5, 2))
    po3_direct = fields.Float(string='PO3', digits=(5, 2))
    po4_direct = fields.Float(string='PO4', digits=(5, 2))
    po5_direct = fields.Float(string='PO5', digits=(5, 2))
    po6_direct = fields.Float(string='PO6', digits=(5, 2))
    po7_direct = fields.Float(string='PO7', digits=(5, 2))
    po8_direct = fields.Float(string='PO8', digits=(5, 2))
    po9_direct = fields.Float(string='PO9', digits=(5, 2))
    po10_direct = fields.Float(string='PO10', digits=(5, 2))
    po11_direct = fields.Float(string='PO11', digits=(5, 2))
    pso1_direct = fields.Float(string='PSO1', digits=(5, 2))
    pso2_direct = fields.Float(string='PSO2', digits=(5, 2))
    pso3_direct = fields.Float(string='PSO3', digits=(5, 2))

    @api.model
    def compute_from_co_matrix(self, sar_id):
        """
        Compute Table 3.8.1: PO attainment per course from CO attainment × CO-PO correlation.
        Formula: PO_k_for_course = avg(CO_attainment × CO-PO_k / 3) for all COs mapping to PO_k
        """
        sar = self.env['nba.sar'].browse(sar_id)
        courses = self.env['nba.co'].search([('sar_id', '=', sar_id)]).mapped('course_id')

        for course in courses:
            cos = self.env['nba.co'].search([
                ('sar_id', '=', sar_id),
                ('course_id', '=', course.id),
            ])
            po_vals = {}
            for i in range(1, 12):
                po_key = f'po{i}'
                contributions = []
                for co in cos:
                    for matrix in co.matrix_ids:
                        corr = int(getattr(matrix, po_key, '0') or '0')
                        if corr > 0:
                            contributions.append(co.attainment_overall * corr / 3.0)
                po_vals[f'po{i}_direct'] = round(
                    sum(contributions) / len(contributions), 2
                ) if contributions else 0.0

            existing = self.search([
                ('sar_id', '=', sar_id),
                ('course_id', '=', course.id),
            ])
            vals = {**po_vals, 'sar_id': sar_id, 'course_id': course.id}
            if existing:
                existing.write(po_vals)
            else:
                self.create(vals)


class NBAC3IndirectAttainment(models.Model):
    _name = 'nba.c3.indirect'
    _description = 'NBA Criterion 3 - Indirect PO Attainment (Survey Data)'
    _order = 'sar_id, survey_name'

    sar_id = fields.Many2one('nba.sar', string='SAR', required=True,
                             ondelete='cascade', index=True)
    survey_name = fields.Char(string='Survey Name', required=True,
                              help='e.g., Exit Survey 2023-24, Employer Survey')
    survey_type = fields.Selection([
        ('exit_survey', 'Student Exit Survey'),
        ('employer_survey', 'Employer Survey'),
        ('alumni_survey', 'Alumni Survey'),
        ('other', 'Other'),
    ], string='Survey Type', default='exit_survey')

    # Indirect PO attainment values
    po1 = fields.Float(string='PO1', digits=(5, 2))
    po2 = fields.Float(string='PO2', digits=(5, 2))
    po3 = fields.Float(string='PO3', digits=(5, 2))
    po4 = fields.Float(string='PO4', digits=(5, 2))
    po5 = fields.Float(string='PO5', digits=(5, 2))
    po6 = fields.Float(string='PO6', digits=(5, 2))
    po7 = fields.Float(string='PO7', digits=(5, 2))
    po8 = fields.Float(string='PO8', digits=(5, 2))
    po9 = fields.Float(string='PO9', digits=(5, 2))
    po10 = fields.Float(string='PO10', digits=(5, 2))
    po11 = fields.Float(string='PO11', digits=(5, 2))
    pso1 = fields.Float(string='PSO1', digits=(5, 2))
    pso2 = fields.Float(string='PSO2', digits=(5, 2))
    pso3 = fields.Float(string='PSO3', digits=(5, 2))

    respondent_count = fields.Integer(string='No. of Respondents')
    survey_date = fields.Date(string='Survey Date')
    source_reference = fields.Char(string='Source Reference')