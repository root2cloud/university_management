# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class GenerateHallTicketWizard(models.TransientModel):
    """
    Wizard for bulk hall ticket generation
    """
    _name = 'generate.examination.hall.ticket.wizard'
    _description = 'Generate Hall Ticket Wizard'

    examination_id = fields.Many2one('examination.examination', string='Examination',
                                     required=True, domain=[('state', 'in', ['scheduled', 'ongoing'])])
    program_id = fields.Many2one('university.program', string='Program')
    department_id = fields.Many2one('university.department', string='Department')
    batch_id = fields.Many2one('university.batch', string='Batch')
    semester = fields.Selection([
        ('1', 'Semester 1'),
        ('2', 'Semester 2'),
        ('3', 'Semester 3'),
        ('4', 'Semester 4'),
        ('5', 'Semester 5'),
        ('6', 'Semester 6'),
        ('7', 'Semester 7'),
        ('8', 'Semester 8'),
    ], string='Semester', required=True, default='1')

    # Eligibility criteria
    check_eligibility = fields.Boolean(string='Check Eligibility Criteria', default=True)
    min_attendance = fields.Float(string='Minimum Attendance %', default=75.0)
    check_fee_payment = fields.Boolean(string='Check Fee Payment', default=True)
    check_documents = fields.Boolean(string='Check Document Verification', default=False)

    # Generation options
    auto_issue = fields.Boolean(string='Auto Issue After Generation', default=True)
    send_email = fields.Boolean(string='Send Email to Students', default=True)

    # Preview lines
    preview_lines = fields.One2many(
        'generate.examination.hall.ticket.wizard.line',
        'wizard_id',  # This must match the field name in the line model
        string='Students Preview',
        readonly=True
    )

    # Statistics
    eligible_student_count = fields.Integer(string='Eligible Students', compute='_compute_counts')
    ineligible_student_count = fields.Integer(string='Ineligible Students', compute='_compute_counts')
    total_student_count = fields.Integer(string='Total Students', compute='_compute_counts')

    @api.depends('preview_lines')
    def _compute_counts(self):
        """Compute statistics based on preview lines"""
        for wizard in self:
            eligible = len(wizard.preview_lines.filtered(lambda l: l.eligible))
            wizard.eligible_student_count = eligible
            wizard.ineligible_student_count = len(wizard.preview_lines) - eligible
            wizard.total_student_count = len(wizard.preview_lines)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        exam_id = res.get('examination_id') or self.env.context.get('default_examination_id')
        if exam_id:
            exam = self.env['examination.examination'].browse(exam_id)
            if exam.exists():
                if exam.semester_id and exam.semester_id.semester_number:
                    res['semester'] = str(exam.semester_id.semester_number)
                if len(exam.program_ids) == 1:
                    res['program_id'] = exam.program_ids[0].id
                if len(exam.department_ids) == 1:
                    res['department_id'] = exam.department_ids[0].id
        return res

    @api.onchange('examination_id')
    def _onchange_examination_id(self):
        """Auto-populate semester and applicable filters from the examination"""
        if self.examination_id:
            exam = self.examination_id
            # Set semester from linked semester record
            if exam.semester_id and exam.semester_id.semester_number:
                self.semester = str(exam.semester_id.semester_number)
            # Set program/department from applicable scope
            if len(exam.program_ids) == 1:
                self.program_id = exam.program_ids[0]
            if len(exam.department_ids) == 1:
                self.department_id = exam.department_ids[0]
            self._update_preview_lines()

    @api.onchange('examination_id', 'program_id', 'department_id', 'batch_id', 'semester',
                  'check_eligibility', 'min_attendance', 'check_fee_payment', 'check_documents')
    def _onchange_filters(self):
        """Update preview when filters change"""
        self._update_preview_lines()

    def _update_preview_lines(self):
        """Update preview lines based on current filters"""
        self.ensure_one()

        # Clear existing lines
        self.preview_lines = [(5, 0, 0)]

        if not self.examination_id or not self.semester:
            return

        # Get students based on filters
        students = self._get_students()

        # Create preview lines
        lines = []
        for student in students:
            eligible, reason = self._check_student_eligibility(student)
            lines.append((0, 0, {
                'student_id': student.id,
                'eligible': eligible,
                'reason': reason
            }))

        self.preview_lines = lines

    def _get_students(self):
        """Get students based on filters"""
        domain = [
            ('state', 'in', ['enrolled', 'active']),
            ('current_semester', '=', int(self.semester) if self.semester else 1)
        ]

        if self.program_id:
            domain.append(('program_id', '=', self.program_id.id))
        if self.department_id:
            domain.append(('department_id', '=', self.department_id.id))
        if self.batch_id:
            domain.append(('batch_id', '=', self.batch_id.id))

        return self.env['student.student'].search(domain)

    def _check_student_eligibility(self, student):
        """Check if student is eligible for hall ticket"""
        if not self.check_eligibility:
            return True, 'No eligibility check'

        reasons = []

        # Check attendance
        if student.attendance_percentage < self.min_attendance:
            return False, f'Low attendance: {student.attendance_percentage:.1f}%'
        reasons.append(f'Attendance: {student.attendance_percentage:.1f}%')

        # Check fee payment
        if self.check_fee_payment and student.total_fee_due > 0:
            return False, 'Fee payment pending'
        reasons.append('Fee paid')

        # Check documents
        if self.check_documents and not student.documents_verified:
            return False, 'Documents not verified'
        reasons.append('Documents verified')

        return True, ', '.join(reasons)

    def action_generate(self):
        """Generate hall tickets for eligible students"""
        self.ensure_one()

        # Get eligible students from preview lines
        eligible_lines = self.preview_lines.filtered(lambda l: l.eligible)

        if not eligible_lines:
            raise UserError(_('No eligible students found for hall ticket generation.'))

        HallTicket = self.env['examination.hall.ticket']
        generated_tickets = self.env['examination.hall.ticket']

        for line in eligible_lines:
            student = line.student_id

            # Check if hall ticket already exists
            existing = HallTicket.search([
                ('student_id', '=', student.id),
                ('examination_id', '=', self.examination_id.id)
            ], limit=1)

            if existing:
                if existing.state == 'cancelled':
                    existing.write({
                        'state': 'issued' if self.auto_issue else 'draft',
                        'is_eligible': True
                    })
                    generated_tickets |= existing
                continue

            # Generate hall ticket
            ticket_vals = {
                'student_id': student.id,
                'examination_id': self.examination_id.id,
                'is_eligible': True,
                'state': 'issued' if self.auto_issue else 'draft'
            }

            ticket = HallTicket.create(ticket_vals)
            generated_tickets |= ticket

            # Send email if enabled
            if self.send_email and self.auto_issue and student.email:
                self._send_hall_ticket_email(ticket)

        # Show result
        return {
            'name': _('Generated Hall Tickets'),
            'type': 'ir.actions.act_window',
            'res_model': 'examination.hall.ticket',
            'view_mode': 'list,form',
            'domain': [('id', 'in', generated_tickets.ids)],
            'target': 'current',
            'context': {
                'create': False,
                'edit': False,
                'delete': False
            }
        }

    def _send_hall_ticket_email(self, hall_ticket):
        """Send hall ticket via email"""
        try:
            template = self.env.ref('university_management.email_template_hall_ticket',
                                    raise_if_not_found=False)
            if template:
                template.send_mail(hall_ticket.id, force_send=True)
                return True
            return False
        except Exception as e:
            _logger.error(f"Hall ticket email error: {str(e)}")
            return False