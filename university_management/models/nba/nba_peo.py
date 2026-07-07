# -*- coding: utf-8 -*-

from odoo import models, fields, api


class NBAPEO(models.Model):
    _name = 'nba.peo'
    _description = 'NBA Program Educational Objectives (PEOs)'
    _order = 'sar_id, sequence'

    sar_id = fields.Many2one('nba.sar', string='SAR', required=True, ondelete='cascade', index=True)
    program_id = fields.Many2one(
        'university.program', string='Program',
        related='sar_id.program_id', store=True
    )
    sequence = fields.Integer(string='PEO No.', default=1)
    name = fields.Char(
        string='PEO Label', compute='_compute_name', store=True,
        help='Auto-generated as PEO1, PEO2 ...'
    )
    statement = fields.Text(string='PEO Statement', required=True)

    # Mission element correlations (M1 to M5)
    m1_corr = fields.Selection(
        [('0', '-'), ('1', '1-Low'), ('2', '2-Medium'), ('3', '3-High')],
        string='M1', default='0'
    )
    m2_corr = fields.Selection(
        [('0', '-'), ('1', '1-Low'), ('2', '2-Medium'), ('3', '3-High')],
        string='M2', default='0'
    )
    m3_corr = fields.Selection(
        [('0', '-'), ('1', '1-Low'), ('2', '2-Medium'), ('3', '3-High')],
        string='M3', default='0'
    )
    m4_corr = fields.Selection(
        [('0', '-'), ('1', '1-Low'), ('2', '2-Medium'), ('3', '3-High')],
        string='M4', default='0'
    )
    m5_corr = fields.Selection(
        [('0', '-'), ('1', '1-Low'), ('2', '2-Medium'), ('3', '3-High')],
        string='M5', default='0'
    )

    notes = fields.Text(string='Rationale / Justification')

    @api.depends('sequence')
    def _compute_name(self):
        for rec in self:
            rec.name = f'PEO{rec.sequence}'

    @api.constrains('sequence')
    def _check_sequence(self):
        for rec in self:
            if not (1 <= rec.sequence <= 5):
                raise models.ValidationError('PEO sequence must be between 1 and 5 (max 5 PEOs).')