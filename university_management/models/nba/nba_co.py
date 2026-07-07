# -*- coding: utf-8 -*-

from odoo import models, fields, api


class NBACO(models.Model):
    _name = 'nba.co'
    _description = 'NBA Course Outcomes (COs)'
    _order = 'sar_id, course_id, sequence'

    sar_id = fields.Many2one('nba.sar', string='SAR', required=True, ondelete='cascade', index=True)
    course_id = fields.Many2one('university.course', string='Course', required=True, index=True)
    semester_id = fields.Many2one(
        'university.semester', string='Semester',
        related='course_id.semester_id', store=True
    )
    program_id = fields.Many2one(
        'university.program', string='Program',
        related='sar_id.program_id', store=True
    )

    sequence = fields.Integer(string='CO No.', default=1)
    name = fields.Char(string='CO Label', compute='_compute_name', store=True)
    statement = fields.Text(string='CO Statement', required=True,
                            help='Measurable outcome statement')

    bloom_level = fields.Selection([
        ('remember', 'Remember (L1)'),
        ('understand', 'Understand (L2)'),
        ('apply', 'Apply (L3)'),
        ('analyze', 'Analyze (L4)'),
        ('evaluate', 'Evaluate (L5)'),
        ('create', 'Create (L6)'),
    ], string="Bloom's Level", default='apply')

    target_level = fields.Float(
        string='Target Attainment (%)', default=60.0,
        help='Target % of students meeting this CO'
    )

    # ─── Attainment ──────────────────────────────────────────────────────────
    attainment_cie = fields.Float(
        string='CIE Attainment (%)', default=0.0,
        help='% from Continuous Internal Evaluation (CIE / Mid-term)'
    )
    attainment_see = fields.Float(
        string='SEE Attainment (%)', default=0.0,
        help='% from Semester End Examination (SEE)'
    )
    attainment_overall = fields.Float(
        string='Overall Attainment (%)',
        compute='_compute_overall_attainment', store=True
    )
    target_met = fields.Boolean(
        string='Target Met', compute='_compute_overall_attainment', store=True
    )

    # ─── CO-PO Matrix (inline) ────────────────────────────────────────────────
    matrix_ids = fields.One2many('nba.co.po.matrix', 'co_id', string='CO-PO Matrix')

    @api.depends('sequence', 'course_id')
    def _compute_name(self):
        for rec in self:
            code = rec.course_id.code if rec.course_id else 'CO'
            rec.name = f'{code}-CO{rec.sequence}'

    @api.depends('attainment_cie', 'attainment_see')
    def _compute_overall_attainment(self):
        for rec in self:
            # NBA standard: 40% weight to CIE, 60% weight to SEE
            rec.attainment_overall = round(0.4 * rec.attainment_cie + 0.6 * rec.attainment_see, 2)
            rec.target_met = rec.attainment_overall >= rec.target_level

    def _compute_attainment(self):
        """Auto-pull attainment from examination records."""
        for rec in self:
            if not rec.course_id:
                continue
            # CIE: avg from exam evaluations for this course
            exam_evals = self.env['examination.result'].search([
                ('course_id', '=', rec.course_id.id),
                ('is_absent', '=', False),
            ])
            if exam_evals:
                pass_rate_cie = sum(1 for e in exam_evals if e.internal_marks >= (e.internal_max * 0.4)) / len(exam_evals) * 100
                rec.attainment_cie = round(pass_rate_cie, 2)

            # SEE: from final exam results
            see_evals = self.env['examination.result'].search([
                ('course_id', '=', rec.course_id.id),
                ('is_absent', '=', False),
            ])
            if see_evals:
                pass_rate_see = sum(1 for e in see_evals if e.is_pass) / len(see_evals) * 100
                rec.attainment_see = round(pass_rate_see, 2)

    @api.constrains('sequence')
    def _check_sequence(self):
        for rec in self:
            if not (1 <= rec.sequence <= 6):
                raise models.ValidationError('CO sequence must be between 1 and 6 (max 6 COs per course).')