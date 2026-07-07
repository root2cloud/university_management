from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HackathonTeam(models.Model):
    _name = 'hackathon.team'
    _description = 'Hackathon Team'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Team Name', required=True, tracking=True)
    code = fields.Char(string='Team Code', required=True, copy=False, readonly=True, default='New')

    event_id = fields.Many2one('hackathon.event', string='Event', required=True, ondelete='cascade')
    track_id = fields.Many2one('hackathon.track', string='Selected Track', domain="[('event_id', '=', event_id)]")

    # Team Leader
    leader_id = fields.Many2one('hackathon.participant', string='Team Leader', required=True, tracking=True)

    # Team Members
    member_ids = fields.One2many('hackathon.participant', 'team_id', string='Team Members')
    member_count = fields.Integer(string='Team Size', compute='_compute_member_count', store=True)

    # Contact
    contact_email = fields.Char(string='Contact Email', related='leader_id.email')
    contact_phone = fields.Char(string='Contact Phone', related='leader_id.phone')

    # Project Details
    project_name = fields.Char(string='Project Name', tracking=True)
    project_description = fields.Html(string='Project Description')

    # Institution
    institution = fields.Char(string='College/Institution', related='leader_id.institution')

    # Mentor
    mentor_id = fields.Many2one('hackathon.mentor', string='Assigned Mentor')

    # Submission
    submission_id = fields.Many2one('hackathon.submission', string='Submission')
    has_submitted = fields.Boolean(string='Submitted', compute='_compute_has_submitted')

    # State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('registered', 'Registered'),
        ('confirmed', 'Confirmed'),
        ('working', 'Working'),
        ('submitted', 'Submitted'),
        ('disqualified', 'Disqualified')
    ], string='Status', default='draft', required=True, tracking=True)

    registration_date = fields.Datetime(string='Registration Date', default=fields.Datetime.now)

    @api.model
    def create(self, vals):
        if vals.get('code', 'New') == 'New':
            vals['code'] = self.env['ir.sequence'].next_by_code('hackathon.team') or 'New'
        return super(HackathonTeam, self).create(vals)

    @api.depends('member_ids')
    def _compute_member_count(self):
        for record in self:
            record.member_count = len(record.member_ids)

    @api.depends('submission_id')
    def _compute_has_submitted(self):
        for record in self:
            record.has_submitted = bool(record.submission_id)

    @api.constrains('member_ids', 'event_id')
    def _check_team_size(self):
        for record in self:
            if record.event_id:
                team_size = len(record.member_ids)
                if team_size < record.event_id.min_team_size:
                    raise ValidationError(_('Team size must be at least %s members.') % record.event_id.min_team_size)
                if team_size > record.event_id.max_team_size:
                    raise ValidationError(_('Team size cannot exceed %s members.') % record.event_id.max_team_size)

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_start_working(self):
        self.write({'state': 'working'})

    def action_disqualify(self):
        self.write({'state': 'disqualified'})