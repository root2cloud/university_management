# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class BulkIdCardWizard(models.TransientModel):
    """
    Wizard for bulk ID card generation
    """
    _name = 'bulk.id.card.wizard'
    _description = 'Bulk ID Card Generation Wizard'

    card_type = fields.Selection([
        ('student', 'Student ID Card'),
        ('faculty', 'Faculty ID Card'),
        ('staff', 'Staff ID Card')
    ], string='Card Type', default='student', required=True)

    # Student filters
    program_id = fields.Many2one('university.program', string='Program')
    department_id = fields.Many2one('university.department', string='Department')
    batch_id = fields.Many2one('university.batch', string='Batch')
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year')

    student_ids = fields.Many2many('student.student', string='Students',
                                   domain=[('state', '=', 'enrolled')])
    faculty_ids = fields.Many2many('faculty.faculty', string='Faculty',
                                   domain=[('state', '=', 'active')])

    card_template_id = fields.Many2one('id.card.template', string='Card Template')
    validity_date = fields.Date(string='Valid Until', required=True,
                                default=lambda self: fields.Date.today().replace(month=12, day=31))

    regenerate_existing = fields.Boolean(string='Regenerate Existing Cards', default=False)
    auto_print = fields.Boolean(string='Auto Print After Generation', default=False)

    preview_count = fields.Integer(string='Cards to Generate', compute='_compute_preview_count')

    @api.depends('card_type', 'student_ids', 'faculty_ids', 'program_id', 'department_id', 'batch_id')
    def _compute_preview_count(self):
        """Compute number of cards to be generated"""
        for wizard in self:
            if wizard.card_type == 'student':
                if wizard.student_ids:
                    wizard.preview_count = len(wizard.student_ids)
                else:
                    domain = [('state', '=', 'enrolled')]
                    if wizard.program_id:
                        domain.append(('program_id', '=', wizard.program_id.id))
                    if wizard.department_id:
                        domain.append(('department_id', '=', wizard.department_id.id))
                    if wizard.batch_id:
                        domain.append(('batch_id', '=', wizard.batch_id.id))

                    if not wizard.regenerate_existing:
                        domain.append(('id_card_id', '=', False))

                    wizard.preview_count = self.env['student.student'].search_count(domain)
            else:
                wizard.preview_count = len(wizard.faculty_ids)

    @api.onchange('card_type')
    def _onchange_card_type(self):
        """Update default template based on card type"""
        if self.card_type == 'student':
            self.card_template_id = self.env.ref(
                'university_management.id_card_template_student',
                raise_if_not_found=False)
        elif self.card_type == 'faculty':
            self.card_template_id = self.env.ref(
                'university_management.id_card_template_faculty',
                raise_if_not_found=False)

    def action_generate_id_cards(self):
        """Generate ID cards in bulk"""
        self.ensure_one()

        if self.card_type == 'student':
            return self._generate_student_cards()
        elif self.card_type == 'faculty':
            return self._generate_faculty_cards()

    def _generate_student_cards(self):
        """Generate student ID cards"""
        # Get students
        if self.student_ids:
            students = self.student_ids
        else:
            domain = [('state', '=', 'enrolled')]
            if self.program_id:
                domain.append(('program_id', '=', self.program_id.id))
            if self.department_id:
                domain.append(('department_id', '=', self.department_id.id))
            if self.batch_id:
                domain.append(('batch_id', '=', self.batch_id.id))

            if not self.regenerate_existing:
                domain.append(('id_card_id', '=', False))

            students = self.env['student.student'].search(domain)

        if not students:
            raise UserError(_('No students found matching the criteria.'))

        # Generate cards
        StudentIdCard = self.env['student.id.card']
        generated_cards = self.env['student.id.card']

        for student in students:
            # Check if card exists
            existing_card = StudentIdCard.search([
                ('student_id', '=', student.id),
                ('state', 'in', ['generated', 'printed'])
            ], limit=1)

            if existing_card and not self.regenerate_existing:
                continue

            # Generate new card
            card_vals = {
                'student_id': student.id,
                'card_number': self._generate_card_number(student),
                'issue_date': fields.Date.today(),
                'valid_until': self.validity_date,
                'template_id': self.card_template_id.id if self.card_template_id else False,
                'state': 'generated'
            }

            card = StudentIdCard.create(card_vals)
            generated_cards |= card

            # Update student record
            student.write({'id_card_id': card.id})

        # Auto print if enabled
        if self.auto_print and generated_cards:
            return self.env.ref('university_management.action_report_student_id_card').report_action(generated_cards)

        # Show result
        return {
            'name': _('Generated ID Cards'),
            'type': 'ir.actions.act_window',
            'res_model': 'student.id.card',
            'view_mode': 'list,form',
            'domain': [('id', 'in', generated_cards.ids)],
            'target': 'current',
        }

    def _generate_faculty_cards(self):
        """Generate faculty ID cards"""
        if not self.faculty_ids:
            raise UserError(_('Please select faculty members.'))

        FacultyIdCard = self.env['faculty.id.card']
        generated_cards = self.env['faculty.id.card']

        for faculty in self.faculty_ids:
            # Check if card exists
            existing_card = FacultyIdCard.search([
                ('faculty_id', '=', faculty.id),
                ('state', 'in', ['generated', 'printed'])
            ], limit=1)

            if existing_card and not self.regenerate_existing:
                continue

            # Generate new card
            card_vals = {
                'faculty_id': faculty.id,
                'card_number': self._generate_card_number(faculty),
                'issue_date': fields.Date.today(),
                'valid_until': self.validity_date,
                'template_id': self.card_template_id.id if self.card_template_id else False,
                'state': 'generated'
            }

            card = FacultyIdCard.create(card_vals)
            generated_cards |= card

            # Update faculty record
            faculty.write({'id_card_id': card.id})

        # Auto print if enabled
        if self.auto_print and generated_cards:
            return self.env.ref('university_management.action_report_faculty_id_card').report_action(generated_cards)

        # Show result
        return {
            'name': _('Generated ID Cards'),
            'type': 'ir.actions.act_window',
            'res_model': 'faculty.id.card',
            'view_mode': 'list,form',
            'domain': [('id', 'in', generated_cards.ids)],
            'target': 'current',
        }

    def _generate_card_number(self, record):
        """Generate unique card number"""
        if hasattr(record, 'registration_number') and record.registration_number:
            return f"ID-{record.registration_number}"
        elif hasattr(record, 'employee_id') and record.employee_id:
            return f"ID-{record.employee_id}"
        else:
            return self.env['ir.sequence'].next_by_code('id.card.sequence') or 'ID-NEW'
