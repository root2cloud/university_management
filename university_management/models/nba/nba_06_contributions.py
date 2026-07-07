# -*- coding: utf-8 -*-

from odoo import models, fields, api


class NBAC6Contributions(models.Model):
    _name = 'nba.c6.contributions'
    _description = 'NBA Criterion 6 - Faculty Contributions Summary'
    _order = 'sar_id, academic_year_id'

    sar_id = fields.Many2one('nba.sar', string='SAR', required=True,
                             ondelete='cascade', index=True)
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year')
    year_label = fields.Selection([
        ('CAYm1', 'CAYm1'),
        ('CAYm2', 'CAYm2'),
        ('CAYm3', 'CAYm3'),
    ], string='Year Label')

    # ─── 6.1.1 Professional Society Memberships ──────────────────────────────
    professional_society_count = fields.Integer(string='Active Professional Society Memberships')

    # ─── 6.1.2 FDP Participation ──────────────────────────────────────────────
    fdp_resource_person_count = fields.Integer(string='FDP/STTP as Resource Person')
    fdp_participant_count = fields.Integer(string='FDP/STTP Participants')
    fdp_participant_raw_pts = fields.Float(
        string='Sum of FDP Participant Points (raw)',
        help='Sum of individual FDP points scored by all faculty (max 5 per faculty per year)'
    )
    fdp_participant_pts = fields.Float(
        string='C6.1.2.2 FDP Participation Assessment Points (AP)',
        compute='_compute_fdp_assessment_pts', store=True,
        help='AP = Sum / (0.5 × RF), limited to 5 per year'
    )
    fdp_participant_avg_pts = fields.Float(
        string='C6.1.2.2 Average AP over 3 Years (max 5)',
        compute='_compute_fdp_assessment_pts', store=True
    )
    rf_value = fields.Integer(
        string='RF (Required Faculty at 20:1 for this year)',
        help='Used in FDP participation formula. RF = DS/20'
    )

    # ─── 6.1.3/6.1.4 MOOC ─────────────────────────────────────────────────────
    mooc_developed_count = fields.Integer(string='MOOCs Developed (SWAYAM)')
    mooc_certified_count = fields.Integer(string='MOOCs Certified')

    # ─── 6.1.5 FDP/STTP Organized ────────────────────────────────────────────
    fdp_organized_count = fields.Integer(string='FDPs/STTPs Organized')
    fdp_organized_pts = fields.Float(string='FDP Organized Points', digits=(5, 2))

    # ─── 6.1.6 Student Innovation ────────────────────────────────────────────
    student_innovation_count = fields.Integer(string='Student Innovation Projects Mentored')

    # ─── 6.1.7 Industry Collaboration ────────────────────────────────────────
    industry_collab_count = fields.Integer(string='Industry Collaboration / Internship')

    # ─── 6.2.1 Publications ───────────────────────────────────────────────────
    journal_papers = fields.Integer(string='Peer-Reviewed Journal Papers (Scopus/WoS)')
    conference_papers = fields.Integer(string='Conference Papers')
    books_chapters = fields.Integer(string='Books / Book Chapters')

    # ─── 6.2.2 PhD ────────────────────────────────────────────────────────────
    phd_enrolled = fields.Integer(string='PhD Students Enrolled')
    phd_graduated = fields.Integer(string='PhD Students Graduated')

    # ─── 6.2.3 Patents/Prototypes ─────────────────────────────────────────────
    patents_granted = fields.Integer(string='Patents Granted')
    patents_published = fields.Integer(string='Patents Published')
    prototypes_developed = fields.Integer(string='Working Models / Prototypes')

    # ─── 6.2.4 Sponsored Research ─────────────────────────────────────────────
    sponsored_research_amount = fields.Float(string='Sponsored Research Amount (Lacs)')
    sponsored_research_marks = fields.Float(
        string='Sponsored Research Marks /15',
        compute='_compute_research_marks', store=True
    )

    # ─── 6.2.5 Consultancy ────────────────────────────────────────────────────
    consultancy_amount = fields.Float(string='Consultancy Amount (Lacs)')
    consultancy_marks = fields.Float(
        string='Consultancy Marks /15',
        compute='_compute_research_marks', store=True
    )

    # ─── 6.2.6 Seed Money ─────────────────────────────────────────────────────
    seed_money_received = fields.Float(string='Seed Money Received (Lacs)')
    seed_money_utilized = fields.Float(string='Seed Money Utilized (Lacs)')
    seed_money_marks = fields.Float(
        string='Seed Money Marks /5',
        compute='_compute_research_marks', store=True
    )

    @api.depends('fdp_participant_raw_pts', 'rf_value')
    def _compute_fdp_assessment_pts(self):
        """
        C6.1.2.2: AP = Sum of faculty FDP points / (0.5 × RF), max 5 per year.
        Average over 3 years (marks limited to 5).
        This computes per-year AP; averaging is done in nba_sar._compute_c6_score.
        """
        for rec in self:
            rf = max(rec.rf_value, 1)
            ap = min(5.0, rec.fdp_participant_raw_pts / (0.5 * rf))
            rec.fdp_participant_pts = round(ap, 2)
            # Average stored here is just this year's AP; SAR averages across years
            rec.fdp_participant_avg_pts = round(ap, 2)

    @api.depends('sponsored_research_amount', 'consultancy_amount',
                 'seed_money_received', 'seed_money_utilized')
    def _compute_research_marks(self):
        for rec in self:
            # Sponsored research marks (C6.2.4)
            sr = rec.sponsored_research_amount
            if sr > 20:
                rec.sponsored_research_marks = 15.0
            elif sr > 16:
                rec.sponsored_research_marks = 12.0
            elif sr > 12:
                rec.sponsored_research_marks = 9.0
            elif sr > 8:
                rec.sponsored_research_marks = 6.0
            elif sr > 4:
                rec.sponsored_research_marks = 3.0
            elif sr > 1:
                rec.sponsored_research_marks = 1.0
            else:
                rec.sponsored_research_marks = 0.0

            # Consultancy marks (C6.2.5)
            cs = rec.consultancy_amount
            if cs > 20:
                rec.consultancy_marks = 15.0
            elif cs > 16:
                rec.consultancy_marks = 12.0
            elif cs > 12:
                rec.consultancy_marks = 9.0
            elif cs > 8:
                rec.consultancy_marks = 6.0
            elif cs > 4:
                rec.consultancy_marks = 3.0
            elif cs > 1:
                rec.consultancy_marks = 1.0
            else:
                rec.consultancy_marks = 0.0

            # Seed money marks (C6.2.6)
            sm_r = rec.seed_money_received
            sm_u = rec.seed_money_utilized
            received_marks = 0.0
            if sm_r > 6:
                received_marks = 3.0
            elif sm_r > 4:
                received_marks = 2.0
            elif sm_r > 2:
                received_marks = 1.0
            utilized_marks = min(2.0, (sm_u / sm_r * 2.0) if sm_r else 0.0)
            rec.seed_money_marks = round(received_marks + utilized_marks, 2)

    @api.model
    def compute_from_research(self, sar_id):
        """Auto-populate C6 summary from nba.research records."""
        sar = self.env['nba.sar'].browse(sar_id)
        for year, label in [
            (sar.caym1_id, 'CAYm1'),
            (sar.caym2_id, 'CAYm2'),
        ]:
            if not year:
                continue
            research = sar.research_ids.filtered(
                lambda r: r.academic_year_id.id == year.id
            )
            vals = {
                'sar_id': sar_id,
                'academic_year_id': year.id,
                'year_label': label,
                'journal_papers': len(research.filtered(lambda r: r.research_type == 'journal')),
                'conference_papers': len(research.filtered(lambda r: r.research_type == 'conference')),
                'fdp_participant_count': len(research.filtered(lambda r: r.research_type == 'fdp_attended')),
                'fdp_organized_count': len(research.filtered(lambda r: r.research_type == 'fdp_organized')),
                'mooc_certified_count': len(research.filtered(lambda r: r.research_type == 'mooc_certified')),
                'mooc_developed_count': len(research.filtered(lambda r: r.research_type == 'mooc_developed')),
                'sponsored_research_amount': sum(
                    r.amount_lacs for r in research.filtered(lambda r: r.research_type == 'funded_project')
                ),
                'consultancy_amount': sum(
                    r.amount_lacs for r in research.filtered(lambda r: r.research_type == 'consultancy')
                ),
                'seed_money_received': sum(
                    r.amount_lacs for r in research.filtered(lambda r: r.research_type == 'seed_money')
                ),
                'student_innovation_count': len(research.filtered(lambda r: r.research_type == 'student_innovation')),
                'industry_collab_count': len(research.filtered(lambda r: r.research_type == 'industry_collab')),
            }
            existing = self.search([('sar_id', '=', sar_id), ('year_label', '=', label)])
            if existing:
                existing.write({k: v for k, v in vals.items() if k not in ('sar_id', 'academic_year_id', 'year_label')})
            else:
                self.create(vals)