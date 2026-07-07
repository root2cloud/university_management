# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class PromoteStudentWizard(models.TransientModel):
    """
    Wizard for bulk student promotion to next year/semester
    """
    _name = 'promote.student.wizard'
    _description = 'Promote Student Wizard'

    current_program_id = fields.Many2one('university.program', string='Current Program', required=True)
    current_batch_id = fields.Many2one('university.batch', string='Current Batch', required=True)
    current_semester = fields.Selection([
        ('1', 'Semester 1'),
        ('2', 'Semester 2'),
        ('3', 'Semester 3'),
        ('4', 'Semester 4'),
        ('5', 'Semester 5'),
        ('6', 'Semester 6'),
        ('7', 'Semester 7'),
        ('8', 'Semester 8'),
    ], string='Current Semester', required=True)

    promotion_type = fields.Selection([
        ('semester', 'Promote to Next Semester'),
        ('year', 'Promote to Next Year'),
        ('graduate', 'Mark as Graduated')
    ], string='Promotion Type', default='semester', required=True)

    next_semester = fields.Selection([
        ('1', 'Semester 1'),
        ('2', 'Semester 2'),
        ('3', 'Semester 3'),
        ('4', 'Semester 4'),
        ('5', 'Semester 5'),
        ('6', 'Semester 6'),
        ('7', 'Semester 7'),
        ('8', 'Semester 8'),
    ], string='Next Semester')
    next_batch_id = fields.Many2one('university.batch', string='Next Batch')

    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year', required=True)
    promotion_date = fields.Date(string='Promotion Date', default=fields.Date.today, required=True)

    student_ids = fields.Many2many('student.student', string='Students to Promote')

    criteria = fields.Selection([
        ('all', 'All Students'),
        ('attendance', 'Minimum Attendance Met'),
        ('result', 'Passed Students Only'),
        ('custom', 'Custom Selection')
    ], string='Promotion Criteria', default='result', required=True)

    min_attendance_percentage = fields.Float(string='Minimum Attendance %', default=75.0)
    check_backlogs = fields.Boolean(string='Check for Backlogs', default=True)

    auto_assign_courses = fields.Boolean(string='Auto Assign Next Semester Courses', default=True)
    send_notification = fields.Boolean(string='Send Promotion Notification', default=True)

    preview_lines = fields.One2many('promote.student.wizard.line', 'wizard_id',
                                    string='Students Preview', compute='_compute_preview_lines')

    @api.depends('current_program_id', 'current_batch_id', 'current_semester', 'criteria', 'student_ids')
    def _compute_preview_lines(self):
        """Compute preview of students to be promoted"""
        for wizard in self:
            if wizard.criteria == 'custom' and wizard.student_ids:
                students = wizard.student_ids
            else:
                students = wizard._get_eligible_students()

            lines = []
            for student in students:
                eligible, reason = wizard._check_eligibility(student)
                lines.append((0, 0, {
                    'student_id': student.id,
                    'current_semester': wizard.current_semester,
                    'eligible': eligible,
                    'reason': reason
                }))

            wizard.preview_lines = lines

    def _get_eligible_students(self):
        """Get students eligible for promotion"""
        domain = [
            ('program_id', '=', self.current_program_id.id),
            ('batch_id', '=', self.current_batch_id.id),
            ('current_semester', '=', self.current_semester),
            ('state', '=', 'enrolled')
        ]

        return self.env['student.student'].search(domain)

    def _check_eligibility(self, student):
        """Check if student is eligible for promotion"""
        if self.criteria == 'all':
            return True, 'Selected for promotion'

        reasons = []

        # Check attendance
        if self.criteria in ['attendance', 'result']:
            attendance_percentage = self._get_student_attendance(student)
            if attendance_percentage < self.min_attendance_percentage:
                return False, f'Attendance {attendance_percentage:.1f}% < {self.min_attendance_percentage}%'
            reasons.append(f'Attendance: {attendance_percentage:.1f}%')

        # Check results
        if self.criteria == 'result':
            has_backlogs = self._check_student_backlogs(student)
            if has_backlogs and self.check_backlogs:
                return False, 'Has pending backlogs'

            if not self._check_passed_exams(student):
                return False, 'Did not pass all exams'

            reasons.append('Passed all exams')

        return True, ', '.join(reasons) if reasons else 'Eligible'

    def _get_student_attendance(self, student):
        """Calculate student attendance percentage"""
        Attendance = self.env['student.attendance']

        # Get attendance for current semester
        total = Attendance.search_count([
            ('student_id', '=', student.id),
            ('semester', '=', self.current_semester)
        ])

        present = Attendance.search_count([
            ('student_id', '=', student.id),
            ('semester', '=', self.current_semester),
            ('state', '=', 'present')
        ])

        return (present / total * 100) if total > 0 else 0.0

    def _check_student_backlogs(self, student):
        """Check if student has backlogs"""
        ExamResult = self.env['exam.result']

        backlogs = ExamResult.search_count([
            ('student_id', '=', student.id),
            ('result', '=', 'fail'),
            ('is_cleared', '=', False)
        ])

        return backlogs > 0

    def _check_passed_exams(self, student):
        """Check if student passed all current semester exams"""
        ExamResult = self.env['exam.result']

        failed_count = ExamResult.search_count([
            ('student_id', '=', student.id),
            ('semester', '=', self.current_semester),
            ('result', '=', 'fail')
        ])

        return failed_count == 0

    def action_promote_students(self):
        """Promote selected students"""
        self.ensure_one()

        # Get eligible students
        if self.criteria == 'custom':
            students = self.student_ids
        else:
            students = self.preview_lines.filtered(lambda l: l.eligible).mapped('student_id')

        if not students:
            raise UserError(_('No eligible students found for promotion.'))

        promoted_count = 0
        errors = []

        for student in students:
            try:
                self._promote_student(student)
                promoted_count += 1
            except Exception as e:
                errors.append(f"{student.name}: {str(e)}")

        # Show result message
        message = _('%s students promoted successfully.') % promoted_count
        if errors:
            message += _('\n\nErrors:\n') + '\n'.join(errors[:5])

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Student Promotion'),
                'message': message,
                'type': 'success' if not errors else 'warning',
                'sticky': True,
            }
        }

    def _promote_student(self, student):
        """Promote individual student"""
        promotion_vals = {
            'student_id': student.id,
            'from_semester': self.current_semester,
            'to_semester': self.next_semester,
            'from_batch_id': self.current_batch_id.id,
            'to_batch_id': self.next_batch_id.id if self.next_batch_id else self.current_batch_id.id,
            'academic_year_id': self.academic_year_id.id,
            'promotion_date': self.promotion_date,
            'promotion_type': self.promotion_type,
            'state': 'promoted'
        }

        # Create promotion record
        self.env['student.promotion'].create(promotion_vals)

        # Update student record
        update_vals = {
            'current_semester': self.next_semester if self.promotion_type != 'graduate' else self.current_semester,
            'batch_id': self.next_batch_id.id if self.next_batch_id else student.batch_id.id,
        }

        if self.promotion_type == 'graduate':
            update_vals['state'] = 'graduated'
            update_vals['graduation_date'] = self.promotion_date

        student.write(update_vals)

        # Auto assign courses
        if self.auto_assign_courses and self.promotion_type != 'graduate':
            self._assign_courses(student)

        # Send notification
        if self.send_notification:
            self._send_promotion_notification(student)

    def _assign_courses(self, student):
        """Auto assign courses for next semester"""
        courses = self.env['university.course'].search([
            ('program_id', '=', student.program_id.id),
            ('semester', '=', self.next_semester)
        ])

        for course in courses:
            self.env['student.course.enrollment'].create({
                'student_id': student.id,
                'course_id': course.id,
                'semester': self.next_semester,
                'academic_year_id': self.academic_year_id.id,
                'state': 'enrolled'
            })

    def _send_promotion_notification(self, student):
        """Send promotion notification to student"""
        template = self.env.ref('university_management.email_template_student_promotion',
                                raise_if_not_found=False)
        if template and student.email:
            template.send_mail(student.id, force_send=True)


class PromoteStudentWizardLine(models.TransientModel):
    """Preview lines for student promotion"""
    _name = 'promote.student.wizard.line'
    _description = 'Promote Student Wizard Line'

    wizard_id = fields.Many2one('promote.student.wizard', string='Wizard', ondelete='cascade')
    student_id = fields.Many2one('student.student', string='Student', readonly=True)
    current_semester = fields.Selection([
        ('1', 'Semester 1'),
        ('2', 'Semester 2'),
        ('3', 'Semester 3'),
        ('4', 'Semester 4'),
        ('5', 'Semester 5'),
        ('6', 'Semester 6'),
        ('7', 'Semester 7'),
        ('8', 'Semester 8'),
    ], string='Current Semester', readonly=True)
    eligible = fields.Boolean(string='Eligible', readonly=True)
    reason = fields.Char(string='Reason', readonly=True)
