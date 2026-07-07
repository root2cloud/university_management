# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PlacementApplication(models.Model):
    _name = 'placement.application'
    _description = 'Student Placement Applications'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'application_date desc'

    name = fields.Char(string='Application Number', required=True, readonly=True,
                       copy=False, default='/')

    # Student
    student_id = fields.Many2one('student.student', string='Student',
                                 required=True, tracking=True, index=True)
    registration_number = fields.Char(related='student_id.registration_number',
                                      string='Registration Number')
    program_id = fields.Many2one(related='student_id.program_id', string='Program', store=True)
    department_id = fields.Many2one(related='student_id.department_id',
                                    string='Department', store=True)
    cgpa = fields.Float(related='student_id.cgpa', string='CGPA')
    academic_year_id = fields.Many2one('university.academic.year',
                                      related='student_id.academic_year_id',
                                      string='Academic Year', store=True)

    # Placement Drive
    drive_id = fields.Many2one('placement.drive', string='Placement Drive',
                               required=True, tracking=True, index=True)
    company_id = fields.Many2one(related='drive_id.company_id', string='Company', store=True)

    # Application Date
    application_date = fields.Date(string='Application Date', default=fields.Date.today(),
                                   required=True)

    # Resume
    resume = fields.Binary(string='Resume', required=True, attachment=True)
    resume_filename = fields.Char(string='Resume Filename')

    # Cover Letter
    cover_letter = fields.Html(string='Cover Letter')

    # Skills
    technical_skills = fields.Text(string='Technical Skills')
    certifications = fields.Text(string='Certifications')

    # Documents
    document_ids = fields.Many2many('ir.attachment', string='Supporting Documents')

    # Selection Rounds
    round_1_status = fields.Selection([
        ('pending', 'Pending'), ('cleared', 'Cleared'), ('rejected', 'Rejected')
    ], string='Round 1 (Aptitude)', default='pending', tracking=True)

    round_2_status = fields.Selection([
        ('pending', 'Pending'), ('cleared', 'Cleared'), ('rejected', 'Rejected')
    ], string='Round 2 (Technical)', tracking=True)

    round_3_status = fields.Selection([
        ('pending', 'Pending'), ('cleared', 'Cleared'), ('rejected', 'Rejected')
    ], string='Round 3 (HR)', tracking=True)

    # Scores
    aptitude_score = fields.Float(string='Aptitude Score')
    technical_score = fields.Float(string='Technical Score')
    hr_score = fields.Float(string='HR Score')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('shortlisted', 'Shortlisted'),
        ('selected', 'Selected'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    ], string='Status', default='draft', tracking=True)

    # Offer
    offer_id = fields.Many2one('placement.offer', string='Offer Letter')

    # Feedback
    feedback = fields.Text(string='Feedback/Comments')

    # Remarks
    remarks = fields.Text(string='Remarks')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Application Number must be unique!'),
        ('unique_application', 'unique(student_id, drive_id)',
         'Student already applied for this drive!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('placement.application') or '/'
        return super(PlacementApplication, self).create(vals)

    @api.constrains('student_id', 'drive_id')
    def _check_eligibility(self):
        """Check if student meets eligibility criteria"""
        for record in self:
            drive = record.drive_id
            student = record.student_id

            # Check CGPA
            if student.cgpa < drive.min_cgpa:
                raise ValidationError(f'CGPA {student.cgpa} is below minimum required {drive.min_cgpa}')

            # Check backlogs
            # if student.active_backlogs > drive.max_backlogs:
            #     raise ValidationError(
            #         f'Active backlogs {student.active_backlogs} exceed maximum allowed {drive.max_backlogs}')

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_review(self):
        self.write({'state': 'under_review'})

    def action_shortlist(self):
        self.write({'state': 'shortlisted'})

    def action_select(self):
        self.write({'state': 'selected'})

    def action_reject(self):
        self.write({'state': 'rejected'})

    def action_withdraw(self):
        self.write({'state': 'withdrawn'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})
