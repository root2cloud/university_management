from odoo import models, fields, api


class HackathonMentor(models.Model):
    _name = 'hackathon.mentor'
    _description = 'Hackathon Mentor'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Name', required=True, tracking=True)
    email = fields.Char(string='Email', required=True)
    phone = fields.Char(string='Phone Number')

    # Professional Details
    designation = fields.Char(string='Designation')
    organization = fields.Char(string='Organization/Company')
    expertise = fields.Text(string='Area of Expertise')
    experience_years = fields.Integer(string='Years of Experience')

    # Links
    linkedin_profile = fields.Char(string='LinkedIn Profile')
    website = fields.Char(string='Website')

    # Availability
    availability = fields.Text(string='Availability Schedule')
    max_teams = fields.Integer(string='Maximum Teams to Mentor', default=3)

    # Assigned Teams
    team_ids = fields.One2many('hackathon.team', 'mentor_id', string='Assigned Teams')
    team_count = fields.Integer(string='Number of Teams', compute='_compute_team_count')

    # Biography
    bio = fields.Html(string='Biography')
    image = fields.Binary(string='Photo')

    active = fields.Boolean(string='Active', default=True)

    @api.depends('team_ids')
    def _compute_team_count(self):
        for record in self:
            record.team_count = len(record.team_ids)