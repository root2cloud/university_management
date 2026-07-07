# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class NAACDepartmentActivity(models.Model):
    _name = 'naac.department.activity'
    _description = 'NAAC Department Activity'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'activity_date desc'

    name = fields.Char(string='Activity Title', required=True, tracking=True)
    reference = fields.Char(string='Reference', readonly=True, copy=False, default='/')

    department_id = fields.Many2one('university.department', string='Department', required=True, tracking=True)
    faculty_id = fields.Many2one('hr.employee', string='Reported By (Faculty)', tracking=True)
    criterion_id = fields.Many2one('naac.criterion', string='NAAC Criterion', required=True, tracking=True)
    metric_id = fields.Many2one('naac.metric', string='NAAC Metric', tracking=True,
                                 domain="[('criterion_id', '=', criterion_id)]")

    activity_type = fields.Selection([
        ('guest_lecture', 'Guest Lecture'),
        ('workshop', 'Workshop'),
        ('seminar', 'Seminar'),
        ('research_publication', 'Research Publication'),
        ('patent_filing', 'Patent Filing'),
        ('industry_collaboration', 'Industry Collaboration'),
        ('student_placement', 'Student Placement'),
        ('extension_activity', 'Extension / Community Activity'),
        ('infrastructure', 'Infrastructure Development'),
        ('mou_signing', 'MoU Signing'),
        ('faculty_development', 'Faculty Development Program'),
        ('sports', 'Sports / Cultural Activity'),
        ('other', 'Other'),
    ], string='Activity Type', required=True, tracking=True)

    activity_date = fields.Date(string='Activity Date', required=True, tracking=True)
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year')
    venue = fields.Char(string='Venue')
    description = fields.Html(string='Activity Description')
    participants_count = fields.Integer(string='Number of Participants')
    outcomes = fields.Text(string='Outcome / Impact')
    date = fields.Date(string='Date / Year', tracking=True)

    evidence_ids = fields.One2many('naac.evidence', 'activity_id', string='Supporting Evidence')
    evidence_count = fields.Integer(string='Evidence Count', compute='_compute_evidence_count', store=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', tracking=True)

    verified_by = fields.Many2one('res.users', string='Verified By')
    verified_date = fields.Date(string='Verified Date')
    rejection_reason = fields.Text(string='Rejection Reason')

    @api.model
    def create(self, vals):
        if vals.get('reference', '/') == '/':
            vals['reference'] = self.env['ir.sequence'].next_by_code('naac.department.activity') or '/'
        return super().create(vals)

    @api.depends('evidence_ids')
    def _compute_evidence_count(self):
        for rec in self:
            rec.evidence_count = len(rec.evidence_ids)

    def action_submit(self):
        self.state = 'submitted'

    def action_verify(self):
        self.state = 'verified'
        self.verified_by = self.env.user.id
        self.verified_date = fields.Date.today()

    def action_reject(self):
        self.state = 'rejected'

    def action_reset_draft(self):
        self.state = 'draft'
