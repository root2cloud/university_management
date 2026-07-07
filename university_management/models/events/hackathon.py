# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class Hackathon(models.Model):
    _name = 'hackathon.hackathon'
    _description = 'Hackathon Management'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'website.published.mixin']
    _order = 'start_date desc'

    name = fields.Char(string='Hackathon Name', required=True, tracking=True)
    code = fields.Char(string='Hackathon Code', required=True, readonly=True,
                       copy=False, default='/')

    # Event Link (optional)
    event_id = fields.Many2one('university.event', string='Related Event')

    # Theme
    theme = fields.Char(string='Theme/Topic', required=True)
    description = fields.Html(string='Description')

    # Duration
    start_date = fields.Datetime(string='Start Date & Time', required=True, tracking=True)
    end_date = fields.Datetime(string='End Date & Time', required=True, tracking=True)
    duration_hours = fields.Float(string='Duration (Hours)', compute='_compute_duration')

    # Venue
    venue_type = fields.Selection([
        ('offline', 'Offline'),
        ('online', 'Online'),
        ('hybrid', 'Hybrid'),
    ], string='Venue Type', default='offline')

    venue = fields.Char(string='Venue')
    online_platform_url = fields.Char(string='Online Platform URL')

    # Registration
    registration_start = fields.Datetime(string='Registration Start')
    registration_end = fields.Datetime(string='Registration End')
    max_teams = fields.Integer(string='Maximum Teams')
    team_size_min = fields.Integer(string='Min Team Size', default=1)
    team_size_max = fields.Integer(string='Max Team Size', default=4)

    # Teams
    team_ids = fields.One2many('hackathon.team', 'hackathon_id', string='Teams')
    total_teams = fields.Integer(string='Total Teams', compute='_compute_teams')

    # Judges
    judge_ids = fields.Many2many('hackathon.judge', string='Judges')

    # Prizes
    first_prize = fields.Monetary(string='First Prize', currency_field='currency_id')
    second_prize = fields.Monetary(string='Second Prize', currency_field='currency_id')
    third_prize = fields.Monetary(string='Third Prize', currency_field='currency_id')

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Winners
    winner_ids = fields.One2many('hackathon.winner', 'hackathon_id', string='Winners')

    # Rules
    rules = fields.Html(string='Rules & Guidelines')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('registration_open', 'Registration Open'),
        ('registration_closed', 'Registration Closed'),
        ('ongoing', 'Ongoing'),
        ('judging', 'Judging Phase'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Hackathon Code must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('code', '/') == '/':
            vals['code'] = self.env['ir.sequence'].next_by_code('hackathon.hackathon') or '/'
        return super(Hackathon, self).create(vals)

    @api.depends('start_date', 'end_date')
    def _compute_duration(self):
        for record in self:
            if record.start_date and record.end_date:
                delta = record.end_date - record.start_date
                record.duration_hours = delta.total_seconds() / 3600
            else:
                record.duration_hours = 0.0

    @api.depends('team_ids')
    def _compute_teams(self):
        for record in self:
            record.total_teams = len(record.team_ids)

    # Workflow Actions
    def action_open_registration(self):
        """Open registration for hackathon."""
        self.write({'state': 'registration_open'})

    def action_close_registration(self):
        """Close registration for hackathon."""
        self.write({'state': 'registration_closed'})

    def action_start_hackathon(self):
        """Start the hackathon."""
        self.write({'state': 'ongoing'})

    def action_start_judging(self):
        """Start judging phase."""
        self.write({'state': 'judging'})

    def action_complete(self):
        """Mark hackathon as completed."""
        self.write({'state': 'completed'})

    def action_cancel(self):
        """Cancel the hackathon."""
        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def action_view_teams(self):
        """Open the teams list for this hackathon."""
        self.ensure_one()
        return {
            'name': _('Hackathon Teams'),
            'type': 'ir.actions.act_window',
            'res_model': 'hackathon.team',
            'view_mode': 'list,form',
            'domain': [('hackathon_id', '=', self.id)],
            'context': {
                'default_hackathon_id': self.id,
                'search_default_hackathon_id': self.id
            },
        }

    def toggle_website_published(self):
        """Toggle website publication status."""
        for record in self:
            record.website_published = not record.website_published
        return True


