# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class FacultyDesignation(models.Model):
    _name = 'faculty.designation'
    _description = 'Faculty Designation (Professor, Assistant Prof, etc.)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    name = fields.Char(string='Designation Name', required=True, tracking=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    level = fields.Selection([
        ('professor', 'Professor'),
        ('associate_professor', 'Associate Professor'),
        ('assistant_professor', 'Assistant Professor'),
        ('lecturer', 'Lecturer'),
        ('senior_lecturer', 'Senior Lecturer'),
        ('guest_faculty', 'Guest Faculty'),
        ('visiting_faculty', 'Visiting Faculty'),
        ('lab_assistant', 'Lab Assistant'),
        ('teaching_assistant', 'Teaching Assistant'),
    ], string='Designation Level', required=True)

    min_salary = fields.Monetary(string='Minimum Salary', currency_field='currency_id')
    max_salary = fields.Monetary(string='Maximum Salary', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    min_qualification = fields.Selection([
        ('phd', 'Ph.D'),
        ('mphil', 'M.Phil'),
        ('postgraduate', 'Post Graduate'),
        ('graduate', 'Graduate'),
    ], string='Minimum Qualification Required')

    min_experience_years = fields.Integer(string='Minimum Experience (Years)')
    max_teaching_hours = fields.Float(string='Maximum Teaching Hours/Week', default=18.0)
    responsibilities = fields.Html(string='Key Responsibilities')

    faculty_ids = fields.One2many('faculty.faculty', 'designation_id', string='Faculty')
    total_faculty = fields.Integer(string='Total Faculty', compute='_compute_total')
    description = fields.Text(string='Description')

    # ── Link to Odoo HR Job Position ─────────────────────────────────────
    hr_job_id = fields.Many2one(
        'hr.job', string='HR Job Position',
        help='Linked Odoo HR Job Position — used by Payroll and HR modules.',
        copy=False
    )

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Designation Code must be unique!'),
    ]

    @api.depends('faculty_ids')
    def _compute_total(self):
        for record in self:
            record.total_faculty = len(record.faculty_ids)

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        rec._sync_hr_job()
        return rec

    def write(self, vals):
        res = super().write(vals)
        if 'name' in vals or 'active' in vals:
            self._sync_hr_job()
        return res

    def _sync_hr_job(self):
        HrJob = self.env['hr.job']
        for rec in self:
            if rec.hr_job_id:
                rec.hr_job_id.write({'name': rec.name, 'active': rec.active})
            else:
                job = HrJob.search([('name', '=', rec.name)], limit=1)
                if not job:
                    job = HrJob.create({'name': rec.name})
                rec.hr_job_id = job.id

    def action_faculty(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Faculty',
            'res_model': 'faculty.faculty',
            'view_mode': 'list,kanban,form',
            'domain': [('designation_id', '=', self.id)],
            'context': {
                'default_designation_id': self.id,
                'search_default_designation_id': self.id,
            },
        }


class FacultyQualification(models.Model):
    _name = 'faculty.qualification'
    _description = 'Faculty Qualification Details'
    _order = 'year_of_passing desc'

    faculty_id = fields.Many2one('faculty.faculty', string='Faculty',
                                 required=True, ondelete='cascade')
    degree = fields.Char(string='Degree/Qualification', required=True)
    specialization = fields.Char(string='Specialization/Major')
    institution = fields.Char(string='Institution/University', required=True)
    year_of_passing = fields.Integer(string='Year of Passing', required=True)
    percentage = fields.Float(string='Percentage/CGPA')
    certificate = fields.Binary(string='Certificate/Document')
    certificate_name = fields.Char(string='File Name')
    is_verified = fields.Boolean(string='Verified')

    # ── Link to Odoo HR Resume Line ───────────────────────────────────────
    hr_resume_line_id = fields.Many2one(
        'hr.resume.line', string='HR Resume Line',
        copy=False, ondelete='set null'
    )

    @api.model
    def create(self, vals):
        rec = super().create(vals)
        rec._sync_hr_resume_line()
        return rec

    def write(self, vals):
        res = super().write(vals)
        if {'degree', 'specialization', 'institution', 'year_of_passing'}.intersection(vals.keys()):
            self._sync_hr_resume_line()
        return res

    def unlink(self):
        for rec in self:
            if rec.hr_resume_line_id:
                rec.hr_resume_line_id.sudo().unlink()
        return super().unlink()

    def _sync_hr_resume_line(self):
        ResumeLine = self.env['hr.resume.line']
        line_type = self.env['hr.resume.line.type'].search(
            [('name', 'ilike', 'Education')], limit=1)
        if not line_type:
            line_type = self.env['hr.resume.line.type'].create({'name': 'Education'})

        for rec in self:
            if not rec.faculty_id or not rec.faculty_id.employee_id:
                continue
            employee = rec.faculty_id.employee_id
            name = '%s — %s' % (rec.degree, rec.specialization) if rec.specialization else rec.degree
            description = '%s | %.1f%%' % (rec.institution, rec.percentage) if rec.percentage else rec.institution
            date_end = '%s-01-01' % rec.year_of_passing if rec.year_of_passing else False

            if rec.hr_resume_line_id:
                rec.hr_resume_line_id.write({
                    'name': name, 'date_end': date_end,
                    'description': description, 'line_type_id': line_type.id,
                })
            else:
                line = ResumeLine.create({
                    'employee_id': employee.id, 'name': name,
                    'date_end': date_end, 'description': description,
                    'line_type_id': line_type.id,
                })
                rec.hr_resume_line_id = line.id