# -*- coding: utf-8 -*-

from odoo import models, fields, api


class NBAProgramArticulation(models.Model):
    _name = 'nba.program.articulation'
    _description = 'NBA Program Articulation Matrix (Course vs PO)'
    _order = 'sar_id, course_id'

    sar_id = fields.Many2one('nba.sar', string='SAR', required=True,
                             ondelete='cascade', index=True)
    course_id = fields.Many2one('university.course', string='Course',
                                required=True, index=True)
    course_code = fields.Char(related='course_id.code', string='Course Code', store=True)
    course_name = fields.Char(related='course_id.name', string='Course Name', store=True)
    semester_id = fields.Many2one(
        'university.semester', related='course_id.semester_id',
        string='Semester', store=True
    )

    CORR_SEL = [('0', '-'), ('1', '1'), ('2', '2'), ('3', '3')]

    # Aggregated PO correlations from CO-PO matrix
    po1 = fields.Float(string='PO1', compute='_compute_po_values', store=True)
    po2 = fields.Float(string='PO2', compute='_compute_po_values', store=True)
    po3 = fields.Float(string='PO3', compute='_compute_po_values', store=True)
    po4 = fields.Float(string='PO4', compute='_compute_po_values', store=True)
    po5 = fields.Float(string='PO5', compute='_compute_po_values', store=True)
    po6 = fields.Float(string='PO6', compute='_compute_po_values', store=True)
    po7 = fields.Float(string='PO7', compute='_compute_po_values', store=True)
    po8 = fields.Float(string='PO8', compute='_compute_po_values', store=True)
    po9 = fields.Float(string='PO9', compute='_compute_po_values', store=True)
    po10 = fields.Float(string='PO10', compute='_compute_po_values', store=True)
    po11 = fields.Float(string='PO11', compute='_compute_po_values', store=True)
    pso1 = fields.Float(string='PSO1', compute='_compute_po_values', store=True)
    pso2 = fields.Float(string='PSO2', compute='_compute_po_values', store=True)
    pso3 = fields.Float(string='PSO3', compute='_compute_po_values', store=True)

    @api.depends('course_id', 'sar_id')
    def _compute_po_values(self):
        for rec in self:
            # Aggregate CO-PO matrix values for this course in this SAR
            cos = self.env['nba.co'].search([
                ('sar_id', '=', rec.sar_id.id),
                ('course_id', '=', rec.course_id.id),
            ])
            po_fields = [f'po{i}' for i in range(1, 12)] + ['pso1', 'pso2', 'pso3']
            for po_f in po_fields:
                values = []
                for co in cos:
                    for matrix in co.matrix_ids:
                        val = int(getattr(matrix, po_f, '0') or '0')
                        if val > 0:
                            values.append(val)
                rec[po_f] = round(sum(values) / len(values), 2) if values else 0.0