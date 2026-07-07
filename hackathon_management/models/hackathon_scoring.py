from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HackathonScoring(models.Model):
    _name = 'hackathon.scoring'
    _description = 'Hackathon Scoring'
    _order = 'submission_id, judge_id'

    submission_id = fields.Many2one('hackathon.submission', string='Submission', required=True, ondelete='cascade')
    judge_id = fields.Many2one('hackathon.judge', string='Judge', required=True, ondelete='cascade')

    # Scoring Criteria (0-100 scale for each)
    innovation_score = fields.Float(string='Innovation & Creativity', default=0.0)
    technical_score = fields.Float(string='Technical Implementation', default=0.0)
    impact_score = fields.Float(string='Social/Business Impact', default=0.0)
    presentation_score = fields.Float(string='Presentation Quality', default=0.0)

    # Weighted Scores
    innovation_weighted = fields.Float(string='Innovation (Weighted)', compute='_compute_weighted_scores', store=True)
    technical_weighted = fields.Float(string='Technical (Weighted)', compute='_compute_weighted_scores', store=True)
    impact_weighted = fields.Float(string='Impact (Weighted)', compute='_compute_weighted_scores', store=True)
    presentation_weighted = fields.Float(string='Presentation (Weighted)', compute='_compute_weighted_scores',
                                         store=True)

    total_score = fields.Float(string='Total Score', compute='_compute_total_score', store=True)

    # Comments
    comments = fields.Text(string='Judge Comments')
    strengths = fields.Text(string='Strengths')
    improvements = fields.Text(string='Areas for Improvement')

    scoring_date = fields.Datetime(string='Scoring Date', default=fields.Datetime.now)

    @api.depends('innovation_score', 'technical_score', 'impact_score', 'presentation_score', 'judge_id')
    def _compute_weighted_scores(self):
        for record in self:
            if record.judge_id:
                record.innovation_weighted = record.innovation_score * (record.judge_id.innovation_weight / 100)
                record.technical_weighted = record.technical_score * (record.judge_id.technical_weight / 100)
                record.impact_weighted = record.impact_score * (record.judge_id.impact_weight / 100)
                record.presentation_weighted = record.presentation_score * (record.judge_id.presentation_weight / 100)

    @api.depends('innovation_weighted', 'technical_weighted', 'impact_weighted', 'presentation_weighted')
    def _compute_total_score(self):
        for record in self:
            record.total_score = (record.innovation_weighted + record.technical_weighted +
                                  record.impact_weighted + record.presentation_weighted)

    @api.constrains('innovation_score', 'technical_score', 'impact_score', 'presentation_score')
    def _check_scores(self):
        for record in self:
            if not (0 <= record.innovation_score <= 100):
                raise ValidationError(_('Innovation score must be between 0 and 100.'))
            if not (0 <= record.technical_score <= 100):
                raise ValidationError(_('Technical score must be between 0 and 100.'))
            if not (0 <= record.impact_score <= 100):
                raise ValidationError(_('Impact score must be between 0 and 100.'))
            if not (0 <= record.presentation_score <= 100):
                raise ValidationError(_('Presentation score must be between 0 and 100.'))

    @api.constrains('submission_id', 'judge_id')
    def _check_unique_scoring(self):
        for record in self:
            duplicate = self.search([
                ('submission_id', '=', record.submission_id.id),
                ('judge_id', '=', record.judge_id.id),
                ('id', '!=', record.id)
            ])
            if duplicate:
                raise ValidationError(_('This judge has already scored this submission.'))