from odoo import models, fields, api


class HackathonJudge(models.Model):
    _name = 'hackathon.judge'
    _description = 'Hackathon Judge'
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

    # Judging Criteria Weights
    innovation_weight = fields.Float(string='Innovation Weight (%)', default=25.0)
    technical_weight = fields.Float(string='Technical Implementation Weight (%)', default=25.0)
    impact_weight = fields.Float(string='Impact Weight (%)', default=25.0)
    presentation_weight = fields.Float(string='Presentation Weight (%)', default=25.0)

    # Links
    linkedin_profile = fields.Char(string='LinkedIn Profile')

    # Scoring
    scoring_ids = fields.One2many('hackathon.scoring', 'judge_id', string='Scored Submissions')

    # Biography
    bio = fields.Html(string='Biography')
    image = fields.Binary(string='Photo')

    active = fields.Boolean(string='Active', default=True)