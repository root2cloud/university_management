# -*- coding: utf-8 -*-

from odoo import models, fields, api


class NBALabInfo(models.Model):
    _name = 'nba.lab.info'
    _description = 'NBA Criterion 7 - Laboratory Information'
    _order = 'sar_id, lab_type, name'

    sar_id = fields.Many2one('nba.sar', string='SAR', required=True,
                             ondelete='cascade', index=True)
    name = fields.Char(string='Laboratory Name', required=True)

    lab_type = fields.Selection([
        ('teaching', '7.1 Teaching Laboratory'),
        ('additional', '7.2 Additional Facility'),
        ('project', '7.5 Project / Research Lab'),
        ('coe', '7.5 Centre of Excellence'),
        ('innovation', '7.5 Innovation / Startup Lab'),
    ], string='Lab Type', required=True, default='teaching')

    department_id = fields.Many2one(
        'university.department', string='Department',
        related='sar_id.department_id', store=True
    )

    # Asset link
    asset_id = fields.Many2one('asset.asset', string='Linked Asset Record')

    # 7.1 Details
    batch_size = fields.Integer(string='Students per Setup (Batch Size)')
    major_equipment = fields.Text(string='Major Equipment List')
    weekly_utilization = fields.Text(
        string='Weekly Utilization (Courses)',
        help='List courses for which this lab is utilized'
    )

    # Technical Staff
    tech_staff_name = fields.Char(string='Technical Staff Name')
    tech_staff_designation = fields.Char(string='Designation')
    tech_staff_qualification = fields.Char(string='Qualification')

    # 7.2 Additional Facility
    facility_purpose = fields.Text(string='Purpose for Creating Facility')
    facility_utilization = fields.Text(string='Utilization Details')
    po_relevance = fields.Char(string='Relevance to POs/PSOs')

    # 7.4 Safety
    safety_measures = fields.Text(string='Safety Measures')

    # 7.5 Project/Research Lab
    project_lab_description = fields.Text(string='Project Lab / CoE Description')
    startups_supported = fields.Integer(string='No. of Startups Supported')

    # Course mapping
    course_ids = fields.Many2many(
        'university.course', 'nba_lab_course_rel', 'lab_id', 'course_id',
        string='Courses Using This Lab'
    )

    notes = fields.Text(string='Additional Notes')