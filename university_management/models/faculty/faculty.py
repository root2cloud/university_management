# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Faculty(models.Model):
    _name = 'faculty.faculty'
    _description = 'Faculty Master'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _inherits = {'hr.employee': 'employee_id'}
    _order = 'name'

    # Employee (inherited from hr.employee)
    employee_id = fields.Many2one('hr.employee', string='Related Employee',
                                  required=True, ondelete='cascade', auto_join=True)

    # Faculty Details
    faculty_code = fields.Char(string='Faculty Code', readonly=True, copy=False, default='/')
    faculty_id_number = fields.Char(string='Faculty ID', tracking=True)

    # Photo
    faculty_photo = fields.Binary(string='Photo', related='employee_id.image_1920',
                                  readonly=False)

    # Personal Information
    date_of_birth = fields.Date(string='Date of Birth', tracking=True)
    age = fields.Integer(string='Age', compute='_compute_age')
    gender = fields.Selection(related='employee_id.gender', readonly=False)
    blood_group = fields.Selection([
        ('a+', 'A+'), ('a-', 'A-'),
        ('b+', 'B+'), ('b-', 'B-'),
        ('o+', 'O+'), ('o-', 'O-'),
        ('ab+', 'AB+'), ('ab-', 'AB-'),
    ], string='Blood Group')
    marital_status = fields.Selection(related='employee_id.marital', readonly=False)

    # Contact
    personal_email = fields.Char(string='Personal Email')
    work_email = fields.Char(related='employee_id.work_email', readonly=False)
    personal_mobile = fields.Char(string='Personal Mobile')
    work_mobile = fields.Char(related='employee_id.mobile_phone', readonly=False)
    emergency_contact = fields.Char(string='Emergency Contact')
    emergency_contact_name = fields.Char(string='Emergency Contact Name')

    # Address
    current_address = fields.Text(string='Current Address')
    permanent_address = fields.Text(string='Permanent Address')

    # Academic Details
    department_id = fields.Many2one('university.department', string='Department',
                                    required=True, tracking=True, index=True)
    designation_id = fields.Many2one('faculty.designation', string='Designation',
                                     required=True, tracking=True)

    # Employment
    date_of_joining = fields.Date(string='Date of Joining', tracking=True)
    employment_type = fields.Selection([
        ('permanent', 'Permanent'),
        ('temporary', 'Temporary'),
        ('contract', 'Contract'),
        ('visiting', 'Visiting Faculty'),
        ('guest', 'Guest Lecturer'),
        ('part_time', 'Part Time'),
    ], string='Employment Type', default='permanent', tracking=True)

    # Qualification
    highest_qualification = fields.Selection([
        ('phd', 'Ph.D'),
        ('mphil', 'M.Phil'),
        ('postgraduate', 'Post Graduate'),
        ('graduate', 'Graduate'),
    ], string='Highest Qualification')

    qualification_details = fields.Text(string='Qualification Details')
    specialization = fields.Char(string='Specialization/Area of Interest')
    experience_years = fields.Integer(string='Years of Experience')

    # Qualifications (detailed)
    qualification_ids = fields.One2many('faculty.qualification', 'faculty_id',
                                        string='Qualifications')

    # Teaching
    courses_taught_ids = fields.Many2many('university.course', 'faculty_course_taught_rel',
                                          'faculty_id', 'course_id',
                                          string='Courses Taught')
    subjects_taught_ids = fields.Many2many('university.subject', 'faculty_subject_rel',
                                           'faculty_id', 'subject_id',
                                           string='Subjects Can Teach')

    # Timetable
    timetable_ids = fields.One2many('university.timetable', 'faculty_id',
                                    string='Teaching Schedule')

    # Workload
    workload_ids = fields.One2many('faculty.workload', 'faculty_id', string='Teaching Workload')
    total_workload_hours = fields.Float(string='Total Workload Hours',
                                        compute='_compute_workload')

    # Attendance
    attendance_ids = fields.One2many('faculty.attendance', 'faculty_id',
                                     string='Attendance Records')
    attendance_percentage = fields.Float(string='Attendance %',
                                         compute='_compute_attendance')

    # Leave
    leave_ids = fields.One2many('faculty.leave', 'faculty_id', string='Leave Records')
    available_leaves = fields.Integer(string='Available Leaves')

    # Salary
    salary_ids = fields.One2many('faculty.salary', 'faculty_id', string='Salary Records')
    current_salary = fields.Monetary(string='Current Salary', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Evaluation
    evaluation_ids = fields.One2many('faculty.evaluation', 'faculty_id',
                                     string='Performance Evaluations')
    average_rating = fields.Float(string='Average Rating', compute='_compute_rating')

    # Research & Publications
    research_papers = fields.Integer(string='Research Papers Published')
    conferences_attended = fields.Integer(string='Conferences Attended')
    awards = fields.Text(string='Awards & Recognitions')

    # Bank Details
    bank_account_number = fields.Char(string='Bank Account Number')
    bank_name = fields.Char(string='Bank Name')
    bank_branch = fields.Char(string='Branch')
    ifsc_code = fields.Char(string='IFSC Code')

    # Government IDs
    aadhar_number = fields.Char(string='Aadhar Number')
    pan_number = fields.Char(string='PAN Number')

    # ── Biometric Device ──────────────────────────────────────────────
    device_id_num = fields.Char(
        string='Biometric Device ID',
        help='ID registered on the ZK biometric device. '
             'Must match the employee device_id_num.',
        tracking=True,
    )

    # ── Work Schedule (Attendance Rules) ─────────────────────────────
    work_start_time = fields.Float(
        string='Work Start Time',
        default=9.0,
        help='Scheduled start time in 24h decimal. e.g. 9.0 = 09:00 AM',
    )
    work_end_time = fields.Float(
        string='Work End Time',
        default=17.5,
        help='Scheduled end time in 24h decimal. e.g. 17.5 = 05:30 PM',
    )
    grace_minutes = fields.Integer(
        string='Grace Period (Minutes)',
        default=10,
        help='Number of minutes after work_start_time before marking as Late.',
    )
    half_day_threshold = fields.Float(
        string='Half Day Threshold (Hours)',
        default=4.0,
        help='Minimum worked hours to count as full day. '
             'Below this threshold the day is marked Half Day.',
    )

    # Portal Access
    user_id = fields.Many2one('res.users', related='employee_id.user_id', readonly=False)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('on_leave', 'On Leave'),
        ('suspended', 'Suspended'),
        ('resigned', 'Resigned'),
        ('retired', 'Retired'),
    ], string='Status', default='active', tracking=True)

    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('faculty_code_unique', 'unique(faculty_code)', 'Faculty Code must be unique!'),
        ('aadhar_unique', 'unique(aadhar_number)', 'Aadhar Number must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('faculty_code', '/') == '/':
            vals['faculty_code'] = self.env['ir.sequence'].next_by_code('faculty.faculty') or '/'

        if not vals.get('employee_id'):
            employee_vals = {
                'name': vals.get('name'),
                'work_email': vals.get('work_email'),
                'mobile_phone': vals.get('work_mobile'),
            }
            # Sync job position from designation
            designation_id = vals.get('designation_id')
            if designation_id:
                designation = self.env['faculty.designation'].browse(designation_id)
                if designation.hr_job_id:
                    employee_vals['job_id'] = designation.hr_job_id.id
            # Sync date of joining
            if vals.get('date_of_joining'):
                employee_vals['date_start'] = vals.get('date_of_joining')
            employee = self.env['hr.employee'].create(employee_vals)
            vals['employee_id'] = employee.id

        rec = super(Faculty, self).create(vals)
        rec._sync_hr_employee_fields()
        return rec

    def write(self, vals):
        res = super(Faculty, self).write(vals)
        sync_fields = {'designation_id', 'highest_qualification', 'date_of_joining', 'device_id_num'}
        if sync_fields.intersection(vals.keys()):
            self._sync_hr_employee_fields()
        return res

    def _sync_hr_employee_fields(self):
        """Sync faculty fields to linked hr.employee record."""
        qualification_map = {
            'phd':          'doctor',
            'mphil':        'master',
            'postgraduate': 'master',
            'graduate':     'bachelor',
        }
        for rec in self:
            if not rec.employee_id:
                continue
            employee_vals = {}
            if rec.designation_id and rec.designation_id.hr_job_id:
                employee_vals['job_id'] = rec.designation_id.hr_job_id.id
            if rec.highest_qualification:
                employee_vals['certificate'] = qualification_map.get(
                    rec.highest_qualification, 'other')
            if rec.date_of_joining:
                employee_vals['date_start'] = rec.date_of_joining
            # Sync biometric device ID to hr.employee so ZK module can find it
            if rec.device_id_num:
                employee_vals['device_id_num'] = rec.device_id_num
            if employee_vals:
                rec.employee_id.sudo().write(employee_vals)

    @api.depends('date_of_birth')
    def _compute_age(self):
        from datetime import date
        for record in self:
            if record.date_of_birth:
                today = date.today()
                record.age = today.year - record.date_of_birth.year - (
                        (today.month, today.day) < (record.date_of_birth.month, record.date_of_birth.day)
                )
            else:
                record.age = 0

    @api.depends('workload_ids', 'workload_ids.hours_per_week')
    def _compute_workload(self):
        for record in self:
            record.total_workload_hours = sum(record.workload_ids.mapped('hours_per_week'))

    @api.depends('attendance_ids')
    def _compute_attendance(self):
        for record in self:
            total = len(record.attendance_ids)
            present = len(record.attendance_ids.filtered(lambda a: a.state == 'present'))
            record.attendance_percentage = (present / total * 100) if total > 0 else 0.0

    @api.depends('evaluation_ids', 'evaluation_ids.overall_rating')
    def _compute_rating(self):
        for record in self:
            if record.evaluation_ids:
                record.average_rating = sum(record.evaluation_ids.mapped('overall_rating')) / len(record.evaluation_ids)
            else:
                record.average_rating = 0.0

    def action_activate(self):
        self.write({'state': 'active'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def action_view_timetable(self):
        return {
            'name': _('My Timetable'),
            'type': 'ir.actions.act_window',
            'res_model': 'university.timetable',
            'view_mode': 'calendar,list,form',
            'domain': [('faculty_id', '=', self.id)],
            'context': {'default_faculty_id': self.id}
        }

    def action_view_courses(self):
        return {
            'name': _('My Courses'),
            'type': 'ir.actions.act_window',
            'res_model': 'university.course',
            'view_mode': 'kanban,list,form',
            'domain': [('faculty_id', '=', self.id)],
            'context': {'default_faculty_id': self.id}
        }

    def action_faculty_attendance(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Faculty Attendance',
            'res_model': 'faculty.attendance',
            'view_mode': 'list,kanban,form,calendar,pivot,graph',
            'domain': [('faculty_id', '=', self.id)],
            'context': {
                'default_faculty_id': self.id,
                'search_default_faculty_id': self.id,
            },
        }

    def action_faculty_workload(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Faculty Workload',
            'res_model': 'faculty.workload',
            'view_mode': 'list,kanban,form,pivot,graph',
            'domain': [('faculty_id', '=', self.id)],
            'context': {
                'default_faculty_id': self.id,
                'search_default_faculty_id': self.id,
            },
        }

    def action_faculty_evaluation(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Faculty Evaluations',
            'res_model': 'faculty.evaluation',
            'view_mode': 'list,kanban,form,pivot,graph',
            'domain': [('faculty_id', '=', self.id)],
            'context': {
                'default_faculty_id': self.id,
                'search_default_faculty_id': self.id,
            },
        }