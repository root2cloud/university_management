# -*- coding: utf-8 -*-

from odoo import models, fields, api


class GenerateHallTicketWizardLine(models.TransientModel):
    """Preview lines for hall ticket generation wizard"""
    _name = 'generate.examination.hall.ticket.wizard.line'
    _description = 'Generate Hall Ticket Wizard Line'

    wizard_id = fields.Many2one(
        'generate.examination.hall.ticket.wizard',
        string='Wizard',
        ondelete='cascade',
        required=True  # Add required=True to ensure it's always set
    )
    student_id = fields.Many2one('student.student', string='Student', required=True, readonly=True)
    eligible = fields.Boolean(string='Eligible', readonly=True, default=False)
    reason = fields.Char(string='Reason/Status', readonly=True)

    # Additional fields for better display
    registration_number = fields.Char(related='student_id.registration_number', string='Reg. No.', readonly=True)
    program_id = fields.Many2one('university.program', related='student_id.program_id', string='Program', readonly=True)
    department_id = fields.Many2one('university.department', related='student_id.department_id', string='Department', readonly=True)
    attendance_percentage = fields.Float(related='student_id.attendance_percentage', string='Attendance %',
                                         readonly=True)
    total_fee_due = fields.Monetary(related='student_id.total_fee_due', string='Fee Due', readonly=True)
    currency_id = fields.Many2one('res.currency', related='student_id.currency_id', string='Currency', readonly=True)