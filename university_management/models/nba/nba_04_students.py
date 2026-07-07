# -*- coding: utf-8 -*-

from odoo import models, fields, api
from dateutil.relativedelta import relativedelta
from datetime import date


class NBAC4Students(models.Model):
    _name = 'nba.c4.students'
    _description = 'NBA Criterion 4 - Student Performance Data (Tables 4A, 4B, 4C)'
    _order = 'sar_id, year_label'

    sar_id = fields.Many2one('nba.sar', string='SAR', required=True,
                             ondelete='cascade', index=True)
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year',
                                       required=True)
    year_label = fields.Selection([
        ('CAY', 'CAY (Current Academic Year)'),
        ('CAYm1', 'CAYm1 (Current Assessment Year)'),
        ('CAYm2', 'CAYm2'),
        ('CAYm3', 'CAYm3'),
        ('LYG', 'LYG (Last Year Graduate)'),
        ('LYGm1', 'LYGm1'),
        ('LYGm2', 'LYGm2'),
    ], string='Year Label', required=True)

    program_id = fields.Many2one(
        'university.program', related='sar_id.program_id', store=True
    )

    # ─── Table 4A: Admission Details ─────────────────────────────────────────
    n_sanctioned = fields.Integer(
        string='N (Sanctioned Intake)',
        compute='_compute_all', store=True
    )
    n1_first_year = fields.Integer(
        string='N1 (1st Year Admitted)', compute='_compute_all', store=True
    )
    n2_lateral = fields.Integer(
        string='N2 (Lateral Entry)', compute='_compute_all', store=True
    )
    n3_separate_div = fields.Integer(string='N3 (Separate Division)', default=0)
    n4_supernumerary = fields.Integer(
        string='N4 (Supernumerary)', compute='_compute_all', store=True
    )
    total_admitted = fields.Integer(
        string='Total Admitted (N1+N2+N3+N4)',
        compute='_compute_total_admitted', store=True
    )

    # ─── Table 4B: Multiple Entry/Exit (sub-fields as per NBA PDF) ───────────
    # Multiple Entry sub-fields
    n52_entry_yr2 = fields.Integer(
        string='N52 – Admitted in 2nd Year (Multiple Entry)', default=0
    )
    n53_entry_yr3 = fields.Integer(
        string='N53 – Admitted in 3rd Year (Multiple Entry)', default=0
    )
    n54_entry_yr4 = fields.Integer(
        string='N54 – Admitted in 4th Year (Multiple Entry)', default=0
    )
    n5_multiple_entry = fields.Integer(
        string='N5 = N52+N53+N54 (Total Multiple Entry)',
        compute='_compute_n5_n6', store=True
    )

    # Multiple Exit sub-fields
    n61_exit_yr1 = fields.Integer(
        string='N61 – Exit after 1st Year (Multiple Exit)', default=0
    )
    n62_exit_yr2 = fields.Integer(
        string='N62 – Exit after 2nd Year (Multiple Exit)', default=0
    )
    n63_exit_yr3 = fields.Integer(
        string='N63 – Exit after 3rd Year (Multiple Exit)', default=0
    )
    n6_multiple_exit = fields.Integer(
        string='N6 = N61+N62+N63 (Total Multiple Exit)',
        compute='_compute_n5_n6', store=True
    )

    # ─── Table 4C: Graduated in Stipulated Period (by year) ──────────────────
    graduated_yr1 = fields.Integer(
        string='Graduated after Year 1 (Table 4C – I Year)', default=0
    )
    graduated_yr2 = fields.Integer(
        string='Graduated after Year 2 (Table 4C – II Year)', default=0
    )
    graduated_yr3 = fields.Integer(
        string='Graduated after Year 3 (Table 4C – III Year)', default=0
    )
    graduated_yr4 = fields.Integer(
        string='Graduated after Year 4 (Table 4C – IV Year)', default=0
    )
    graduated_stipulated = fields.Integer(
        string='Total Graduated in Stipulated Period',
        compute='_compute_graduated_total', store=True
    )

    # ─── C4.1 Enrolment Ratio ────────────────────────────────────────────────
    enrolment_ratio = fields.Float(
        string='Enrolment Ratio (ER)', compute='_compute_enrolment_ratio', store=True,
        digits=(5, 4)
    )

    # ─── C4.2 Success Rate ────────────────────────────────────────────────────
    effective_admitted = fields.Integer(
        string='A (Effective Admitted)', compute='_compute_success_rate', store=True
    )
    success_rate = fields.Float(
        string='Success Rate (SR %)', compute='_compute_success_rate', store=True,
        digits=(5, 2)
    )

    # ─── C4.3/4/5 Academic Performance Index ─────────────────────────────────
    mean_cgpa_yr1 = fields.Float(string='Mean CGPA Year 1', digits=(5, 2))
    y1_passed = fields.Integer(string='Y1 Passed Students')
    y1_appeared = fields.Integer(string='Y1 Appeared Students')
    api_yr1 = fields.Float(
        string='API Year 1', compute='_compute_api', store=True, digits=(5, 4)
    )

    mean_cgpa_yr2 = fields.Float(string='Mean CGPA Year 2', digits=(5, 2))
    y2_passed = fields.Integer(string='Y2 Passed Students')
    y2_appeared = fields.Integer(string='Y2 Appeared Students')
    api_yr2 = fields.Float(
        string='API Year 2', compute='_compute_api', store=True, digits=(5, 4)
    )

    mean_cgpa_yr3 = fields.Float(string='Mean CGPA Year 3', digits=(5, 2))
    y3_passed = fields.Integer(string='Y3 Passed Students')
    y3_appeared = fields.Integer(string='Y3 Appeared Students')
    api_yr3 = fields.Float(
        string='API Year 3', compute='_compute_api', store=True, digits=(5, 4)
    )

    # ─── C4.6 Placement Index ─────────────────────────────────────────────────
    final_year_students = fields.Integer(string='FS (Final Year Students)')
    placement_placed = fields.Integer(
        string='X (Placed)', compute='_compute_all', store=True
    )
    placement_higher_studies = fields.Integer(
        string='Y (Higher Studies)', compute='_compute_all', store=True
    )
    placement_entrepreneur = fields.Integer(
        string='Z (Entrepreneurship)', compute='_compute_all', store=True
    )
    placement_index = fields.Float(
        string='Placement Index (P%)', compute='_compute_placement', store=True,
        digits=(5, 2)
    )

    # ─── Override flag ─────────────────────────────────────────────────────────
    is_manual_override = fields.Boolean(
        string='Manual Override', default=False,
        help='If checked, auto-computation will not overwrite these values'
    )

    @api.depends('n52_entry_yr2', 'n53_entry_yr3', 'n54_entry_yr4',
                 'n61_exit_yr1', 'n62_exit_yr2', 'n63_exit_yr3')
    def _compute_n5_n6(self):
        for rec in self:
            rec.n5_multiple_entry = rec.n52_entry_yr2 + rec.n53_entry_yr3 + rec.n54_entry_yr4
            rec.n6_multiple_exit = rec.n61_exit_yr1 + rec.n62_exit_yr2 + rec.n63_exit_yr3

    @api.depends('graduated_yr1', 'graduated_yr2', 'graduated_yr3', 'graduated_yr4')
    def _compute_graduated_total(self):
        for rec in self:
            rec.graduated_stipulated = (rec.graduated_yr1 + rec.graduated_yr2 +
                                        rec.graduated_yr3 + rec.graduated_yr4)

    @api.depends('n1_first_year', 'n2_lateral', 'n3_separate_div', 'n4_supernumerary')
    def _compute_total_admitted(self):
        for rec in self:
            rec.total_admitted = (rec.n1_first_year + rec.n2_lateral +
                                  rec.n3_separate_div + rec.n4_supernumerary)

    @api.depends('n1_first_year', 'n4_supernumerary', 'n_sanctioned')
    def _compute_enrolment_ratio(self):
        for rec in self:
            n = rec.n_sanctioned or rec.sar_id.sanctioned_intake or 1
            rec.enrolment_ratio = round((rec.n1_first_year + rec.n4_supernumerary) / n, 4)

    @api.depends('total_admitted', 'n5_multiple_entry', 'n6_multiple_exit',
                 'graduated_stipulated', 'n_sanctioned', 'n2_lateral')
    def _compute_success_rate(self):
        for rec in self:
            a = rec.total_admitted + rec.n5_multiple_entry - rec.n6_multiple_exit
            # NBA rule: if A < N+N2, use N+N2
            min_a = (rec.n_sanctioned or rec.sar_id.sanctioned_intake) + rec.n2_lateral
            a = max(a, min_a)
            rec.effective_admitted = a
            rec.success_rate = round((rec.graduated_stipulated / a * 100) if a else 0.0, 2)

    @api.depends('mean_cgpa_yr1', 'y1_passed', 'y1_appeared',
                 'mean_cgpa_yr2', 'y2_passed', 'y2_appeared',
                 'mean_cgpa_yr3', 'y3_passed', 'y3_appeared')
    def _compute_api(self):
        for rec in self:
            # API = (Mean CGPA/10) * (passed/appeared)
            rec.api_yr1 = round(
                (rec.mean_cgpa_yr1 / 10.0) * (rec.y1_passed / rec.y1_appeared)
                if rec.y1_appeared else 0.0, 4
            )
            rec.api_yr2 = round(
                (rec.mean_cgpa_yr2 / 10.0) * (rec.y2_passed / rec.y2_appeared)
                if rec.y2_appeared else 0.0, 4
            )
            rec.api_yr3 = round(
                (rec.mean_cgpa_yr3 / 10.0) * (rec.y3_passed / rec.y3_appeared)
                if rec.y3_appeared else 0.0, 4
            )

    @api.depends('placement_placed', 'placement_higher_studies',
                 'placement_entrepreneur', 'final_year_students',
                 'n_sanctioned', 'n2_lateral')
    def _compute_placement(self):
        for rec in self:
            fs = rec.final_year_students
            min_fs = (rec.n_sanctioned or rec.sar_id.sanctioned_intake) + rec.n2_lateral
            fs = max(fs, min_fs) if fs else min_fs
            total = rec.placement_placed + rec.placement_higher_studies + rec.placement_entrepreneur
            rec.placement_index = round((total / fs * 100) if fs else 0.0, 2)

    def _compute_all(self):
        """Auto-pull all values from existing student/exam/placement records."""
        for rec in self:
            if rec.is_manual_override or not rec.program_id or not rec.academic_year_id:
                continue
            program = rec.program_id
            year = rec.academic_year_id

            # N (sanctioned intake)
            rec.n_sanctioned = program.total_seats or rec.sar_id.sanctioned_intake

            # N1: first-year admissions
            admissions = self.env['student.admission'].search([
                ('program_id', '=', program.id),
                ('academic_year_id', '=', year.id),
                ('state', '=', 'enrolled'),
            ])
            rec.n1_first_year = len(admissions)

            # N2: lateral entry
            lateral = self.env['student.student'].search([
                ('program_id', '=', program.id),
                ('academic_year_id', '=', year.id),
            ])
            rec.n2_lateral = 0  # Will be derived from admission entry_type when available

            # N4: supernumerary (EWS, NRI, etc.) - kept 0 unless specific quota field exists
            rec.n4_supernumerary = 0

            # Graduated in stipulated period: students with all semesters cleared
            # Note: graduated_yr1/yr2/yr3/yr4 should be entered manually or set via
            # separate logic. Here we estimate graduated_yr4 from student records.
            graduated = self.env['student.student'].search([
                ('program_id', '=', program.id),
            ])
            est = min(len(graduated), rec.n1_first_year)
            # Only set yr4 if not already manually entered
            if not rec.graduated_yr4:
                rec.graduated_yr4 = est

            # Placement data from placement offers
            offers = self.env['placement.offer'].search([
                ('student_id.program_id', '=', program.id),
            ])
            rec.placement_placed = len(offers)
            rec.placement_higher_studies = 0
            rec.placement_entrepreneur = 0
            rec.final_year_students = rec.n1_first_year

            # Academic performance: pull exam result averages
            results = self.env['examination.result'].search([
                ('program_id', '=', program.id),
                ('academic_year_id', '=', year.id),
                ('is_absent', '=', False),
            ])
            if results:
                all_pcts = [r.percentage for r in results if r.percentage > 0]
                if all_pcts:
                    avg_pct = sum(all_pcts) / len(all_pcts)
                    rec.mean_cgpa_yr1 = round(avg_pct / 10.0, 2)
                    rec.y1_passed = sum(1 for r in results if r.is_pass)
                    rec.y1_appeared = len(results)


# ─────────────────────────────────────────────────────────────────────────────
# C4.7 Professional Activities models (within nba_c4_students.py per plan)
# ─────────────────────────────────────────────────────────────────────────────

class NBAC4ProfSociety(models.Model):
    """Table 4.7.1.1: Active Professional Societies / Bodies / Chapters / Clubs"""
    _name = 'nba.c4.prof.society'
    _description = 'NBA C4.7.1.1 - Professional Societies & Clubs'
    _order = 'sar_id, name'

    sar_id = fields.Many2one('nba.sar', string='SAR', required=True,
                             ondelete='cascade', index=True)
    name = fields.Char(string='Name of Society/Body/Chapter/Club', required=True)
    society_type = fields.Selection([
        ('professional_body', 'Professional Body (IEEE, ISTE, CSI, etc.)'),
        ('chapter', 'Student Chapter'),
        ('club', 'Departmental Club'),
        ('other', 'Other'),
    ], string='Type', default='professional_body')
    level = fields.Selection([
        ('national', 'National'), ('international', 'International'),
    ], string='Level', default='national')
    year_established = fields.Char(string='Year Established')
    faculty_coordinator = fields.Many2one('faculty.faculty', string='Faculty Coordinator')
    is_active = fields.Boolean(string='Active', default=True)


class NBAC4ProfEvent(models.Model):
    """Table 4.7.1.2: Events Organized by Professional Societies"""
    _name = 'nba.c4.prof.event'
    _description = 'NBA C4.7.1.2 - Events by Professional Societies'
    _order = 'sar_id, year_label, event_date'

    sar_id = fields.Many2one('nba.sar', string='SAR', required=True,
                             ondelete='cascade', index=True)
    year_label = fields.Selection([
        ('CAYm1', 'CAYm1'), ('CAYm2', 'CAYm2'), ('CAYm3', 'CAYm3'),
    ], string='Year', required=True)
    society_id = fields.Many2one('nba.c4.prof.society', string='Society/Club')
    society_name = fields.Char(string='Society / Club Name')
    event_name = fields.Char(string='Event Name', required=True)
    event_level = fields.Selection([
        ('national', 'National'), ('international', 'International'),
        ('state', 'State'), ('institute', 'Institute'),
    ], string='Level', default='national')
    event_date = fields.Date(string='Date')
    participants_count = fields.Integer(string='Participants')


class NBAC4StudentEvent(models.Model):
    """Table 4.7.2.1: Student Participation in Professional Events"""
    _name = 'nba.c4.student.event'
    _description = 'NBA C4.7.2.1 - Student Professional Events'
    _order = 'sar_id, year_label, event_date'

    sar_id = fields.Many2one('nba.sar', string='SAR', required=True,
                             ondelete='cascade', index=True)
    year_label = fields.Selection([
        ('CAYm1', 'CAYm1'), ('CAYm2', 'CAYm2'), ('CAYm3', 'CAYm3'),
    ], string='Year', required=True)
    student_id = fields.Many2one('student.student', string='Student')
    student_name = fields.Char(string='Student Name', required=True)
    semester = fields.Char(string='Semester')
    event_name = fields.Char(string='Event Name', required=True)
    event_type = fields.Selection([
        ('hackathon', 'Hackathon'), ('codeathon', 'Codeathon'),
        ('ideathon', 'Ideathon'), ('paper_presentation', 'Paper Presentation'),
        ('project_exhibition', 'Project Exhibition'), ('other', 'Other'),
    ], string='Type', default='hackathon')
    event_level = fields.Selection([
        ('state', 'State'), ('national', 'National'), ('international', 'International'),
    ], string='Level', default='national')
    event_date = fields.Date(string='Date')
    award_name = fields.Char(string='Award (if any)')
    organizer = fields.Char(string='Organizing Institute')


class NBAC4DeptPublication(models.Model):
    """Table 4.7.3.1: Dept Journals / Magazines / Newsletters"""
    _name = 'nba.c4.dept.publication'
    _description = 'NBA C4.7.3.1 - Dept Journals & Newsletters'
    _order = 'sar_id, year_label'

    sar_id = fields.Many2one('nba.sar', string='SAR', required=True,
                             ondelete='cascade', index=True)
    year_label = fields.Selection([
        ('CAYm1', 'CAYm1'), ('CAYm2', 'CAYm2'), ('CAYm3', 'CAYm3'),
    ], string='Year', required=True)
    publication_name = fields.Char(string='Name of Journal/Magazine/Newsletter', required=True)
    editor_name = fields.Char(string='Editor Name')
    student_names = fields.Text(string='Student Names & Semester')
    no_of_issues = fields.Integer(string='No. of Issues')
    volume_no = fields.Char(string='Volume No.')
    format_type = fields.Selection([
        ('hard_copy', 'Hard Copy'), ('soft_copy', 'Soft Copy'), ('both', 'Both'),
    ], string='Format', default='both')


class NBAC4StudentPublication(models.Model):
    """Table 4.7.4.1: Student Publications in Journals/Conferences"""
    _name = 'nba.c4.student.publication'
    _description = 'NBA C4.7.4.1 - Student Research Publications'
    _order = 'sar_id, year_label, publication_date'

    sar_id = fields.Many2one('nba.sar', string='SAR', required=True,
                             ondelete='cascade', index=True)
    year_label = fields.Selection([
        ('CAYm1', 'CAYm1'), ('CAYm2', 'CAYm2'), ('CAYm3', 'CAYm3'),
    ], string='Year', required=True)
    student_id = fields.Many2one('student.student', string='Student')
    student_name = fields.Char(string='Student Name & Semester', required=True)
    publisher_name = fields.Char(string='Publisher', required=True)
    journal_conference = fields.Char(string='Journal / Conference Name', required=True)
    publication_type = fields.Selection([
        ('journal', 'Journal'), ('conference', 'Conference'), ('book_chapter', 'Book Chapter'),
    ], string='Type', default='journal')
    volume_no = fields.Char(string='Volume No.')
    issue_no = fields.Char(string='Issue No.')
    doi = fields.Char(string='DOI')
    publication_date = fields.Date(string='Date')
    award_name = fields.Char(string='Award (if any)')
    indexed_in = fields.Selection([
        ('scopus', 'Scopus'), ('wos', 'Web of Science'),
        ('ugc', 'UGC Listed'), ('other', 'Other'),
    ], string='Indexed In')
    faculty_guide = fields.Many2one('faculty.faculty', string='Faculty Guide')