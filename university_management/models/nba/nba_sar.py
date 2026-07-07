# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class NBASAR(models.Model):
    _name = 'nba.sar'
    _description = 'NBA Self-Assessment Report (SAR) - GAPC V4.0'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # ─── Identity ────────────────────────────────────────────────────────────
    name = fields.Char(
        string='SAR Reference', readonly=True, copy=False, default='/',
        tracking=True
    )
    program_id = fields.Many2one(
        'university.program', string='Program', required=True,
        tracking=True, index=True,
        help='The UG Engineering program applying for NBA accreditation'
    )
    department_id = fields.Many2one(
        'university.department', string='Department',
        compute='_compute_department', store=True
    )
    allied_dept_ids = fields.Many2many(
        'university.department', 'nba_sar_allied_dept_rel',
        'sar_id', 'dept_id',
        string='Allied Departments',
        help='Allied/cluster departments for SFR and faculty computation'
    )
    nba_coordinator_id = fields.Many2one(
        'res.users', string='NBA Coordinator',
        default=lambda self: self.env.uid
    )

    # ─── Academic Years (CAY, CAYm1, CAYm2) ──────────────────────────────────
    academic_year_id = fields.Many2one(
        'university.academic.year', string='CAY (Current Academic Year)',
        required=True, tracking=True
    )
    cay_id = fields.Many2one(
        'university.academic.year', string='CAY',
        related='academic_year_id', store=True
    )
    caym1_id = fields.Many2one(
        'university.academic.year', string='CAYm1 (Assessment Year)',
        required=True, tracking=True
    )
    caym2_id = fields.Many2one(
        'university.academic.year', string='CAYm2',
        required=True, tracking=True
    )
    lyg_id = fields.Many2one(
        'university.academic.year', string='LYG (Last Year Graduate)',
        tracking=True
    )
    lygm1_id = fields.Many2one(
        'university.academic.year', string='LYGm1',
        tracking=True
    )
    lygm2_id = fields.Many2one(
        'university.academic.year', string='LYGm2',
        tracking=True
    )

    # ─── Program Details ──────────────────────────────────────────────────────
    sanctioned_intake = fields.Integer(
        string='Sanctioned Intake (N)', default=60,
        help='AICTE approved intake for the program'
    )
    accreditation_cycle = fields.Char(
        string='Accreditation Cycle', default='2025-26',
        help='e.g., 2025-26'
    )

    # ─── Workflow State ───────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft', 'Draft'),
        ('data_entry', 'Data Entry'),
        ('under_review', 'Under Review'),
        ('submitted', 'Submitted to NBA'),
        ('accredited', 'Accredited'),
    ], string='Status', default='draft', tracking=True)

    # ─── Score Fields (per criterion) ────────────────────────────────────────
    c1_score = fields.Float(string='C1 Score', compute='_compute_c1_score', store=True)
    c2_score = fields.Float(string='C2 Score', compute='_compute_c2_score', store=True)
    c3_score = fields.Float(string='C3 Score', compute='_compute_c3_score', store=True)
    c4_score = fields.Float(string='C4 Score', compute='_compute_c4_score', store=True)
    c5_score = fields.Float(string='C5 Score', compute='_compute_c5_score', store=True)
    c6_score = fields.Float(string='C6 Score', compute='_compute_c6_score', store=True)
    c7_score = fields.Float(string='C7 Score', default=0.0)
    c8_score = fields.Float(string='C8 Score', default=0.0)
    c9_score = fields.Float(string='C9 Score', default=0.0)

    total_score = fields.Float(
        string='Total Score /1000', compute='_compute_total_score', store=True
    )
    readiness_pct = fields.Float(
        string='Readiness %', compute='_compute_total_score', store=True
    )
    last_computed_on = fields.Datetime(string='Last Computed On', readonly=True)

    # ─── Related Records (One2many) ───────────────────────────────────────────
    peo_ids = fields.One2many('nba.peo', 'sar_id', string='Program Educational Objectives')
    pso_ids = fields.One2many('nba.pso', 'sar_id', string='Program Specific Outcomes')
    co_ids = fields.One2many('nba.co', 'sar_id', string='Course Outcomes')
    research_ids = fields.One2many('nba.research', 'sar_id', string='Research & FDP')
    evidence_ids = fields.One2many('nba.evidence', 'sar_id', string='Evidence Documents')
    c4_student_ids = fields.One2many('nba.c4.students', 'sar_id', string='C4 Student Data')
    c5_faculty_ids = fields.One2many('nba.c5.faculty', 'sar_id', string='C5 Faculty Data')
    lab_ids = fields.One2many('nba.lab.info', 'sar_id', string='Laboratories')
    fdp_ids = fields.One2many('nba.fdp', 'sar_id', string='FDP / Visiting Faculty')
    c1_course_scheme_ids = fields.One2many(
        'nba.c1.course.scheme', 'sar_id', string='C1.2.2 Course Teaching Scheme (L/T/P/SL)'
    )
    c1_curriculum_ids = fields.One2many(
        'nba.c1.curriculum', 'sar_id', string='C1.2.3 Curriculum Components'
    )
    # ─── C4.7 Professional Activities ─────────────────────────────────────────
    prof_society_ids = fields.One2many(
        'nba.c4.prof.society', 'sar_id', string='4.7.1 Professional Societies/Clubs'
    )
    prof_event_ids = fields.One2many(
        'nba.c4.prof.event', 'sar_id', string='4.7.1 Events Organized'
    )
    student_event_ids = fields.One2many(
        'nba.c4.student.event', 'sar_id', string='4.7.2 Student Professional Events'
    )
    dept_publication_ids = fields.One2many(
        'nba.c4.dept.publication', 'sar_id', string='4.7.3 Dept Journals/Newsletters'
    )
    student_publication_ids = fields.One2many(
        'nba.c4.student.publication', 'sar_id', string='4.7.4 Student Publications'
    )

    # ─── Criterion 1 Narrative Fields ─────────────────────────────────────────
    c1_vision_mission = fields.Html(string='1.1 Vision, Mission & PEOs')
    c1_curriculum_structure = fields.Html(string='1.2 Curriculum Structure')
    c1_po_pso_mapping = fields.Html(string='1.3 PO/PSO Mapping')
    c1_education_reforms = fields.Html(string='1.2.4 Education Reforms')

    # ─── Criterion 2 Narrative Fields ─────────────────────────────────────────
    c2_teaching_quality = fields.Html(string='2.1 Teaching & Learning Quality')
    c2_capstone_quality = fields.Html(string='2.2 Capstone Project Quality')
    c2_internship_summary = fields.Html(string='2.3 Internship / Industrial Training')
    c2_seminar_projects = fields.Html(string='2.4 Seminars & Mini Projects')
    c2_case_studies = fields.Html(string='2.5 Case Studies')
    c2_mooc_summary = fields.Html(string='2.6 SWAYAM/NPTEL/MOOC')
    c2_sdg_activities = fields.Html(string='2.7 Complex Engineering + SDGs')
    c2_industry_partnerships = fields.Html(string='2.8 Industry-Institute Partnerships')

    # ─── Criterion 3 Summary ──────────────────────────────────────────────────
    c3_assessment_tools = fields.Html(string='3.1-3.6 Assessment Tools & Evidence')
    c3_indirect_attainment = fields.Html(string='3.8.2 Indirect PO Attainment (Survey Data)')

    # ─── Criterion 7 Narrative ────────────────────────────────────────────────
    c7_narrative = fields.Html(string='7. Facilities Narrative')
    c7_safety_measures = fields.Html(string='7.4 Safety Measures')

    # ─── Criterion 8 Narrative ────────────────────────────────────────────────
    c8_co_improvement_actions = fields.Html(string='8.1.1 CO Improvement Actions')
    c8_po_improvement_actions = fields.Html(string='8.1.2 PO/PSO Improvement Actions')
    c8_academic_audit = fields.Html(string='8.2 Academic Audit')

    # ─── Criterion 9 Narrative ────────────────────────────────────────────────
    c9_mentoring_system = fields.Html(string='9.2 Mentoring System')
    c9_feedback_analysis = fields.Html(string='9.3 Feedback Analysis')
    c9_training_placement = fields.Html(string='9.4 Training & Placement')
    c9_startup_entrepreneurship = fields.Html(string='9.5 Startup & Entrepreneurship')
    c9_governance = fields.Html(string='9.6 Governance & Transparency')
    c9_sdg_initiatives = fields.Html(string='9.11 SDG Initiatives')
    c9_innovative_initiatives = fields.Html(string='9.12 Innovative Educational Initiatives')
    c9_fpads = fields.Html(string='9.13 Faculty Performance Appraisal (FPADS)')
    c9_outreach = fields.Html(string='9.14 Outreach Activities')

    # ─── Smart Button Counts ──────────────────────────────────────────────────
    evidence_count = fields.Integer(compute='_compute_counts', string='Evidence')
    co_count = fields.Integer(compute='_compute_counts', string='COs Defined')
    research_count = fields.Integer(compute='_compute_counts', string='Research/FDP')
    faculty_count = fields.Integer(compute='_compute_counts', string='Faculty')
    student_count = fields.Integer(compute='_compute_counts', string='Students')

    # ─── Generated PDF ────────────────────────────────────────────────────────
    sar_pdf = fields.Binary(string='Generated SAR PDF', attachment=True)
    sar_pdf_filename = fields.Char(string='SAR PDF Filename')

    # ─── Notes ────────────────────────────────────────────────────────────────
    notes = fields.Text(string='Internal Notes')

    # ════════════════════════════════════════════════════════════════════════════
    # Compute Methods
    # ════════════════════════════════════════════════════════════════════════════

    @api.depends('program_id')
    def _compute_department(self):
        for rec in self:
            rec.department_id = rec.program_id.department_id if rec.program_id else False

    @api.depends('evidence_ids', 'co_ids', 'research_ids')
    def _compute_counts(self):
        for rec in self:
            rec.evidence_count = len(rec.evidence_ids)
            rec.co_count = len(rec.co_ids)
            rec.research_count = len(rec.research_ids)
            # Faculty count from dept
            if rec.department_id:
                rec.faculty_count = self.env['faculty.faculty'].search_count([
                    ('department_id', '=', rec.department_id.id)
                ])
            else:
                rec.faculty_count = 0
            # Student count from program
            if rec.program_id:
                rec.student_count = self.env['student.student'].search_count([
                    ('program_id', '=', rec.program_id.id)
                ])
            else:
                rec.student_count = 0

    @api.depends('peo_ids', 'pso_ids', 'co_ids', 'c1_vision_mission',
                 'c1_curriculum_structure', 'c1_education_reforms',
                 'c1_po_pso_mapping', 'c1_course_scheme_ids', 'c1_curriculum_ids')
    def _compute_c1_score(self):
        for rec in self:
            score = 0.0

            # ── 1.1 Vision, Mission & PEOs (35 marks total) ──────────────────
            # 1.1.1 Vision & Mission statement (5 marks)
            if rec.c1_vision_mission:
                score += 5.0
            # 1.1.2 PEOs defined: 3-5 PEOs = 5 marks
            peo_count = len(rec.peo_ids)
            if peo_count >= 3:
                score += 5.0
            # 1.1.3 Process of defining V/M/PEOs (10 marks) — narrative field
            if rec.c1_vision_mission and len(rec.c1_vision_mission) > 200:
                score += 10.0  # Counts as process documented if substantial
            # 1.1.4 Dissemination (5 marks) — covered by c1_vision_mission length
            if rec.c1_vision_mission and len(rec.c1_vision_mission) > 400:
                score += 5.0
            # 1.1.5 PEO-Mission mapping (10 marks) — needs at least 3 PEOs with correlations
            peos_with_mapping = rec.peo_ids.filtered(
                lambda p: any([p.m1_corr != '0', p.m2_corr != '0',
                               p.m3_corr != '0', p.m4_corr != '0', p.m5_corr != '0'])
            )
            if len(peos_with_mapping) >= 3:
                score += 10.0
            elif len(peos_with_mapping) >= 1:
                score += 5.0

            # ── 1.2 Curriculum Structure & Features (30 marks total) ─────────
            # 1.2.1 Curriculum development process (10 marks)
            if rec.c1_curriculum_structure:
                score += 10.0
            # 1.2.2 Curriculum structure table L/T/P/SL (10 marks)
            if rec.c1_course_scheme_ids:
                score += 10.0
            # 1.2.3 Curriculum components table (5 marks)
            if rec.c1_curriculum_ids:
                score += 5.0
            # 1.2.4 Education reforms (5 marks)
            if rec.c1_education_reforms:
                score += 5.0

            # ── 1.3 PO, PSO and Mapping with Courses (20 marks total) ────────
            # 1.3.1 PSOs defined: up to 3 (5 marks)
            pso_count = len(rec.pso_ids)
            if pso_count >= 1:
                score += 5.0
            # 1.3.2 Course-PO mapping (15 marks) — need COs with matrix entries
            cos_with_matrix = rec.co_ids.filtered(lambda c: c.matrix_ids)
            if len(cos_with_matrix) >= 10:
                score += 15.0
            elif len(cos_with_matrix) >= 5:
                score += 10.0
            elif len(cos_with_matrix) >= 1:
                score += 5.0

            # ── 1.4 Course Outcomes & Articulation Matrix (30 marks total) ───
            # 1.4.1 CO statements: max 6 per course per semester (15 marks)
            co_count = len(rec.co_ids)
            if co_count >= 24:   # ~4 courses × 6 COs across multiple sems
                score += 15.0
            elif co_count >= 12:
                score += 10.0
            elif co_count >= 6:
                score += 7.0
            elif co_count >= 1:
                score += 3.0
            # 1.4.2 Course Articulation Matrix with CO-PO correlations (15 marks)
            cos_with_full_matrix = rec.co_ids.filtered(
                lambda c: c.matrix_ids and any(
                    int(m.po1 or '0') + int(m.po2 or '0') + int(m.po3 or '0') > 0
                    for m in c.matrix_ids
                )
            )
            if len(cos_with_full_matrix) >= 10:
                score += 15.0
            elif len(cos_with_full_matrix) >= 5:
                score += 10.0
            elif len(cos_with_full_matrix) >= 1:
                score += 5.0

            # ── 1.5 Program Articulation Matrix (5 marks) ────────────────────
            prog_arts = self.env['nba.program.articulation'].search([
                ('sar_id', '=', rec.id)
            ])
            if prog_arts:
                score += 5.0

            rec.c1_score = min(score, 120.0)

    @api.depends('c2_teaching_quality', 'c2_capstone_quality', 'c2_internship_summary')
    def _compute_c2_score(self):
        for rec in self:
            score = 0.0
            if rec.c2_teaching_quality:
                score += 20.0
            if rec.c2_capstone_quality:
                score += 25.0
            if rec.c2_internship_summary:
                score += 10.0
            if rec.c2_seminar_projects:
                score += 10.0
            if rec.c2_case_studies:
                score += 10.0
            if rec.c2_mooc_summary:
                score += 10.0
            if rec.c2_sdg_activities:
                score += 20.0
            if rec.c2_industry_partnerships:
                score += 15.0
            rec.c2_score = min(score, 120.0)

    @api.depends('co_ids')
    def _compute_c3_score(self):
        for rec in self:
            score = 0.0
            cos_with_attainment = rec.co_ids.filtered(
                lambda c: c.attainment_overall > 0
            )
            if cos_with_attainment:
                avg_attainment = sum(c.attainment_overall for c in cos_with_attainment) / len(cos_with_attainment)
                # Scale to 25 marks for CO attainment
                score += min(25.0, avg_attainment / 4.0)
            if rec.c3_assessment_tools:
                score += 30.0
            if rec.c3_indirect_attainment:
                score += 25.0
            rec.c3_score = min(score, 120.0)

    @api.depends('c4_student_ids')
    def _compute_c4_score(self):
        for rec in self:
            score = 0.0
            if rec.c4_student_ids:
                # Enrolment ratio (20 marks)
                cay_records = rec.c4_student_ids.filtered(
                    lambda r: r.year_label in ('CAY', 'CAYm1', 'CAYm2')
                )
                if cay_records:
                    avg_er = sum(r.enrolment_ratio for r in cay_records) / len(cay_records)
                    if avg_er >= 0.9:
                        score += 20.0
                    elif avg_er >= 0.8:
                        score += 17.0
                    elif avg_er >= 0.7:
                        score += 14.0
                    elif avg_er >= 0.6:
                        score += 11.0
                    elif avg_er >= 0.5:
                        score += 8.0
                    elif avg_er >= 0.4:
                        score += 5.0

                # Success rate (15 marks)
                lyg_records = rec.c4_student_ids.filtered(
                    lambda r: r.year_label in ('LYG', 'LYGm1', 'LYGm2')
                )
                if lyg_records:
                    avg_sr = sum(r.success_rate for r in lyg_records) / len(lyg_records)
                    score += min(15.0, 1.5 * avg_sr / 10.0)

                # Placement index (30 marks)
                if lyg_records:
                    avg_p = sum(r.placement_index for r in lyg_records) / len(lyg_records)
                    score += min(30.0, 0.3 * avg_p)

                # Academic performance (10+10+10 = 30 marks)
                score += 30.0  # Placeholder: full marks if data exists

                # Professional activities (25 marks partial)
                score += 25.0

            rec.c4_score = min(score, 120.0)

    @api.depends('c5_faculty_ids')
    def _compute_c5_score(self):
        for rec in self:
            score = 0.0
            if rec.c5_faculty_ids:
                latest = rec.c5_faculty_ids.sorted('id', reverse=True)[:1]
                if latest:
                    f = latest[0]
                    score += f.sfr_marks
                    score += min(25.0, f.fqi_score)
                    score += f.cadre_marks
                    score += f.retention_marks
                    # Visiting faculty section (10 marks)
                    if rec.fdp_ids:
                        score += 10.0
            rec.c5_score = min(score, 100.0)

    @api.depends('research_ids')
    def _compute_c6_score(self):
        for rec in self:
            score = 0.0

            # ── 6.1 Professional Development Activities (60 marks) ───────────

            # 6.1.1 Professional Society Memberships (5 marks)
            # Full 5 if any faculty has active memberships
            prof_soc = rec.research_ids.filtered(lambda r: r.research_type == 'prof_society')
            if prof_soc:
                score += 5.0

            # 6.1.2.1 FDP as Resource Person (5 marks)
            fdp_resource = rec.research_ids.filtered(lambda r: r.research_type == 'fdp_attended'
                                                     and r.fdp_is_external)
            if fdp_resource:
                score += 5.0

            # 6.1.2.2 FDP Participation Assessment Points (5 marks)
            # Formula: AP = Sum_pts / (0.5 * RF), avg over 3 years, max 5
            # Pull from nba.c6.contributions records if available
            c6_contribs = self.env['nba.c6.contributions'].search([('sar_id', '=', rec.id)])
            if c6_contribs:
                ap_vals = [c.fdp_participant_pts for c in c6_contribs if c.fdp_participant_pts > 0]
                avg_ap = sum(ap_vals) / len(ap_vals) if ap_vals else 0.0
                score += min(5.0, avg_ap)
            else:
                # Fallback: count external FDPs attended per faculty
                fdp_attended = rec.research_ids.filtered(
                    lambda r: r.research_type == 'fdp_attended' and r.fdp_is_external
                )
                if fdp_attended:
                    pts = sum(r.fdp_points for r in fdp_attended)
                    score += min(5.0, pts / max(1, len(fdp_attended.mapped('faculty_id'))))

            # 6.1.3 MOOC Developed (7 marks)
            mooc_developed = rec.research_ids.filtered(lambda r: r.research_type == 'mooc_developed')
            if mooc_developed:
                score += 7.0

            # 6.1.4 MOOC Certified (8 marks)
            mooc_certified = rec.research_ids.filtered(lambda r: r.research_type == 'mooc_certified')
            if mooc_certified:
                score += 8.0

            # 6.1.5 FDP/STTP Organized (10 marks): 2 pts/FDP, max 4/year, max 10 total
            fdp_organized = rec.research_ids.filtered(lambda r: r.research_type == 'fdp_organized')
            fdp_org_pts = sum(r.fdp_points for r in fdp_organized)
            score += min(10.0, fdp_org_pts)

            # 6.1.6 Student Innovation Mentoring (10 marks)
            innovation = rec.research_ids.filtered(lambda r: r.research_type == 'student_innovation')
            if innovation:
                score += 10.0

            # 6.1.7 Faculty Industry Collaboration / Internship (10 marks)
            collab = rec.research_ids.filtered(lambda r: r.research_type == 'industry_collab')
            if collab:
                score += 10.0

            # ── 6.2 Research & Development Activities (60 marks) ─────────────

            # 6.2.1 Academic Research: journals 10 marks
            journals = rec.research_ids.filtered(lambda r: r.research_type == 'journal')
            conferences = rec.research_ids.filtered(lambda r: r.research_type == 'conference')
            books = rec.research_ids.filtered(lambda r: r.research_type in ('book', 'book_chapter'))
            if journals or conferences or books:
                score += 10.0

            # 6.2.2 PhD Students (5 marks)
            phd_guided = rec.research_ids.filtered(lambda r: r.research_type == 'phd_guidance')
            if phd_guided:
                score += 5.0

            # 6.2.3 Development Activities: patents (10 marks — based on nba.research patent type)
            patents = rec.research_ids.filtered(lambda r: r.research_type == 'patent')
            if patents:
                score += 10.0

            # 6.2.4 Sponsored Research (15 marks) — NBA slab on total amount (Lacs)
            funded = rec.research_ids.filtered(lambda r: r.research_type == 'funded_project')
            total_funding = sum(r.amount_lacs for r in funded)
            if total_funding > 20:
                score += 15.0
            elif total_funding > 16:
                score += 12.0
            elif total_funding > 12:
                score += 9.0
            elif total_funding > 8:
                score += 6.0
            elif total_funding > 4:
                score += 3.0
            elif total_funding > 1:
                score += 1.0

            # 6.2.5 Consultancy (15 marks) — NBA slab
            consult = rec.research_ids.filtered(lambda r: r.research_type == 'consultancy')
            total_consult = sum(r.amount_lacs for r in consult)
            if total_consult > 20:
                score += 15.0
            elif total_consult > 16:
                score += 12.0
            elif total_consult > 12:
                score += 9.0
            elif total_consult > 8:
                score += 6.0
            elif total_consult > 4:
                score += 3.0
            elif total_consult > 1:
                score += 1.0

            # 6.2.6 Seed Money (5 marks): received (3) + utilized (2)
            seed = rec.research_ids.filtered(lambda r: r.research_type == 'seed_money')
            if seed:
                total_seed_r = sum(r.amount_lacs for r in seed)
                total_seed_u = sum(r.amount_utilized_lacs for r in seed)
                if total_seed_r > 6:
                    score += 3.0
                elif total_seed_r > 4:
                    score += 2.0
                elif total_seed_r > 2:
                    score += 1.0
                if total_seed_r > 0:
                    util_pct = total_seed_u / total_seed_r
                    score += min(2.0, util_pct * 2.0)

            rec.c6_score = min(score, 120.0)


    # ════════════════════════════════════════════════════════════════════════════
    # ORM Overrides

    @api.depends('c1_score', 'c2_score', 'c3_score', 'c4_score',
                 'c5_score', 'c6_score', 'c7_score', 'c8_score', 'c9_score')
    def _compute_total_score(self):
        for rec in self:
            total = (rec.c1_score + rec.c2_score + rec.c3_score + rec.c4_score +
                     rec.c5_score + rec.c6_score + rec.c7_score + rec.c8_score +
                     rec.c9_score)
            rec.total_score = round(total, 2)
            rec.readiness_pct = round(total / 10.0, 2)  # out of 1000 → %

    # ════════════════════════════════════════════════════════════════════════════
    # ORM Overrides
    # ════════════════════════════════════════════════════════════════════════════

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('nba.sar') or '/'
        return super().create(vals)

    # ════════════════════════════════════════════════════════════════════════════
    # Workflow Actions
    # ════════════════════════════════════════════════════════════════════════════

    def action_start_data_entry(self):
        self.write({'state': 'data_entry'})
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': _('Data Entry Started'),
                           'message': _('SAR is now open for data entry.'),
                           'type': 'success'}}

    def action_submit_review(self):
        self.write({'state': 'under_review'})

    def action_submit_nba(self):
        self.write({'state': 'submitted'})

    def action_mark_accredited(self):
        self.write({'state': 'accredited'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_open_compute_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Auto-Compute NBA Criteria'),
            'res_model': 'nba.compute.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_sar_id': self.id},
        }

    def action_generate_sar(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generate SAR Report'),
            'res_model': 'nba.generate.sar.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_sar_id': self.id},
        }

    def action_compute_all(self):
        """Trigger full recomputation of all criteria from live data."""
        self.ensure_one()
        # C4 - Pull student data
        self._pull_c4_student_data()
        # C5 - Pull faculty data
        self._pull_c5_faculty_data()
        # CO attainment from exam results
        for co in self.co_ids:
            co._compute_attainment()
        self.write({'last_computed_on': fields.Datetime.now()})
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': _('Computation Complete'),
                           'message': _('All NBA criteria have been recomputed from live data.'),
                           'type': 'success'}}

    def _pull_c4_student_data(self):
        """Auto-populate C4 student tables from admission records."""
        self.ensure_one()
        if not self.program_id:
            return
        year_map = [
            (self.cay_id, 'CAY'),
            (self.caym1_id, 'CAYm1'),
            (self.caym2_id, 'CAYm2'),
            (self.lyg_id, 'LYG'),
            (self.lygm1_id, 'LYGm1'),
            (self.lygm2_id, 'LYGm2'),
        ]
        for year, label in year_map:
            if not year:
                continue
            existing = self.env['nba.c4.students'].search([
                ('sar_id', '=', self.id),
                ('academic_year_id', '=', year.id),
            ])
            if not existing:
                self.env['nba.c4.students'].create({
                    'sar_id': self.id,
                    'academic_year_id': year.id,
                    'year_label': label,
                })
            else:
                existing._compute_all()

    def _pull_c5_faculty_data(self):
        """Auto-populate C5 faculty tables."""
        self.ensure_one()
        if not self.department_id:
            return
        year_map = [
            (self.cay_id, 'CAY'),
            (self.caym1_id, 'CAYm1'),
            (self.caym2_id, 'CAYm2'),
        ]
        for year, label in year_map:
            if not year:
                continue
            existing = self.env['nba.c5.faculty'].search([
                ('sar_id', '=', self.id),
                ('academic_year_id', '=', year.id),
            ])
            if not existing:
                self.env['nba.c5.faculty'].create({
                    'sar_id': self.id,
                    'academic_year_id': year.id,
                    'year_label': label,
                })
            else:
                existing._compute_all()

    # ─── Smart button action methods ──────────────────────────────────────────
    def action_view_evidence(self):
        return {'type': 'ir.actions.act_window', 'res_model': 'nba.evidence',
                'view_mode': 'list,form', 'domain': [('sar_id', '=', self.id)],
                'context': {'default_sar_id': self.id}}

    def action_bulk_upload_evidence(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bulk Upload Evidence'),
            'res_model': 'nba.evidence.bulk.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_sar_id': self.id},
        }

    def action_view_cos(self):
        return {'type': 'ir.actions.act_window', 'res_model': 'nba.co',
                'view_mode': 'list,form', 'domain': [('sar_id', '=', self.id)],
                'context': {'default_sar_id': self.id}}

    def action_view_research(self):
        return {'type': 'ir.actions.act_window', 'res_model': 'nba.research',
                'view_mode': 'list,form', 'domain': [('sar_id', '=', self.id)],
                'context': {'default_sar_id': self.id}}

    def action_view_faculty(self):
        return {'type': 'ir.actions.act_window', 'res_model': 'faculty.faculty',
                'view_mode': 'list,form',
                'domain': [('department_id', '=', self.department_id.id)]}

    def action_view_students(self):
        return {'type': 'ir.actions.act_window', 'res_model': 'student.student',
                'view_mode': 'list,form',
                'domain': [('program_id', '=', self.program_id.id)]}

    def action_view_scores(self):
        return {'type': 'ir.actions.act_window', 'res_model': 'nba.sar',
                'view_mode': 'form', 'res_id': self.id,
                'context': {'active_tab': 'scores'}}