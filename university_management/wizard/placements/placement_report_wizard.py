# -*- coding: utf-8 -*-
from odoo import models, fields, _

class PlacementReportWizard(models.TransientModel):
    _name = 'placement.report.wizard'
    _description = 'Placement Statistics Report Wizard'

    academic_year_id = fields.Many2one(
        'university.academic.year', string='Academic Year'
    )
    program_id = fields.Many2one(
        'university.program', string='Program'
    )
    department_id = fields.Many2one(
        'university.department', string='Department'
    )
    date_from = fields.Date(string='From Date')
    date_to = fields.Date(string='To Date')
    include_year_comparison = fields.Boolean(
        string='Include Year-wise Comparison', default=True
    )
    remarks = fields.Text(string='Remarks')

    def action_print_report(self):
        """Trigger placement statistics report"""
        self.ensure_one()
        data = {
            'academic_year_id': self.academic_year_id.id,
            'program_id': self.program_id.id,
            'department_id': self.department_id.id,
            'date_from': self.date_from.isoformat() if self.date_from else False,
            'date_to': self.date_to.isoformat() if self.date_to else False,
            'include_year_comparison': self.include_year_comparison,
            'remarks': self.remarks,
        }
        return self.env.ref(
            'university_management.action_report_placement_statistics'
        ).report_action(self, data=data)
