from odoo import models, fields, api


class HackathonTrack(models.Model):
    _name = 'hackathon.track'
    _description = 'Hackathon Track/Problem Statement'
    _order = 'sequence, name'

    name = fields.Char(string='Track Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    event_id = fields.Many2one('hackathon.event', string='Event', required=True, ondelete='cascade')

    description = fields.Html(string='Description')
    problem_statement = fields.Html(string='Problem Statement', required=True)

    # Technical Details
    technologies = fields.Char(string='Suggested Technologies')
    difficulty_level = fields.Selection([
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced')
    ], string='Difficulty Level', default='intermediate')

    # Sponsor Details
    sponsor_id = fields.Many2one('res.partner', string='Sponsor')
    sponsor_prize = fields.Monetary(string='Sponsor Prize', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='event_id.currency_id')

    # Resources
    reference_links = fields.Text(string='Reference Links')
    sample_data = fields.Text(string='Sample Data/Resources')

    # Statistics
    team_ids = fields.One2many('hackathon.team', 'track_id', string='Teams')
    team_count = fields.Integer(string='Number of Teams', compute='_compute_team_count')

    active = fields.Boolean(string='Active', default=True)

    @api.depends('team_ids')
    def _compute_team_count(self):
        for record in self:
            record.team_count = len(record.team_ids)