# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class GenerateOMRSheetsWizard(models.TransientModel):
    """
    Wizard to bulk-generate OMR sheets for all students
    registered in a given examination + subject combination.
    """
    _name = 'exam.generate.omr.sheets.wizard'
    _description = 'Generate OMR Sheets Wizard'

    examination_id = fields.Many2one('examination.examination', string='Examination',
                                     required=True)
    subject_id = fields.Many2one('university.subject', string='Subject',
                                 required=True)
    omr_template_id = fields.Many2one('exam.omr.template', string='OMR Template',
                                      required=True)

    exam_month_year = fields.Char(string='Month-Year', required=True,
                                  help='e.g., AUGUST 2026')
    exam_date = fields.Date(string='Date of Exam')

    # Optionally filter students
    program_id = fields.Many2one('university.program', string='Program (filter)')
    department_id = fields.Many2one('university.department', string='Department (filter)')

    generate_pdf = fields.Boolean(string='Also Generate PDFs', default=True,
                                  help='Generate the OMR sheet PDF for each student immediately.')

    def action_generate(self):
        """Generate OMR sheets for eligible students."""
        self.ensure_one()

        # Find students via hall tickets for this exam
        domain = [('examination_id', '=', self.examination_id.id)]
        hall_tickets = self.env['examination.hall.ticket'].search(domain)

        if not hall_tickets:
            raise UserError(_(
                'No hall tickets found for this examination. '
                'Please generate hall tickets first.'
            ))

        students = hall_tickets.mapped('student_id')

        # Apply optional filters
        if self.program_id:
            students = students.filtered(lambda s: s.program_id == self.program_id)
        if self.department_id:
            students = students.filtered(lambda s: s.department_id == self.department_id)

        if not students:
            raise UserError(_('No students found matching the filters.'))

        OMRSheet = self.env['exam.omr.sheet']
        created = self.env['exam.omr.sheet']
        skipped = 0

        for student in students:
            # Check if OMR sheet already exists
            existing = OMRSheet.search([
                ('student_id', '=', student.id),
                ('examination_id', '=', self.examination_id.id),
                ('subject_id', '=', self.subject_id.id),
            ], limit=1)
            if existing:
                skipped += 1
                continue

            # Find hall ticket number
            ht = hall_tickets.filtered(lambda h: h.student_id == student)
            ht_number = ht[0].name if ht else ''

            vals = {
                'student_id': student.id,
                'examination_id': self.examination_id.id,
                'subject_id': self.subject_id.id,
                'omr_template_id': self.omr_template_id.id,
                'exam_month_year': self.exam_month_year,
                'exam_date': self.exam_date,
                'hall_ticket_number': ht_number,
            }
            sheet = OMRSheet.create(vals)
            created |= sheet

        # Optionally generate PDFs
        if self.generate_pdf and created:
            for sheet in created:
                try:
                    sheet.action_generate_pdf()
                except Exception as e:
                    _logger.warning('PDF generation failed for OMR %s: %s',
                                    sheet.serial_number, e)

        # Return action showing generated sheets
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generated OMR Sheets (%d created, %d skipped)') % (len(created), skipped),
            'res_model': 'exam.omr.sheet',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created.ids)] if created else [('id', '=', 0)],
            'target': 'current',
        }