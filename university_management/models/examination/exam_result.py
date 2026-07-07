# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ExaminationResult(models.Model):
    _name = 'examination.result'
    _description = 'Exam Result Entry'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'examination_id, student_id'

    active = fields.Boolean(string='Active', default=True)
    name = fields.Char(string='Result Number', compute='_compute_name', store=True)

    # Student
    student_id = fields.Many2one('student.student', string='Student',
                                 required=True, tracking=True, index=True)
    registration_number = fields.Char(related='student_id.registration_number',
                                      string='Registration Number')
    program_id = fields.Many2one('university.program', related='student_id.program_id', string='Program', store=True)
    department_id = fields.Many2one('university.department', related='student_id.department_id',
                                    string='Department', store=True)

    # Examination
    examination_id = fields.Many2one('examination.examination', string='Examination',
                                     required=True, tracking=True, index=True)
    academic_year_id = fields.Many2one('university.academic.year', related='examination_id.academic_year_id',
                                       string='Academic Year', store=True)
    semester_id = fields.Many2one('university.semester', related='examination_id.semester_id',
                                  string='Semester', store=True)

    # Subject & Course
    course_id = fields.Many2one('university.course', string='Course',
                                required=True, tracking=True)
    subject_id = fields.Many2one('university.subject', related='course_id.subject_id', string='Subject',
                                 store=True, readonly=True)

    # Marks
    max_marks = fields.Integer(string='Maximum Marks', required=True, default=100)
    passing_marks = fields.Integer(string='Passing Marks', required=True, default=40)

    internal_marks = fields.Integer(string='Internal Marks', default=0)
    internal_max = fields.Integer(string='Internal Max', default=30)

    external_marks = fields.Integer(string='External Marks', default=0)
    external_max = fields.Integer(string='External Max', default=70)

    total_marks = fields.Integer(string='Total Marks Obtained',
                                 compute='_compute_total_marks', store=True)

    percentage = fields.Float(string='Percentage', compute='_compute_percentage', store=True)

    credits = fields.Integer(string='Credits', required=True, default=3)

    # Grade
    grade_id = fields.Many2one('examination.grade.system', string='Grade',
                               compute='_compute_grade', store=True)
    grade_letter = fields.Char(related='grade_id.grade', string='Grade Letter', store=True)
    grade_point = fields.Float(related='grade_id.grade_point', string='Grade Point', store=True)

    # Result
    is_pass = fields.Boolean(string='Pass', compute='_compute_result', store=True)
    result = fields.Selection([
        ('pass', 'Pass'),
        ('fail', 'Fail'),
        ('absent', 'Absent'),
        ('withheld', 'Result Withheld'),
    ], string='Result', compute='_compute_result', store=True, tracking=True)

    # Absence
    is_absent = fields.Boolean(string='Absent', default=False, tracking=True)

    # Evaluation
    evaluated_by = fields.Many2one('faculty.faculty', string='Evaluated By')
    evaluation_date = fields.Date(string='Evaluation Date')

    # Verification
    verified_by = fields.Many2one('res.users', string='Verified By', readonly=True)
    verification_date = fields.Date(string='Verification Date', readonly=True)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('verified', 'Verified'),
        ('published', 'Published'),
    ], string='Status', default='draft', tracking=True, index=True)

    # Revaluation
    revaluation_requested = fields.Boolean(string='Revaluation Requested')
    revaluation_id = fields.Many2one('examination.revaluation', string='Revaluation')

    # Revaluation related fields for display in form
    rev_revaluated_by = fields.Many2one('faculty.faculty', related='revaluation_id.revaluated_by',
                                         string='Revaluated By', readonly=True)
    rev_revaluation_date = fields.Date(related='revaluation_id.revaluation_date',
                                        string='Revaluation Date', readonly=True)
    rev_revaluation_type = fields.Selection(related='revaluation_id.revaluation_type',
                                             string='Revaluation Type', readonly=True)
    rev_state = fields.Selection(related='revaluation_id.state',
                                  string='Revaluation Status', readonly=True)
    rev_original_marks = fields.Integer(related='revaluation_id.original_marks',
                                         string='Original Marks', readonly=True)
    rev_original_grade = fields.Char(related='revaluation_id.original_grade',
                                      string='Original Grade', readonly=True)
    rev_revaluated_marks = fields.Integer(related='revaluation_id.revaluated_marks',
                                           string='Revaluated Marks', readonly=True)
    rev_revaluated_grade = fields.Char(related='revaluation_id.revaluated_grade',
                                        string='Revaluated Grade', readonly=True)
    rev_marks_difference = fields.Integer(related='revaluation_id.marks_difference',
                                           string='Marks Difference', readonly=True)
    rev_outcome = fields.Selection(related='revaluation_id.outcome',
                                    string='Outcome', readonly=True)

    # Remarks
    remarks = fields.Text(string='Remarks')

    _sql_constraints = [
        ('unique_result', 'unique(student_id, examination_id, course_id)',
         'Result already exists for this student, examination and course!'),
    ]

    @api.depends('student_id', 'examination_id', 'subject_id')
    def _compute_name(self):
        for record in self:
            record.name = f"{record.student_id.registration_number} - {record.subject_id.name if record.subject_id else ''}"

    @api.depends('internal_marks', 'external_marks')
    def _compute_total_marks(self):
        for record in self:
            record.total_marks = record.internal_marks + record.external_marks

    @api.depends('total_marks', 'max_marks')
    def _compute_percentage(self):
        for record in self:
            if record.max_marks > 0:
                record.percentage = (record.total_marks / record.max_marks) * 100
            else:
                record.percentage = 0.0

    @api.depends('percentage')
    def _compute_grade(self):
        for record in self:
            if not record.is_absent:
                grade = self.env['examination.grade.system'].search([
                    ('min_percentage', '<=', record.percentage),
                    ('max_percentage', '>=', record.percentage)
                ], limit=1)
                record.grade_id = grade.id if grade else False
            else:
                record.grade_id = False

    @api.depends('total_marks', 'passing_marks', 'is_absent', 'internal_marks', 'external_marks')
    def _compute_result(self):
        for record in self:
            if record.is_absent:
                record.result = 'absent'
                record.is_pass = False
            elif record.total_marks >= record.passing_marks:
                # Check if passed in both internal and external
                internal_pass = record.internal_marks >= (record.internal_max * 0.4)
                external_pass = record.external_marks >= (record.external_max * 0.4)

                if internal_pass and external_pass:
                    record.result = 'pass'
                    record.is_pass = True
                else:
                    record.result = 'fail'
                    record.is_pass = False
            else:
                record.result = 'fail'
                record.is_pass = False

    @api.constrains('internal_marks', 'internal_max')
    def _check_internal_marks(self):
        for record in self:
            if record.internal_marks > record.internal_max:
                raise ValidationError(_('Internal marks cannot exceed maximum internal marks!'))

    @api.constrains('external_marks', 'external_max')
    def _check_external_marks(self):
        for record in self:
            if record.external_marks > record.external_max:
                raise ValidationError(_('External marks cannot exceed maximum external marks!'))

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_verify(self):
        self.write({
            'state': 'verified',
            'verified_by': self.env.user.id,
            'verification_date': fields.Date.today()
        })

    def action_publish(self):
        self.write({'state': 'published'})
        self._send_result_notification()

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def _send_result_notification(self):
        """Send result notification to student via email."""
        import logging
        _logger = logging.getLogger(__name__)

        recipient_email = self.student_id.email
        if not recipient_email:
            _logger.warning("No email for student on result %s. Skipping.", self.name)
            return

        student_name = self.student_id.name or ''
        exam_name = self.examination_id.name or ''
        subject_name = self.subject_id.name if self.subject_id else ''
        total_marks = self.total_marks or 0
        max_marks = self.max_marks or 100
        percentage = '{:.2f}'.format(self.percentage) if self.percentage else '0.00'
        grade = self.grade_letter or 'N/A'
        result_status = 'PASS' if self.is_pass else 'FAIL'
        result_color = '#4CAF50' if self.is_pass else '#F44336'
        academic_year = self.academic_year_id.name if self.academic_year_id else ''
        semester = self.semester_id.name if self.semester_id else ''
        company_name = self.env.company.name
        email_from = (
                self.env.company.email
                or self.env.user.email
                or self.env['ir.config_parameter'].sudo().get_param('mail.default.from')
                or False
        )

        if not email_from:
            _logger.warning("No sender email configured for result %s. Skipping.", self.name)
            return

        body_html = """
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #4CAF50; color: white; padding: 20px; text-align: center;">
            <h1>Examination Results Published</h1>
        </div>
        <div style="padding: 20px; background: #f9f9f9;">
            <p>Dear <strong>{student_name}</strong>,</p>
            <p>Your examination results for <strong>{exam_name}</strong> have been published.</p>
            <div style="background: white; padding: 20px; border-radius: 5px; margin: 20px 0; text-align: center;">
                <h2 style="color: {result_color}; margin: 0;">{result_status}</h2>
                <p style="margin: 5px 0;">Grade: <strong>{grade}</strong></p>
            </div>
            <div style="background: white; padding: 15px; border-left: 4px solid #4CAF50; margin: 20px 0;">
                <table style="width: 100%;">
                    <tr>
                        <td style="padding: 5px 0;"><strong>Subject:</strong></td>
                        <td style="padding: 5px 0;">{subject_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Academic Year:</strong></td>
                        <td style="padding: 5px 0;">{academic_year}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Semester:</strong></td>
                        <td style="padding: 5px 0;">{semester}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Marks Obtained:</strong></td>
                        <td style="padding: 5px 0;">{total_marks} / {max_marks}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Percentage:</strong></td>
                        <td style="padding: 5px 0;">{percentage}%</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Grade:</strong></td>
                        <td style="padding: 5px 0;">{grade}</td>
                    </tr>
                </table>
            </div>
            <p>You can download your marksheet from the student portal.</p>
            <p>Best Regards,<br/>
            <strong>Examination Controller</strong><br/>
            {company_name}</p>
        </div>
    </div>
    """.format(
            student_name=student_name,
            exam_name=exam_name,
            subject_name=subject_name,
            total_marks=total_marks,
            max_marks=max_marks,
            percentage=percentage,
            grade=grade,
            result_status=result_status,
            result_color=result_color,
            academic_year=academic_year,
            semester=semester,
            company_name=company_name,
        )

        mail_values = {
            'subject': 'Exam Results Published - %s' % exam_name,
            'email_from': email_from,
            'email_to': recipient_email,
            'body_html': body_html,
            'auto_delete': True,
        }
        mail = self.env['mail.mail'].sudo().create(mail_values)
        mail.send()