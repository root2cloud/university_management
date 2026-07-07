# -*- coding: utf-8 -*-

from odoo import models, fields, api


class NBAC2Teaching(models.Model):
    _name = 'nba.c2.teaching'
    _description = 'NBA Criterion 2 - Teaching Learning Activity Details'
    _order = 'sar_id, activity_type'

    sar_id = fields.Many2one('nba.sar', string='SAR', required=True,
                             ondelete='cascade', index=True)
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year')

    activity_type = fields.Selection([
        ('capstone_project', 'Capstone Project'),
        ('mini_project', 'Mini Project'),
        ('internship', 'Industry Internship'),
        ('mooc', 'MOOC / SWAYAM Course'),
        ('case_study', 'Case Study'),
        ('seminar', 'Seminar'),
        ('industry_visit', 'Industry Visit'),
        ('workshop', 'Workshop'),
        ('hackathon', 'Hackathon'),
        ('other', 'Other'),
    ], string='Activity Type', required=True)

    title = fields.Char(string='Title / Description', required=True)
    student_count = fields.Integer(string='No. of Students Involved')
    faculty_id = fields.Many2one('faculty.faculty', string='Faculty Guide')
    program_id = fields.Many2one(
        'university.program', string='Program',
        related='sar_id.program_id', store=True
    )

    # POs addressed
    po_addressed = fields.Char(
        string='POs/PSOs Addressed',
        help='e.g., PO1, PO2, PO5, PSO1'
    )
    sdg_addressed = fields.Char(
        string='SDGs Addressed',
        help='e.g., SDG4, SDG9, SDG13'
    )

    outcome_description = fields.Text(string='Outcome / Impact')
    duration = fields.Char(string='Duration')
    reference_link = fields.Char(string='Reference / URL')

    # For MOOCs
    mooc_platform = fields.Char(string='Platform (SWAYAM/NPTEL/Coursera)')
    mooc_certified_count = fields.Integer(string='No. of Students Certified')