# -*- coding: utf-8 -*-

from odoo import models, fields, api


class NBACoPoMatrix(models.Model):
    _name = 'nba.co.po.matrix'
    _description = 'NBA CO-PO Articulation Matrix'
    _order = 'co_id'

    co_id = fields.Many2one('nba.co', string='Course Outcome', required=True,
                            ondelete='cascade', index=True)
    course_id = fields.Many2one(
        'university.course', string='Course',
        related='co_id.course_id', store=True
    )
    sar_id = fields.Many2one(
        'nba.sar', string='SAR',
        related='co_id.sar_id', store=True
    )

    CORR_SEL = [('0', '-'), ('1', '1-Low'), ('2', '2-Medium'), ('3', '3-High')]

    # PO correlations (PO1-PO11)
    po1 = fields.Selection(CORR_SEL, string='PO1', default='0')
    po2 = fields.Selection(CORR_SEL, string='PO2', default='0')
    po3 = fields.Selection(CORR_SEL, string='PO3', default='0')
    po4 = fields.Selection(CORR_SEL, string='PO4', default='0')
    po5 = fields.Selection(CORR_SEL, string='PO5', default='0')
    po6 = fields.Selection(CORR_SEL, string='PO6', default='0')
    po7 = fields.Selection(CORR_SEL, string='PO7', default='0')
    po8 = fields.Selection(CORR_SEL, string='PO8', default='0')
    po9 = fields.Selection(CORR_SEL, string='PO9', default='0')
    po10 = fields.Selection(CORR_SEL, string='PO10', default='0')
    po11 = fields.Selection(CORR_SEL, string='PO11', default='0')

    # PSO correlations (up to 3)
    pso1 = fields.Selection(CORR_SEL, string='PSO1', default='0')
    pso2 = fields.Selection(CORR_SEL, string='PSO2', default='0')
    pso3 = fields.Selection(CORR_SEL, string='PSO3', default='0')

    def get_po_value(self, po_name):
        """Return integer value for a PO field."""
        return int(getattr(self, po_name, '0') or '0')