# -*- coding: utf-8 -*-

from odoo import models, fields, api


class NAACFacultyResearch(models.Model):
    _name = 'naac.faculty.research'
    _description = 'NAAC Faculty Research / Contribution'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc'

    name = fields.Char(string='Title', required=True, tracking=True)
    faculty_id = fields.Many2one('faculty.faculty', string='Faculty', required=True,
                                  tracking=True, index=True)
    department_id = fields.Many2one('university.department', string='Department',
                                     related='faculty_id.department_id', store=True)

    research_type = fields.Selection([
        ('journal_paper', 'Journal Paper'),
        ('conference_paper', 'Conference Paper'),
        ('book', 'Book'),
        ('book_chapter', 'Book Chapter'),
        ('patent_filed', 'Patent Filed'),
        ('patent_granted', 'Patent Granted'),
        ('research_grant', 'Research Grant'),
        ('consultancy', 'Consultancy'),
        ('funded_project', 'Funded Research Project'),
    ], string='Research Type', required=True, tracking=True)

    journal_conference = fields.Char(string='Journal / Conference Name')
    publisher = fields.Char(string='Publisher')
    issn_isbn = fields.Char(string='ISSN / ISBN')
    doi = fields.Char(string='DOI / URL')

    date = fields.Date(string='Date / Year', tracking=True)
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year')

    # Research Grant / Consultancy
    funding_agency = fields.Char(string='Funding Agency')
    amount = fields.Monetary(string='Amount (INR)', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Patent
    patent_number = fields.Char(string='Patent Number')
    patent_office = fields.Char(string='Patent Office')

    # NAAC link
    criterion_id = fields.Many2one('naac.criterion', string='NAAC Criterion',
                                    default=lambda self: self.env['naac.criterion'].search(
                                        [('criterion_number', '=', 3)], limit=1))
    metric_id = fields.Many2one('naac.metric', string='Metric',
                                 domain="[('criterion_id', '=', criterion_id)]")

    evidence_document = fields.Binary(string='Supporting Document', attachment=True)
    evidence_filename = fields.Char(string='Document Filename')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('verified', 'Verified'),
    ], string='Status', default='draft', tracking=True)

    co_author_ids = fields.Many2many('faculty.faculty',
                                      'naac_research_coauthor_rel',
                                      'research_id', 'faculty_id',
                                      string='Co-Authors / Co-Investigators')
    student_author_ids = fields.Many2many('student.student',
                                           'naac_research_student_rel',
                                           'research_id', 'student_id',
                                           string='Student Co-Authors')

    scopus_indexed = fields.Boolean(string='Scopus Indexed')
    wos_indexed = fields.Boolean(string='WoS Indexed')
    ugc_listed = fields.Boolean(string='UGC Listed')

    impact_factor = fields.Float(string='Impact Factor', digits=(5, 3))

    notes = fields.Text(string='Notes')

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_verify(self):
        self.write({'state': 'verified'})
