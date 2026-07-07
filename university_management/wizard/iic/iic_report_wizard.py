# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class IICReportWizard(models.TransientModel):
    _name = 'iic.report.wizard'
    _description = 'IIC Event Report Export Wizard'

    event_id = fields.Many2one('iic.event', string='Event',
                                default=lambda self: self.env.context.get('default_event_id'))
    report_type = fields.Selection([
        ('event_report', 'Full Event Report (MSME Format)'),
        ('attendance_sheet', 'Attendance Sheet'),
        ('poster', 'Event Poster'),
    ], string='Report Type', required=True, default='event_report')

    def action_generate(self):
        self.ensure_one()
        if self.report_type == 'event_report':
            reports = self.event_id.report_ids.filtered(lambda r: r.state == 'approved')
            if not reports:
                reports = self.event_id.report_ids
            if not reports:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('No Report'),
                        'message': _('No event report found. Create one first.'),
                        'type': 'warning',
                    }
                }
            return self.env.ref(
                'university_management.action_report_iic_event_report'
            ).report_action(reports[0])
        elif self.report_type == 'attendance_sheet':
            return self.env.ref(
                'university_management.action_report_iic_attendance_sheet'
            ).report_action(self.event_id)
