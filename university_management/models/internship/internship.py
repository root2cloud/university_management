# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class Internship(models.Model):
    _name = 'internship.internship'
    _description = 'Student Internship Management'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'start_date desc'

    name = fields.Char(string='Internship Code', required=True, readonly=True,
                       copy=False, default='/')

    # Student
    student_id = fields.Many2one('student.student', string='Student',
                                 required=True, tracking=True, index=True)
    registration_number = fields.Char(related='student_id.registration_number',
                                      string='Registration Number')
    program_id = fields.Many2one(related='student_id.program_id', string='Program', store=True)
    department_id = fields.Many2one(related='student_id.department_id',
                                    string='Department', store=True)

    # Academic Details
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year',
                                       required=True)
    semester_id = fields.Many2one('university.semester', string='Semester')

    # Internship Type
    internship_type = fields.Selection([
        ('mandatory', 'Mandatory/Curriculum'),
        ('summer', 'Summer Internship'),
        ('winter', 'Winter Internship'),
        ('industrial', 'Industrial Training'),
        ('voluntary', 'Voluntary'),
    ], string='Internship Type', required=True, tracking=True)

    # Company
    company_id = fields.Many2one('internship.company', string='Company',
                                 required=True, tracking=True)

    # Internship Details
    designation = fields.Char(string='Designation/Role', required=True)
    department = fields.Char(string='Department/Team')
    location = fields.Char(string='Location')

    # Duration
    start_date = fields.Date(string='Start Date', required=True, tracking=True)
    end_date = fields.Date(string='End Date', required=True, tracking=True)
    duration_months = fields.Float(string='Duration (Months)', compute='_compute_duration')

    # Stipend
    has_stipend = fields.Boolean(string='Paid Internship')
    stipend_amount = fields.Monetary(string='Stipend Amount (Monthly)',
                                     currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Supervisor
    company_supervisor = fields.Char(string='Company Supervisor Name')
    supervisor_email = fields.Char(string='Supervisor Email')
    supervisor_phone = fields.Char(string='Supervisor Phone')

    # Faculty Mentor
    faculty_mentor_id = fields.Many2one('faculty.faculty', string='Faculty Mentor',
                                        tracking=True)

    # Work Details
    job_description = fields.Html(string='Job Description')
    responsibilities = fields.Html(string='Key Responsibilities')
    skills_learned = fields.Text(string='Skills/Technologies Learned')

    # Documents
    offer_letter = fields.Binary(string='Offer Letter', attachment=True)
    joining_report = fields.Binary(string='Joining Report', attachment=True)
    completion_certificate = fields.Binary(string='Completion Certificate', attachment=True)

    # Report
    report_ids = fields.One2many('internship.report', 'internship_id', string='Reports')

    # Evaluation
    evaluation_ids = fields.One2many('internship.evaluation', 'internship_id',
                                     string='Evaluations')

    # Marks/Credits
    marks_obtained = fields.Float(string='Marks Obtained')
    max_marks = fields.Float(string='Maximum Marks', default=100.0)
    credits = fields.Float(string='Credits Earned')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('evaluated', 'Evaluated'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    # Performance Rating
    company_rating = fields.Selection([
        ('1', 'Poor'), ('2', 'Below Average'), ('3', 'Average'),
        ('4', 'Good'), ('5', 'Excellent'),
    ], string='Company Rating')

    # PPO (Pre-Placement Offer)
    received_ppo = fields.Boolean(string='Received PPO', tracking=True)
    ppo_ctc = fields.Monetary(string='PPO CTC', currency_field='currency_id')

    # Remarks
    remarks = fields.Text(string='Remarks')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Internship Code must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('internship.internship') or '/'
        return super(Internship, self).create(vals)

    @api.depends('start_date', 'end_date')
    def _compute_duration(self):
        for record in self:
            if record.start_date and record.end_date:
                delta = record.end_date - record.start_date
                record.duration_months = delta.days / 30.0
            else:
                record.duration_months = 0.0

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_start(self):
        self.write({'state': 'ongoing'})

    def action_complete(self):
        self.write({'state': 'completed'})

    def action_evaluate(self):
        self.write({'state': 'evaluated'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def action_view_reports(self):
        """Open the related internship reports."""
        self.ensure_one()
        return {
            'name': _('Internship Reports'),
            'type': 'ir.actions.act_window',
            'res_model': 'internship.report',
            'view_mode': 'list,form',
            'domain': [('internship_id', '=', self.id)],
            'context': {'default_internship_id': self.id},
        }

    def action_view_evaluations(self):
        """Open the related internship evaluations."""
        self.ensure_one()
        return {
            'name': _('Internship Evaluations'),
            'type': 'ir.actions.act_window',
            'res_model': 'internship.evaluation',
            'view_mode': 'list,form',
            'domain': [('internship_id', '=', self.id)],
            'context': {'default_internship_id': self.id},
        }

    def action_view_student(self):
        """Open the student record."""
        self.ensure_one()
        if not self.student_id:
            return False
        return {
            'name': _('Student'),
            'type': 'ir.actions.act_window',
            'res_model': 'student.student',
            'view_mode': 'form',
            'res_id': self.student_id.id,
            'target': 'current',
        }
