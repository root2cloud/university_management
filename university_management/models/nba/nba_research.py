# -*- coding: utf-8 -*-

from odoo import models, fields, api


class NBAResearch(models.Model):
    _name = 'nba.research'
    _description = 'NBA Faculty Research, Publications, FDP & Projects'
    _inherit = ['mail.thread']
    _order = 'sar_id, academic_year_id desc, research_type'

    name = fields.Char(string='Reference', readonly=True, copy=False, default='/')
    sar_id = fields.Many2one(
        'nba.sar', string='SAR',
        compute='_compute_sar_id', store=True, readonly=False, precompute=True,
        ondelete='cascade', index=True, tracking=True,
        help='Automatically resolved from the faculty department and academic '
             'year. You can still override it manually.'
    )
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
    ], string='Assessment Year',
        compute='_compute_year_label', store=True, readonly=False)

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

    # ─── SAR resolution ──────────────────────────────────────────────────────
    @api.model
    def _sar_year_ids(self, sar):
        """All academic years covered by a SAR (CAY, CAYm1, CAYm2)."""
        return {
            y.id for y in (sar.academic_year_id | sar.caym1_id | sar.caym2_id)
            if y
        }

    @api.model
    def _find_sar(self, faculty, academic_year):
        """Return the best matching nba.sar for a faculty + academic year.

        Priority:
          1. SAR of the faculty's department (by id) that covers the year
          2. SAR of an allied department (by id) that covers the year
          3. Most recent SAR of the faculty's / allied department (by id)
          4. Same as 1-3 but matching the department by name instead of id
             (covers duplicate 'university.department' master records that
             share a name but not an id - e.g. one used on Faculty, another
             used on the Program linked to the SAR)
          5. If there is exactly one nba.sar in the whole system, use it
          6. Otherwise, the most recently created SAR that is still open
             (draft / data_entry / under_review), system-wide
        """
        Sar = self.env['nba.sar']
        department = faculty.department_id
        candidates = Sar

        if department:
            own = Sar.search([('department_id', '=', department.id)],
                             order='create_date desc')
            allied = Sar.search([('allied_dept_ids', 'in', department.id),
                                 ('id', 'not in', own.ids)],
                                order='create_date desc')
            candidates = own + allied

        if not candidates and department and department.name:
            # Fallback for duplicate department records sharing the same name
            own = Sar.search([('department_id.name', '=', department.name)],
                             order='create_date desc')
            allied = Sar.search(
                [('allied_dept_ids.name', '=', department.name),
                 ('id', 'not in', own.ids)],
                order='create_date desc'
            )
            candidates = own + allied

        if candidates:
            if academic_year:
                for sar in candidates:
                    if academic_year.id in self._sar_year_ids(sar):
                        return sar
            # No year match: prefer a SAR still being worked on
            open_sars = candidates.filtered(
                lambda s: s.state in ('draft', 'data_entry', 'under_review')
            )
            return (open_sars or candidates)[0]

        # Still nothing: last-resort, system-wide fallback so a single-SAR
        # institution never ends up with a blank field.
        all_sars = Sar.search([], order='create_date desc')
        if len(all_sars) == 1:
            return all_sars
        open_sars = all_sars.filtered(
            lambda s: s.state in ('draft', 'data_entry', 'under_review')
        )
        return (open_sars or all_sars)[:1]

    @api.depends('faculty_id', 'faculty_id.department_id', 'academic_year_id')
    def _compute_sar_id(self):
        for rec in self:
            if not rec.faculty_id:
                rec.sar_id = rec.sar_id or False
                continue

            current = rec.sar_id
            if current:
                dept = rec.faculty_id.department_id
                dept_ok = dept and dept.id in (
                    [current.department_id.id] + current.allied_dept_ids.ids
                )
                year_ok = (
                    not rec.academic_year_id
                    or rec.academic_year_id.id in self._sar_year_ids(current)
                )
                if dept_ok and year_ok:
                    # Manual/previous choice is still valid - keep it
                    continue

            sar = self._find_sar(rec.faculty_id, rec.academic_year_id)
            rec.sar_id = sar or current or False

    @api.depends('sar_id', 'academic_year_id')
    def _compute_year_label(self):
        for rec in self:
            sar, year = rec.sar_id, rec.academic_year_id
            if not sar or not year:
                continue
            if sar.caym1_id and year.id == sar.caym1_id.id:
                rec.year_label = 'CAYm1'
            elif sar.caym2_id and year.id == sar.caym2_id.id:
                rec.year_label = 'CAYm2'

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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('nba.research') or '/'
        records = super().create(vals_list)
        # Safety net: records created from the faculty form (where sar_id is
        # not on screen) still get their SAR filled in.
        records._fill_missing_sar()
        return records

    def _fill_missing_sar(self):
        """Resolve the SAR for records that do not have one yet."""
        for rec in self.filtered(lambda r: not r.sar_id and r.faculty_id):
            sar = self._find_sar(rec.faculty_id, rec.academic_year_id)
            if sar:
                rec.sar_id = sar.id

    @api.model
    def action_fill_missing_sar(self):
        """Backfill the SAR on all existing records that are missing it."""
        self.search([('sar_id', '=', False)])._fill_missing_sar()
        return True