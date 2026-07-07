# -*- coding: utf-8 -*-
from odoo import models, fields, _

class AttendanceReportWizard(models.TransientModel):
    _name = 'attendance.report.wizard'
    _description = 'Attendance Report Wizard'

    date_from = fields.Date(string='Start Date', required=True)
    date_to = fields.Date(string='End Date', required=True)
    student_ids = fields.Many2many('student.student', string='Students')
    program_id = fields.Many2one('university.program', string='Program')
    department_id = fields.Many2one('university.department', string='Department')

    def action_print_report(self):
        """Trigger attendance report"""
        self.ensure_one()
        data = {
            'date_from': self.date_from.isoformat() if self.date_from else False,
            'date_to': self.date_to.isoformat() if self.date_to else False,
            'student_ids': self.student_ids.ids,
            'program_id': self.program_id.id,
            'department_id': self.department_id.id,
        }
        # Action name must match your ir.actions.report xml id
        return self.env.ref('university_management.action_report_attendance').report_action(
            self, data=data
        )
