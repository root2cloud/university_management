# -*- coding: utf-8 -*-

from odoo import models, fields, api


class NBAPSO(models.Model):
    _name = 'nba.pso'
    _description = 'NBA Program Specific Outcomes (PSOs)'
    _order = 'sar_id, sequence'

    sar_id = fields.Many2one('nba.sar', string='SAR', required=True, ondelete='cascade', index=True)
    program_id = fields.Many2one(
        'university.program', string='Program',
        related='sar_id.program_id', store=True
    )
    sequence = fields.Integer(string='PSO No.', default=1)
    name = fields.Char(string='PSO Label', compute='_compute_name', store=True)
    statement = fields.Text(string='PSO Statement', required=True)
    knowledge_domain = fields.Char(string='Knowledge Domain')

    # PO correlations for PSO
    po1 = fields.Integer(string='PO1', default=0)
    po2 = fields.Integer(string='PO2', default=0)
    po3 = fields.Integer(string='PO3', default=0)
    po4 = fields.Integer(string='PO4', default=0)
    po5 = fields.Integer(string='PO5', default=0)
    po6 = fields.Integer(string='PO6', default=0)
    po7 = fields.Integer(string='PO7', default=0)
    po8 = fields.Integer(string='PO8', default=0)
    po9 = fields.Integer(string='PO9', default=0)
    po10 = fields.Integer(string='PO10', default=0)
    po11 = fields.Integer(string='PO11', default=0)

    @api.depends('sequence')
    def _compute_name(self):
        for rec in self:
            rec.name = f'PSO{rec.sequence}'

    @api.constrains('sequence')
    def _check_sequence(self):
        for rec in self:
            if not (1 <= rec.sequence <= 3):
                raise models.ValidationError('PSO sequence must be between 1 and 3 (max 3 PSOs).')