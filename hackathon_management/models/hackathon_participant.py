from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HackathonParticipant(models.Model):
    _name = 'hackathon.participant'
    _description = 'Hackathon Participant'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Full Name', required=True, tracking=True)
    email = fields.Char(string='Email', required=True, tracking=True)
    phone = fields.Char(string='Phone Number', required=True)

    event_id = fields.Many2one('hackathon.event', string='Event', required=True, ondelete='cascade')
    team_id = fields.Many2one('hackathon.team', string='Team', ondelete='set null')

    # Personal Details
    date_of_birth = fields.Date(string='Date of Birth')
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], string='Gender')

    # Academic Details
    institution = fields.Char(string='College/Institution', required=True)
    department = fields.Char(string='Department/Branch')
    year_of_study = fields.Selection([
        ('1', 'First Year'),
        ('2', 'Second Year'),
        ('3', 'Third Year'),
        ('4', 'Fourth Year'),
        ('pg', 'Post Graduate'),
        ('phd', 'PhD')
    ], string='Year of Study')
    student_id = fields.Char(string='Student ID/Roll Number')

    # Technical Details
    skills = fields.Text(string='Technical Skills')
    programming_languages = fields.Char(string='Programming Languages')
    experience_level = fields.Selection([
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced')
    ], string='Experience Level', default='intermediate')

    # Links
    github_profile = fields.Char(string='GitHub Profile')
    linkedin_profile = fields.Char(string='LinkedIn Profile')
    portfolio = fields.Char(string='Portfolio URL')

    # Emergency Contact
    emergency_contact_name = fields.Char(string='Emergency Contact Name')
    emergency_contact_phone = fields.Char(string='Emergency Contact Phone')

    # Dietary & Medical
    dietary_preferences = fields.Selection([
        ('veg', 'Vegetarian'),
        ('non_veg', 'Non-Vegetarian'),
        ('vegan', 'Vegan')
    ], string='Dietary Preference')
    medical_conditions = fields.Text(string='Medical Conditions/Allergies')

    # T-Shirt Size (for event merchandise)
    tshirt_size = fields.Selection([
        ('xs', 'XS'),
        ('s', 'S'),
        ('m', 'M'),
        ('l', 'L'),
        ('xl', 'XL'),
        ('xxl', 'XXL')
    ], string='T-Shirt Size')

    # Role
    is_team_leader = fields.Boolean(string='Is Team Leader', compute='_compute_is_team_leader', store=True)

    # State
    state = fields.Selection([
        ('registered', 'Registered'),
        ('verified', 'Verified'),
        ('checked_in', 'Checked In'),
        ('withdrawn', 'Withdrawn')
    ], string='Status', default='registered', required=True, tracking=True)

    registration_date = fields.Datetime(string='Registration Date', default=fields.Datetime.now)
    check_in_date = fields.Datetime(string='Check-in Date')

    # Certificate
    certificate_issued = fields.Boolean(string='Certificate Issued', default=False)

    active = fields.Boolean(string='Active', default=True)

    @api.depends('team_id', 'team_id.leader_id')
    def _compute_is_team_leader(self):
        for record in self:
            record.is_team_leader = record.team_id and record.team_id.leader_id == record

    @api.constrains('email')
    def _check_unique_email(self):
        for record in self:
            duplicate = self.search([
                ('email', '=', record.email),
                ('event_id', '=', record.event_id.id),
                ('id', '!=', record.id)
            ])
            if duplicate:
                raise ValidationError(_('A participant with this email is already registered for this event.'))

    def action_verify(self):
        self.write({'state': 'verified'})

    def action_check_in(self):
        self.write({
            'state': 'checked_in',
            'check_in_date': fields.Datetime.now()
        })

    def action_withdraw(self):
        self.write({'state': 'withdrawn'})