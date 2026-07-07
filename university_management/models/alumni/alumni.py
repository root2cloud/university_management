# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class Alumni(models.Model):
    _name = 'alumni.alumni'
    _description = 'Alumni Database'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _inherits = {'res.partner': 'partner_id'}  # Integration with contacts
    _order = 'graduation_year desc, name'

    # Partner (for contact details)
    partner_id = fields.Many2one('res.partner', string='Related Partner',
                                 required=True, ondelete='cascade', auto_join=True)

    # Student Reference
    student_id = fields.Many2one('student.student', string='Student Record')
    registration_number = fields.Char(string='Registration Number')

    # Photo
    photo = fields.Binary(string='Photo', attachment=True)

    # Academic Details
    program_id = fields.Many2one('university.program', string='Program', required=True)
    department_id = fields.Many2one('university.department', string='Department')
    batch_id = fields.Many2one('university.batch', string='Batch')

    admission_year = fields.Integer(string='Year of Admission')
    graduation_year = fields.Integer(string='Year of Graduation', required=True, index=True, store=True)

    # Education
    cgpa = fields.Float(string='CGPA')
    final_percentage = fields.Float(string='Final Percentage')

    # Current Employment
    is_employed = fields.Boolean(string='Currently Employed', default=True, store=True)
    current_company = fields.Char(string='Current Company')
    current_designation = fields.Char(string='Current Designation')
    current_location = fields.Char(string='Current Location')

    industry = fields.Selection([
        ('it', 'IT/Software'),
        ('core', 'Core Engineering'),
        ('finance', 'Finance/Banking'),
        ('consulting', 'Consulting'),
        ('manufacturing', 'Manufacturing'),
        ('healthcare', 'Healthcare'),
        ('education', 'Education'),
        ('government', 'Government'),
        ('business', 'Business/Entrepreneurship'),
        ('other', 'Other'),
    ], string='Industry')

    annual_ctc = fields.Monetary(string='Annual CTC (LPA)', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Higher Education
    pursuing_higher_education = fields.Boolean(string='Pursuing Higher Education', store=True)
    higher_education_details = fields.Text(string='Higher Education Details')

    # Social Media
    linkedin_profile = fields.Char(string='LinkedIn Profile')
    twitter_handle = fields.Char(string='Twitter Handle')
    facebook_profile = fields.Char(string='Facebook Profile')

    # Achievements
    achievement_ids = fields.One2many('alumni.achievement', 'alumni_id', string='Achievements')

    # Events Participation
    event_registration_ids = fields.Many2many('alumni.event', string='Events Attended')

    # Donations
    donation_ids = fields.One2many('alumni.donation', 'alumni_id', string='Donations')
    total_donations = fields.Monetary(string='Total Donations', compute='_compute_donations',
                                      currency_field='currency_id', store=True)

    # Mentorship
    willing_to_mentor = fields.Boolean(string='Willing to Mentor Students', store=True)
    mentorship_area = fields.Text(string='Mentorship Area/Expertise')

    # Portal Access
    user_id = fields.Many2one('res.users', string='Portal User')

    # Status
    active = fields.Boolean(string='Active', default=True, store=True)

    @api.depends('donation_ids', 'donation_ids.amount')
    def _compute_donations(self):
        for record in self:
            record.total_donations = sum(record.donation_ids.mapped('amount'))

    def action_alumni_achievement(self):
        """Open achievements for this alumni."""
        self.ensure_one()
        return {
            'name': _('Achievements'),
            'type': 'ir.actions.act_window',
            'res_model': 'alumni.achievement',
            'view_mode': 'list,form',
            'domain': [('alumni_id', '=', self.id)],
            'context': {
                'default_alumni_id': self.id,
            },
        }

    def action_alumni_donation(self):
        """Open donations for this alumni."""
        self.ensure_one()
        return {
            'name': _('Donations'),
            'type': 'ir.actions.act_window',
            'res_model': 'alumni.donation',
            'view_mode': 'list,form',
            'domain': [('alumni_id', '=', self.id)],
            'context': {'default_alumni_id': self.id},
        }