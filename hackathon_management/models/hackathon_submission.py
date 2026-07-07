from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HackathonSubmission(models.Model):
    _name = 'hackathon.submission'
    _description = 'Hackathon Submission'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'submission_date desc'

    name = fields.Char(string='Submission Title', required=True, tracking=True)
    event_id = fields.Many2one('hackathon.event', string='Event', required=True, ondelete='cascade')
    team_id = fields.Many2one('hackathon.team', string='Team', required=True, ondelete='cascade')
    track_id = fields.Many2one('hackathon.track', related='team_id.track_id', string='Track', store=True)

    # Submission Details
    description = fields.Html(string='Project Description', required=True)
    problem_solved = fields.Html(string='Problem Solved')
    solution_approach = fields.Html(string='Solution Approach')

    # Technical Details
    technologies_used = fields.Text(string='Technologies Used')
    features = fields.Html(string='Key Features')
    architecture = fields.Html(string='System Architecture')

    # Links & Files
    github_repo = fields.Char(string='GitHub Repository URL')
    demo_url = fields.Char(string='Demo/Live URL')
    video_url = fields.Char(string='Demo Video URL')
    presentation_url = fields.Char(string='Presentation URL')

    # Attachments
    attachment_ids = fields.Many2many('ir.attachment', string='Additional Files')

    # Future Scope
    future_enhancements = fields.Html(string='Future Enhancements')
    commercial_viability = fields.Html(string='Commercial Viability')

    # Scoring
    scoring_ids = fields.One2many('hackathon.scoring', 'submission_id', string='Scores')
    average_score = fields.Float(string='Average Score', compute='_compute_average_score', store=True)
    total_score = fields.Float(string='Total Score', compute='_compute_total_score', store=True)

    # Winner Status
    is_winner = fields.Boolean(string='Winner', default=False)
    prize_category = fields.Selection([
        ('first', 'First Prize'),
        ('second', 'Second Prize'),
        ('third', 'Third Prize'),
        ('special', 'Special Prize'),
        ('track_winner', 'Track Winner')
    ], string='Prize Category')

    # State
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('evaluated', 'Evaluated'),
        ('winner', 'Winner')
    ], string='Status', default='draft', required=True, tracking=True)

    submission_date = fields.Datetime(string='Submission Date', default=fields.Datetime.now)

    @api.depends('scoring_ids', 'scoring_ids.total_score')
    def _compute_average_score(self):
        for record in self:
            if record.scoring_ids:
                record.average_score = sum(record.scoring_ids.mapped('total_score')) / len(record.scoring_ids)
            else:
                record.average_score = 0.0

    @api.depends('scoring_ids', 'scoring_ids.total_score')
    def _compute_total_score(self):
        for record in self:
            record.total_score = sum(record.scoring_ids.mapped('total_score'))

    @api.constrains('team_id', 'event_id')
    def _check_duplicate_submission(self):
        for record in self:
            duplicate = self.search([
                ('team_id', '=', record.team_id.id),
                ('event_id', '=', record.event_id.id),
                ('id', '!=', record.id)
            ])
            if duplicate:
                raise ValidationError(_('This team has already submitted a project for this event.'))

    def action_submit(self):
        self.write({'state': 'submitted', 'submission_date': fields.Datetime.now()})
        self.team_id.write({'state': 'submitted', 'submission_id': self.id})

    def action_start_review(self):
        self.write({'state': 'under_review'})

    def action_evaluate(self):
        self.write({'state': 'evaluated'})

    def action_mark_winner(self):
        self.write({'state': 'winner', 'is_winner': True})

    def action_view_scores(self):
        """Open the scoring records for this submission"""
        self.ensure_one()
        return {
            'name': 'Scores',
            'type': 'ir.actions.act_window',
            'res_model': 'hackathon.scoring',
            'view_mode': 'list,form',
            'domain': [('submission_id', '=', self.id)],
            'context': {'default_submission_id': self.id},
        }