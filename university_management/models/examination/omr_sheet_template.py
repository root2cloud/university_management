# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class OMRSheetTemplate(models.Model):
    """
    Configurable OMR sheet format template.
    Defines the grid layout — number of questions, sub-parts,
    whether there is a Part-A + Part-B, etc.
    Each examination can pick a template, and per-student OMR sheets
    are generated from it.
    """
    _name = 'exam.omr.template'
    _description = 'OMR Sheet Template'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(string='Template Name', required=True, tracking=True)
    code = fields.Char(string='Template Code', required=True)
    active = fields.Boolean(default=True)
    description = fields.Text(string='Description')

    sheet_count = fields.Integer(string='OMR Sheets', compute='_compute_sheet_count')

    def _compute_sheet_count(self):
        grouped = {}
        if self.ids:
            data = self.env['exam.omr.sheet'].read_group(
                [('omr_template_id', 'in', self.ids)],
                ['omr_template_id'], ['omr_template_id'])
            grouped = {d['omr_template_id'][0]: d['omr_template_id_count'] for d in data}
        for rec in self:
            rec.sheet_count = grouped.get(rec.id, 0)

    def action_view_sheets(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('OMR Sheets'),
            'res_model': 'exam.omr.sheet',
            'view_mode': 'list,form',
            'domain': [('omr_template_id', '=', self.id)],
            'context': {'default_omr_template_id': self.id},
        }

    # ------------------------------------------------------------------
    # Format selection
    # ------------------------------------------------------------------
    format_type = fields.Selection([
        ('r20', 'R20 — Part-A (Objective) + Part-B (Descriptive)'),
        ('r22', 'R22 — 10 Questions with sub-parts (a,b,c,d)'),
        ('custom', 'Custom'),
    ], string='Format Type', required=True, default='r20', tracking=True)

    # Institution details printed on OMR
    institution_name = fields.Char(
        string='Institution Name',
        default='LENDI INSTITUTE OF ENGINEERING AND TECHNOLOGY',
    )
    institution_subtitle = fields.Char(
        string='Subtitle',
        default='An Autonomous Institution',
    )
    institution_accreditation = fields.Text(
        string='Accreditation / Address Lines',
        default=('Approved by AICTE & Permanently Affiliated to JNTUGV, Vizianagaram\n'
                 'Accredited by NAAC with "A" Grade\n'
                 'Jonnada (Village), Denkada (Mandal), Vizianagaram Dist. \u2013 535 005'),
        help='One line per row — printed under the subtitle, e.g. AICTE '
             'approval, affiliation, NAAC grade, and campus address.',
    )

    # ------------------------------------------------------------------
    # R22 format settings
    # ------------------------------------------------------------------
    r22_total_questions = fields.Integer(
        string='Total Questions (R22)', default=10,
        help='Number of question rows in the grid',
    )
    r22_sub_parts = fields.Integer(
        string='Sub-parts per Question', default=4,
        help='Columns a, b, c, d = 4',
    )

    # ------------------------------------------------------------------
    # R20 format settings
    # ------------------------------------------------------------------
    # Part-A
    r20_part_a_columns = fields.Integer(
        string='Part-A Columns', default=10,
        help='Number of columns A through J',
    )
    r20_part_a_questions = fields.Integer(
        string='Part-A Question Rows', default=1,
        help='Usually 1 row for Part-A',
    )
    # Part-B
    r20_part_b_questions = fields.Integer(
        string='Part-B Questions', default=12,
        help='Number of question rows in Part-B grid',
    )
    r20_part_b_sub_parts = fields.Integer(
        string='Part-B Sub-parts', default=4,
        help='Columns a, b, c, d per question',
    )

    # ------------------------------------------------------------------
    # Custom format settings
    # ------------------------------------------------------------------
    custom_total_questions = fields.Integer(string='Total Questions', default=10)
    custom_sub_parts = fields.Integer(string='Sub-parts', default=4)
    custom_has_part_a = fields.Boolean(string='Has Part-A Section', default=False)
    custom_part_a_columns = fields.Integer(string='Part-A Columns', default=10)

    # ------------------------------------------------------------------
    # Valuation settings (sheets printed)
    # ------------------------------------------------------------------
    valuation_copies = fields.Integer(
        string='Valuation Copies', default=2,
        help='How many valuation sheets (Part-II = Valuation 1, Part-III = Re-Valuation 2)',
    )

    # ------------------------------------------------------------------
    # Company
    # ------------------------------------------------------------------
    company_id = fields.Many2one('res.company', default=lambda s: s.env.company)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Template Code must be unique!'),
    ]

    def get_grid_config(self):
        """
        Return a dict describing the grid layout for PDF generation
        and OCR parsing.
        """
        self.ensure_one()
        if self.format_type == 'r22':
            return {
                'format': 'r22',
                'parts': [{
                    'name': 'main',
                    'questions': self.r22_total_questions,
                    'sub_parts': self.r22_sub_parts,
                    'columns_per_row': 2,  # questions shown in pairs (1,2), (3,4) …
                }],
                'valuation_copies': self.valuation_copies,
            }
        elif self.format_type == 'r20':
            return {
                'format': 'r20',
                'parts': [
                    {
                        'name': 'part_a',
                        'label': 'PART-A',
                        'columns': self.r20_part_a_columns,
                        'rows': self.r20_part_a_questions,
                    },
                    {
                        'name': 'part_b',
                        'label': 'PART-B',
                        'questions': self.r20_part_b_questions,
                        'sub_parts': self.r20_part_b_sub_parts,
                        'columns_per_row': 2,
                    },
                ],
                'valuation_copies': self.valuation_copies,
            }
        else:
            cfg = {
                'format': 'custom',
                'parts': [],
                'valuation_copies': self.valuation_copies,
            }
            if self.custom_has_part_a:
                cfg['parts'].append({
                    'name': 'part_a',
                    'label': 'PART-A',
                    'columns': self.custom_part_a_columns,
                    'rows': 1,
                })
            cfg['parts'].append({
                'name': 'main',
                'questions': self.custom_total_questions,
                'sub_parts': self.custom_sub_parts,
                'columns_per_row': 2,
            })
            return cfg