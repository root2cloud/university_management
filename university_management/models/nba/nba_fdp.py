# -*- coding: utf-8 -*-
from odoo import models, fields, api


class NBAFdp(models.Model):
    _name = 'nba.fdp'
    _description = 'NBA FDP / Visiting Faculty (C5.4)'
    _order = 'sar_id, academic_year_id desc'

    sar_id = fields.Many2one('nba.sar', string='SAR', required=True, ondelete='cascade', index=True)
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year')
    year_label = fields.Selection([
        ('CAYm1', 'CAYm1'), ('CAYm2', 'CAYm2'), ('CAYm3', 'CAYm3'),
    ], string='Year')

    person_name = fields.Char(string='Name of Person', required=True)
    designation = fields.Char(string='Designation & Organization')
    course_name = fields.Char(string='Course / Subject Handled')
    hours_handled = fields.Float(string='No. of Hours Handled', digits=(6, 1))
    interaction_type = fields.Selection([
        ('visiting', 'Visiting Faculty'),
        ('adjunct', 'Adjunct Faculty'),
        ('emeritus', 'Emeritus Professor'),
        ('pop', 'Professor of Practice (PoP)'),
        ('industry_expert', 'Industry Expert'),
    ], string='Type', default='visiting')
    is_from_industry = fields.Boolean(string='From Industry / Research Org', default=True)
    notes = fields.Text(string='Notes')