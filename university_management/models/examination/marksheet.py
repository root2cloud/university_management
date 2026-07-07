# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ExaminationMarksheet(models.Model):
    _name = 'examination.marksheet'
    _description = 'Student Marksheet Generation'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'issue_date desc'

    name = fields.Char(string='Marksheet Number', required=True, readonly=True,
                       copy=False, default='/')

    examination_id = fields.Many2one('examination.examination', string='Examination',
                                     required=True, tracking=True)

    # Student
    student_id = fields.Many2one('student.student', string='Student',
                                 required=True, tracking=True, index=True)
    registration_number = fields.Char(related='student_id.registration_number',
                                      string='Registration Number')
    student_photo = fields.Binary(related='student_id.student_photo', string='Photo')

    # Academic Details
    program_id = fields.Many2one(related='student_id.program_id', string='Program', store=True)
    department_id = fields.Many2one(related='student_id.department_id',
                                    string='Department', store=True)

    # Academic Period
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year',
                                       required=True, tracking=True)
    semester_id = fields.Many2one('university.semester', string='Semester',
                                  required=True, tracking=True)

    # Marksheet Type
    marksheet_type = fields.Selection([
        ('semester', 'Semester Marksheet'),
        ('annual', 'Annual Marksheet'),
        ('final', 'Final/Consolidated Marksheet'),
        ('provisional', 'Provisional Certificate'),
        ('duplicate', 'Duplicate Marksheet'),
    ], string='Marksheet Type', required=True, default='semester', tracking=True)

    # Results
    result_ids = fields.Many2many('examination.result', 'marksheet_result_rel',
                                  'marksheet_id', 'result_id',
                                  string='Exam Results',
                                  domain="[('student_id', '=', student_id), ('state', '=', 'published')]")

    # Performance Summary
    total_subjects = fields.Integer(string='Total Subjects', compute='_compute_performance')
    subjects_passed = fields.Integer(string='Subjects Passed', compute='_compute_performance')
    subjects_failed = fields.Integer(string='Subjects Failed', compute='_compute_performance')

    subject_pass_pct = fields.Float(
        string='Pass %',
        compute='_compute_subject_percents',
        store=False,
    )
    subject_fail_pct = fields.Float(
        string='Fail %',
        compute='_compute_subject_percents',
        store=False,
    )

    total_credits = fields.Float(string='Total Credits', compute='_compute_performance')
    credits_earned = fields.Float(string='Credits Earned', compute='_compute_performance')
    credit_progress_width = fields.Float(
        string='Credit Progress Width',
        compute='_compute_credit_progress_width',
        store=False,
    )

    sgpa = fields.Float(string='SGPA', compute='_compute_performance', store=True,
                        help='Semester Grade Point Average')
    cgpa = fields.Float(string='CGPA', compute='_compute_cgpa', store=True,
                        help='Cumulative Grade Point Average')

    percentage = fields.Float(string='Percentage', compute='_compute_performance', store=True)

    # Classification/Division
    classification = fields.Selection([
        ('distinction', 'First Class with Distinction'),
        ('first', 'First Class'),
        ('second', 'Second Class'),
        ('third', 'Third Class'),
        ('pass', 'Pass'),
    ], string='Classification', compute='_compute_classification', store=True)

    # Overall Result
    overall_result = fields.Selection([
        ('pass', 'Pass'),
        ('fail', 'Fail'),
        ('promoted', 'Promoted'),
        ('detained', 'Detained'),
    ], string='Overall Result', compute='_compute_overall_result', store=True)

    # Issue Details
    issue_date = fields.Date(string='Issue Date', default=fields.Date.today(), tracking=True)
    issued_by = fields.Many2one('res.users', string='Issued By',
                                default=lambda self: self.env.user, readonly=True)

    # Verification
    verified_by = fields.Many2one('res.users', string='Verified By', readonly=True)
    verification_date = fields.Date(string='Verification Date', readonly=True)

    # Principal/Controller Signature
    principal_name = fields.Char(string='Principal Name')
    controller_name = fields.Char(string='Controller of Examinations')

    # Duplicate
    is_duplicate = fields.Boolean(string='Is Duplicate')
    original_marksheet_id = fields.Many2one('examination.marksheet', string='Original Marksheet')
    duplicate_fee = fields.Monetary(string='Duplicate Fee', currency_field='currency_id')
    duplicate_fee_paid = fields.Boolean(string='Fee Paid')

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company, index=True)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('verified', 'Verified'),
        ('issued', 'Issued'),
        ('downloaded', 'Downloaded'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    # Remarks
    remarks = fields.Text(string='Remarks')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Marksheet Number must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('examination.marksheet') or '/'
        return super(ExaminationMarksheet, self).create(vals)

    @api.depends('result_ids', 'result_ids.grade_point', 'result_ids.is_pass')
    def _compute_performance(self):
        for record in self:
            results = record.result_ids.filtered(lambda r: not r.is_absent)

            record.total_subjects = len(results)
            record.subjects_passed = len(results.filtered(lambda r: r.is_pass))
            record.subjects_failed = len(results.filtered(lambda r: not r.is_pass))

            # Credits
            record.total_credits = sum(results.mapped('course_id.credits'))
            record.credits_earned = sum(results.filtered(lambda r: r.is_pass).mapped('course_id.credits'))

            # SGPA
            if results:
                total_grade_points = sum(results.mapped('grade_point'))
                record.sgpa = total_grade_points / len(results)
            else:
                record.sgpa = 0.0

            # Percentage
            if results:
                total_obtained = sum(results.mapped('total_marks'))
                total_max = sum(results.mapped('max_marks'))
                record.percentage = (total_obtained / total_max * 100) if total_max > 0 else 0.0
            else:
                record.percentage = 0.0

    @api.depends('student_id', 'academic_year_id')
    def _compute_cgpa(self):
        for record in self:
            # Get all published results for the student up to current academic year
            all_results = self.env['examination.result'].search([
                ('student_id', '=', record.student_id.id),
                ('state', '=', 'published'),
                ('academic_year_id', '<=', record.academic_year_id.id)
            ])

            if all_results:
                total_grade_points = sum(all_results.mapped('grade_point'))
                record.cgpa = total_grade_points / len(all_results)
            else:
                record.cgpa = 0.0

    @api.depends('percentage')
    def _compute_classification(self):
        for record in self:
            if record.percentage >= 75:
                record.classification = 'distinction'
            elif record.percentage >= 60:
                record.classification = 'first'
            elif record.percentage >= 50:
                record.classification = 'second'
            elif record.percentage >= 40:
                record.classification = 'third'
            elif record.percentage >= 35:
                record.classification = 'pass'
            else:
                record.classification = False

    @api.depends('subjects_failed')
    def _compute_overall_result(self):
        for record in self:
            if record.subjects_failed == 0:
                record.overall_result = 'pass'
            elif record.subjects_failed <= 2:
                record.overall_result = 'promoted'
            else:
                record.overall_result = 'detained'

    def action_verify(self):
        self.write({
            'state': 'verified',
            'verified_by': self.env.user.id,
            'verification_date': fields.Date.today()
        })

    def action_issue(self):
        self.write({'state': 'issued'})
        self._send_marksheet()

    def action_download(self):
        self.write({'state': 'downloaded'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def action_print_marksheet(self):
        return self.env.ref('university_management.action_report_marksheet').report_action(self)

    def action_generate_duplicate(self):
        """Generate duplicate marksheet"""
        duplicate = self.copy({
            'is_duplicate': True,
            'original_marksheet_id': self.id,
            'state': 'draft',
        })

        return {
            'type': 'ir.actions.act_window',
            'name': _('Duplicate Marksheet'),
            'res_model': 'examination.marksheet',
            'res_id': duplicate.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _send_marksheet(self):
        """Send marksheet via email"""
        template = self.env.ref('university_management.email_template_marksheet',
                                raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)

    @api.depends('total_credits', 'credits_earned')
    def _compute_credit_progress_width(self):
        for record in self:
            if record.total_credits:
                record.credit_progress_width = (
                        record.credits_earned / record.total_credits * 100
                )
            else:
                record.credit_progress_width = 0.0

    @api.depends('total_subjects', 'subjects_passed', 'subjects_failed')
    def _compute_subject_percents(self):
        for rec in self:
            if rec.total_subjects:
                rec.subject_pass_pct = rec.subjects_passed / rec.total_subjects * 100
                rec.subject_fail_pct = rec.subjects_failed / rec.total_subjects * 100
            else:
                rec.subject_pass_pct = 0.0
                rec.subject_fail_pct = 0.0
