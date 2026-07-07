# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class PlacementDrive(models.Model):
    _name = 'placement.drive'
    _description = 'Campus Placement Drives'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'drive_date desc'

    name = fields.Char(string='Drive Name', required=True, tracking=True)
    code = fields.Char(string='Drive Code', required=True, readonly=True,
                       copy=False, default='/')

    # Company
    company_id = fields.Many2one('placement.company', string='Company',
                                 required=True, tracking=True, index=True)
    industry = fields.Selection(related='company_id.industry', string='Industry', store=True)

    # Drive Details
    drive_date = fields.Date(string='Drive Date', required=True, tracking=True)
    venue = fields.Char(string='Venue')

    # Academic Year
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year',
                                       required=True)

    # Eligibility
    eligible_program_ids = fields.Many2many('university.program', string='Eligible Programs')
    eligible_department_ids = fields.Many2many('university.department',
                                               string='Eligible Departments')

    min_cgpa = fields.Float(string='Minimum CGPA', default=6.0)
    max_backlogs = fields.Integer(string='Maximum Active Backlogs', default=0)

    eligibility_criteria = fields.Html(string='Eligibility Criteria')

    # Job Details
    job_title = fields.Char(string='Job Title/Position', required=True)
    job_description = fields.Html(string='Job Description')
    job_location = fields.Char(string='Job Location')

    # Salary Package
    ctc_min = fields.Monetary(string='CTC Min (LPA)', currency_field='currency_id')
    ctc_max = fields.Monetary(string='CTC Max (LPA)', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Positions
    total_positions = fields.Integer(string='Total Positions', default=1)

    # Selection Process
    selection_rounds = fields.Html(string='Selection Process/Rounds',
                                   help='Aptitude, Technical, HR, etc.')

    # Registration
    registration_start = fields.Date(string='Registration Start Date')
    registration_end = fields.Date(string='Registration End Date')

    # Applications
    application_ids = fields.One2many('placement.application', 'drive_id', string='Applications')
    total_applications = fields.Integer(string='Total Applications', compute='_compute_stats')
    shortlisted_count = fields.Integer(string='Shortlisted', compute='_compute_stats')

    # Offers
    offer_ids = fields.One2many('placement.offer', 'drive_id', string='Offers')
    total_offers = fields.Integer(string='Total Offers', compute='_compute_stats')

    # Coordinator
    coordinator_id = fields.Many2one('placement.coordinator', string='Placement Coordinator')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('registration_open', 'Registration Open'),
        ('registration_closed', 'Registration Closed'),
        ('scheduled', 'Scheduled'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    # Documents Required
    documents_required = fields.Html(string='Documents Required')

    # Notes
    notes = fields.Text(string='Notes')

    def action_placement_application(self):
        """Open placement applications for this drive"""
        return {
            'name': 'Applications',
            'type': 'ir.actions.act_window',
            'res_model': 'placement.application',
            'view_mode': 'list,form',
            'domain': [('drive_id', '=', self.id)],
            'context': {'default_drive_id': self.id},
        }

    def action_placement_drive(self):
        """Open shortlisted applications for this drive"""
        return {
            'name': 'Shortlisted Students',
            'type': 'ir.actions.act_window',
            'res_model': 'placement.drive',
            'view_mode': 'list,form',
            'domain': [('drive_id', '=', self.id), ('state', 'in', ['shortlisted', 'selected'])],
            'context': {'default_drive_id': self.id},
        }

    def action_placement_offer(self):
        """Open placement offers for this drive"""
        return {
            'name': 'Offers',
            'type': 'ir.actions.act_window',
            'res_model': 'placement.offer',
            'view_mode': 'list,form',
            'domain': [('drive_id', '=', self.id)],
            'context': {'default_drive_id': self.id},
        }

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Drive Code must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('code', '/') == '/':
            vals['code'] = self.env['ir.sequence'].next_by_code('placement.drive') or '/'
        return super(PlacementDrive, self).create(vals)

    @api.depends('application_ids', 'application_ids.state', 'offer_ids')
    def _compute_stats(self):
        for record in self:
            record.total_applications = len(record.application_ids)
            record.shortlisted_count = len(record.application_ids.filtered(
                lambda a: a.state in ['shortlisted', 'selected']))
            record.total_offers = len(record.offer_ids)

    def action_open_registration(self):
        self.write({'state': 'registration_open'})

    def action_close_registration(self):
        self.write({'state': 'registration_closed'})

    def action_schedule(self):
        self.write({'state': 'scheduled'})

    def action_start(self):
        self.write({'state': 'ongoing'})

    def action_complete(self):
        self.write({'state': 'completed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})