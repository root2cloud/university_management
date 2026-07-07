# -*- coding: utf-8 -*-

from odoo import models, fields, api


class NBAResearch(models.Model):
    _name = 'nba.research'
    _description = 'NBA Faculty Research, Publications, FDP & Projects'
    _inherit = ['mail.thread']
    _order = 'sar_id, academic_year_id desc, research_type'

    name = fields.Char(string='Reference', readonly=True, copy=False, default='/')
    sar_id = fields.Many2one('nba.sar', string='SAR', required=True,
                             ondelete='cascade', index=True)
    faculty_id = fields.Many2one('faculty.faculty', string='Faculty (PI)',
                                 required=True, index=True, tracking=True)
    department_id = fields.Many2one(
        'university.department', string='Department',
        related='faculty_id.department_id', store=True
    )
    academic_year_id = fields.Many2one('university.academic.year',
                                       string='Academic Year', index=True)
    year_label = fields.Selection([
        ('CAYm1', 'CAYm1'),
        ('CAYm2', 'CAYm2'),
        ('CAYm3', 'CAYm3'),
    ], string='Assessment Year')

    research_type = fields.Selection([
        ('journal', 'Journal Paper (Scopus/WoS)'),
        ('conference', 'Conference Paper'),
        ('book', 'Book'),
        ('book_chapter', 'Book Chapter'),
        ('patent', 'Patent'),
        ('funded_project', 'Funded Research Project'),
        ('consultancy', 'Consultancy Project'),
        ('seed_money', 'Seed Money / Internal Grant'),
        ('fdp_attended', 'FDP/STTP Attended'),
        ('fdp_organized', 'FDP/STTP Organized'),
        ('mooc_certified', 'MOOC Certification'),
        ('mooc_developed', 'MOOC Course Developed'),
        ('industry_collab', 'Industry Collaboration / Internship'),
        ('student_innovation', 'Student Innovation Project Mentored'),
        ('prof_society', 'Professional Society Membership'),
        ('phd_guidance', 'PhD Guidance'),
    ], string='Type', required=True, tracking=True)

    title = fields.Char(string='Title', required=True)
    publisher_journal = fields.Char(string='Publisher / Journal / Agency')
    doi = fields.Char(string='DOI / Patent No.')
    indexed_in = fields.Selection([
        ('scopus', 'Scopus'),
        ('wos', 'Web of Science'),
        ('ugc', 'UGC Listed'),
        ('other', 'Other'),
    ], string='Indexed In')
    publication_date = fields.Date(string='Publication / Grant Date')

    # Financial fields
    amount_lacs = fields.Float(string='Amount (Lacs)', digits=(10, 4))
    amount_utilized_lacs = fields.Float(string='Amount Utilized (Lacs)', digits=(10, 4))

    # FDP details
    fdp_duration_days = fields.Integer(string='FDP Duration (Days)')
    fdp_is_external = fields.Boolean(
        string='External FDP',
        default=True,
        help='External FDPs are counted for C6.1.2; internal ones are not'
    )
    fdp_organizer = fields.Char(string='Organized By')
    fdp_location = fields.Char(string='Location')
    fdp_points = fields.Float(
        string='FDP Points', compute='_compute_fdp_points', store=True
    )

    # Patent details
    patent_status = fields.Selection([
        ('granted', 'Granted'),
        ('published', 'Published'),
        ('filed', 'Filed'),
    ], string='Patent Status')

    # Co-investigators
    co_pi_ids = fields.Many2many(
        'faculty.faculty', 'nba_research_copi_rel', 'research_id', 'faculty_id',
        string='Co-PIs'
    )

    # Project duration
    duration_months = fields.Integer(string='Duration (Months)')
    funding_agency = fields.Char(string='Funding Agency')

    source = fields.Selection([
        ('auto_pulled', 'Auto-Pulled'),
        ('manual', 'Manual Entry'),
    ], string='Data Source', default='manual')

    notes = fields.Text(string='Notes')

    @api.depends('fdp_duration_days', 'fdp_is_external')
    def _compute_fdp_points(self):
        for rec in self:
            if rec.research_type not in ('fdp_attended', 'fdp_organized'):
                rec.fdp_points = 0.0
                continue
            if not rec.fdp_is_external:
                rec.fdp_points = 0.0
                continue
            # C6.1.2: 2-5 days = 3 pts, >5 days = 5 pts (max 5 per faculty)
            if rec.fdp_duration_days >= 5:
                rec.fdp_points = 5.0
            elif rec.fdp_duration_days >= 2:
                rec.fdp_points = 3.0
            else:
                rec.fdp_points = 0.0

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('nba.research') or '/'
        return super().create(vals)