from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta


class HackathonEvent(models.Model):
    _name = 'hackathon.event'
    _description = 'Hackathon Event'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc'

    name = fields.Char(string='Hackathon Name', required=True, tracking=True)
    code = fields.Char(string='Event Code', required=True, copy=False, readonly=True, default='New')
    description = fields.Html(string='Description')

    # Event Dates
    registration_start_date = fields.Datetime(string='Registration Start', required=True, tracking=True)
    registration_end_date = fields.Datetime(string='Registration End', required=True, tracking=True)
    start_date = fields.Datetime(string='Hackathon Start', required=True, tracking=True)
    end_date = fields.Datetime(string='Hackathon End', required=True, tracking=True)

    # Venue Information
    venue = fields.Char(string='Venue', required=True)
    venue_address = fields.Text(string='Venue Address')
    venue_capacity = fields.Integer(string='Venue Capacity')

    # Event Details
    theme = fields.Char(string='Theme')
    rules = fields.Html(string='Rules & Guidelines')
    eligibility = fields.Html(string='Eligibility Criteria')

    # Team Configuration
    min_team_size = fields.Integer(string='Minimum Team Size', default=2)
    max_team_size = fields.Integer(string='Maximum Team Size', default=5)
    allow_solo = fields.Boolean(string='Allow Solo Participants', default=False)

    # Relationships
    track_ids = fields.One2many('hackathon.track', 'event_id', string='Tracks/Problem Statements')
    team_ids = fields.One2many('hackathon.team', 'event_id', string='Teams')
    participant_ids = fields.One2many('hackathon.participant', 'event_id', string='Participants')
    mentor_ids = fields.Many2many('hackathon.mentor', string='Mentors')
    judge_ids = fields.Many2many('hackathon.judge', string='Judges')
    submission_ids = fields.One2many('hackathon.submission', 'event_id', string='Submissions')

    # Organizer Details
    organizer_id = fields.Many2one('res.users', string='Organizer', default=lambda self: self.env.user)
    organizer_contact = fields.Char(string='Contact Email')
    organizer_phone = fields.Char(string='Contact Phone')

    # Prizes
    first_prize = fields.Monetary(string='First Prize', currency_field='currency_id')
    second_prize = fields.Monetary(string='Second Prize', currency_field='currency_id')
    third_prize = fields.Monetary(string='Third Prize', currency_field='currency_id')
    special_prizes = fields.Text(string='Special Prizes')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)

    # Resources
    resources_provided = fields.Html(string='Resources Provided')
    api_keys = fields.Text(string='API Keys & Access')
    datasets = fields.Text(string='Available Datasets')

    # Statistics
    total_teams = fields.Integer(string='Total Teams', compute='_compute_statistics', store=True)
    total_participants = fields.Integer(string='Total Participants', compute='_compute_statistics', store=True)
    total_submissions = fields.Integer(string='Total Submissions', compute='_compute_statistics', store=True)

    # State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('registration', 'Registration Open'),
        ('ongoing', 'Ongoing'),
        ('judging', 'Judging'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True, tracking=True)

    # Image
    image = fields.Binary(string='Event Banner')

    @api.model
    def create(self, vals):
        if vals.get('code', 'New') == 'New':
            vals['code'] = self.env['ir.sequence'].next_by_code('hackathon.event') or 'New'
        return super(HackathonEvent, self).create(vals)

    @api.depends('team_ids', 'participant_ids', 'submission_ids')
    def _compute_statistics(self):
        for record in self:
            record.total_teams = len(record.team_ids)
            record.total_participants = len(record.participant_ids)
            record.total_submissions = len(record.submission_ids)

    @api.constrains('start_date', 'end_date', 'registration_start_date', 'registration_end_date')
    def _check_dates(self):
        for record in self:
            if record.registration_start_date >= record.registration_end_date:
                raise ValidationError(_('Registration end date must be after start date.'))
            if record.start_date >= record.end_date:
                raise ValidationError(_('Event end date must be after start date.'))
            if record.registration_end_date > record.start_date:
                raise ValidationError(_('Registration must close before event starts.'))

    def action_publish(self):
        self.write({'state': 'published'})

    def action_open_registration(self):
        self.write({'state': 'registration'})

    def action_start_hackathon(self):
        self.write({'state': 'ongoing'})

    def action_start_judging(self):
        self.write({'state': 'judging'})

    def action_complete(self):
        self.write({'state': 'completed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})