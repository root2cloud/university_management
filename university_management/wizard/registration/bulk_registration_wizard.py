# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class BulkRegistrationWizard(models.TransientModel):
    """
    Wizard for bulk student registration number generation
    """
    _name = 'bulk.registration.wizard'
    _description = 'Bulk Registration Wizard'

    program_id = fields.Many2one('university.program', string='Program')
    department_id = fields.Many2one('university.department', string='Department')
    batch_id = fields.Many2one('university.batch', string='Batch')
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year')

    student_ids = fields.Many2many('student.student', string='Students',
                                   domain=[('registration_number', '=', False)])

    registration_prefix = fields.Char(string='Registration Prefix',
                                      help='e.g., REG/2024/', required=True)
    starting_number = fields.Integer(string='Starting Number', default=1, required=True)

    preview_lines = fields.One2many('bulk.registration.wizard.line', 'wizard_id',
                                    string='Preview', readonly=True)

    @api.onchange('program_id', 'department_id', 'batch_id', 'academic_year_id')
    def _onchange_filters(self):
        """Update student domain based on filters"""
        domain = [('registration_number', '=', False), ('state', '=', 'admitted')]

        if self.program_id:
            domain.append(('program_id', '=', self.program_id.id))
        if self.department_id:
            domain.append(('department_id', '=', self.department_id.id))
        if self.batch_id:
            domain.append(('batch_id', '=', self.batch_id.id))
        if self.academic_year_id:
            domain.append(('academic_year_id', '=', self.academic_year_id.id))

        return {'domain': {'student_ids': domain}}

    @api.onchange('registration_prefix', 'starting_number')
    def _generate_preview(self):
        """Generate preview of registration numbers"""
        if self.student_ids:
            self.preview_lines = [(5, 0, 0)]  # Clear existing lines

            lines = []
            for idx, student in enumerate(self.student_ids):
                reg_number = f"{self.registration_prefix}{self.starting_number + idx:04d}"
                lines.append((0, 0, {
                    'student_id': student.id,
                    'registration_number': reg_number
                }))

            self.preview_lines = lines

    def action_generate_registrations(self):
        """Generate registration numbers for selected students"""
        self.ensure_one()

        if not self.student_ids:
            raise UserError(_('Please select at least one student.'))

        StudentRegistration = self.env['student.registration']

        for idx, student in enumerate(self.student_ids):
            reg_number = f"{self.registration_prefix}{self.starting_number + idx:04d}"

            # Create registration record
            registration = StudentRegistration.create({
                'student_id': student.id,
                'registration_number': reg_number,
                'registration_date': fields.Date.today(),
                'program_id': student.program_id.id,
                'department_id': student.department_id.id,
                'batch_id': student.batch_id.id,
                'academic_year_id': student.academic_year_id.id,
                'state': 'registered'
            })

            # Update student record
            student.write({
                'registration_number': reg_number,
                'registration_id': registration.id,
                'state': 'enrolled'
            })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('%s registration numbers generated successfully.') % len(self.student_ids),
                'type': 'success',
                'sticky': False,
            }
        }


class BulkRegistrationWizardLine(models.TransientModel):
    """Preview lines for bulk registration"""
    _name = 'bulk.registration.wizard.line'
    _description = 'Bulk Registration Wizard Line'

    wizard_id = fields.Many2one('bulk.registration.wizard', string='Wizard', ondelete='cascade')
    student_id = fields.Many2one('student.student', string='Student', readonly=True)
    registration_number = fields.Char(string='Registration Number', readonly=True)
