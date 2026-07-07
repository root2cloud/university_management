# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HackathonTeam(models.Model):
    _name = 'hackathon.team'
    _description = 'Hackathon Team Registration'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'registration_date desc'

    name = fields.Char(string='Team Name', required=True, tracking=True)
    code = fields.Char(string='Team Code', required=True, readonly=True,
                       copy=False, default='/')

    # Hackathon
    hackathon_id = fields.Many2one('hackathon.hackathon', string='Hackathon',
                                   required=True, tracking=True, index=True)

    # Team Leader
    team_leader_id = fields.Many2one('student.student', string='Team Leader',
                                     required=True, tracking=True)

    # Team Members
    member_ids = fields.Many2many('student.student', 'hackathon_team_member_rel',
                                  'team_id', 'student_id',
                                  string='Team Members')
    team_size = fields.Integer(string='Team Size', compute='_compute_team_size')

    # Project Details
    project_title = fields.Char(string='Project Title', tracking=True)
    project_description = fields.Html(string='Project Description')
    technologies = fields.Text(string='Technologies to be Used')

    # Submission
    github_repo = fields.Char(string='GitHub Repository URL')
    demo_url = fields.Char(string='Demo URL')
    presentation = fields.Binary(string='Presentation', attachment=True)
    video_url = fields.Char(string='Video Demo URL')

    submission_date = fields.Datetime(string='Submission Date')

    # Evaluation
    score = fields.Float(string='Total Score', compute='_compute_score', store=True)

    # Registration
    registration_date = fields.Datetime(string='Registration Date', default=fields.Datetime.now)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('registered', 'Registered'),
        ('approved', 'Approved'),
        ('disqualified', 'Disqualified'),
    ], string='Status', default='draft', tracking=True)

    # Remarks
    remarks = fields.Text(string='Remarks')

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Team Code must be unique!'),
        ('name_hackathon_unique', 'unique(name, hackathon_id)',
         'Team name must be unique per hackathon!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('code', '/') == '/':
            vals['code'] = self.env['ir.sequence'].next_by_code('hackathon.team') or '/'
        return super(HackathonTeam, self).create(vals)

    @api.depends('member_ids', 'team_leader_id')
    def _compute_team_size(self):
        for record in self:
            # Include team leader in count
            all_members = record.member_ids | record.team_leader_id
            record.team_size = len(all_members)

    @api.depends('hackathon_id.judge_ids')
    def _compute_score(self):
        for record in self:
            # Calculate average score from all judges
            # This would link to judge evaluations (not implemented here for brevity)
            record.score = 0.0

    @api.constrains('team_size', 'hackathon_id')
    def _check_team_size(self):
        for record in self:
            hackathon = record.hackathon_id
            if record.team_size < hackathon.team_size_min:
                raise ValidationError(f'Team size must be at least {hackathon.team_size_min}')
            if record.team_size > hackathon.team_size_max:
                raise ValidationError(f'Team size cannot exceed {hackathon.team_size_max}')

    def action_register(self):
        self.write({'state': 'registered'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_disqualify(self):
        self.write({'state': 'disqualified'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def action_view_team_members(self):
        """Open the team members list."""
        self.ensure_one()
        # Get all members including team leader
        all_member_ids = (self.member_ids | self.team_leader_id).ids

        return {
            'name': _('Team Members'),
            'type': 'ir.actions.act_window',
            'res_model': 'student.student',
            'view_mode': 'list,form',
            'domain': [('id', 'in', all_member_ids)],
            'context': {'create': False},
        }
