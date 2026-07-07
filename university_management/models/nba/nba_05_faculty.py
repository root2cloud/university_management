# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import date


class NBAC5Faculty(models.Model):
    _name = 'nba.c5.faculty'
    _description = 'NBA Criterion 5 - Faculty Information (SFR, FQI, Cadre, Retention)'
    _order = 'sar_id, year_label'

    sar_id = fields.Many2one('nba.sar', string='SAR', required=True,
                             ondelete='cascade', index=True)
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year',
                                       required=True)
    year_label = fields.Selection([
        ('CAY', 'CAY'),
        ('CAYm1', 'CAYm1'),
        ('CAYm2', 'CAYm2'),
    ], string='Year', required=True)

    # ─── Student Counts for SFR ────────────────────────────────────────────
    s_ug_yr2 = fields.Integer(string='UG Yr2 Students', compute='_compute_all', store=True)
    s_ug_yr3 = fields.Integer(string='UG Yr3 Students', compute='_compute_all', store=True)
    s_ug_yr4 = fields.Integer(string='UG Yr4 Students', compute='_compute_all', store=True)
    s_pg_yr1 = fields.Integer(string='PG Yr1 Students', compute='_compute_all', store=True)
    s_pg_yr2 = fields.Integer(string='PG Yr2 Students', compute='_compute_all', store=True)
    s_total = fields.Integer(string='Total Students (S)', compute='_compute_all', store=True)

    # ─── Faculty Counts ──────────────────────────────────────────────────────
    f_total = fields.Integer(string='Total Faculty (F)', compute='_compute_all', store=True)
    ff_first_year_only = fields.Integer(
        string='FF (First-Year-Only Faculty)', default=0
    )
    tf_effective = fields.Integer(
        string='TF (Effective Faculty F-FF)', compute='_compute_sfr', store=True
    )

    # ─── C5.1 SFR ────────────────────────────────────────────────────────────
    sfr_value = fields.Float(
        string='SFR Value', compute='_compute_sfr', store=True, digits=(5, 2)
    )
    sfr_marks = fields.Float(
        string='SFR Marks /30', compute='_compute_sfr', store=True, digits=(5, 1)
    )
    rf_required = fields.Integer(
        string='RF (Required Faculty at 20:1)', compute='_compute_sfr', store=True
    )

    # ─── C5.2 Faculty Qualification Index ────────────────────────────────────
    x_phd = fields.Integer(string='X (Ph.D Faculty)', compute='_compute_all', store=True)
    y_mtech = fields.Integer(string='Y (M.Tech/ME Faculty)', compute='_compute_all', store=True)
    fqi_score = fields.Float(
        string='FQI Score /25', compute='_compute_fqi', store=True, digits=(5, 2)
    )

    # ─── C5.3 Faculty Cadre Proportion ───────────────────────────────────────
    rf1_req = fields.Float(string='RF1 (Required Professors)', compute='_compute_cadre', store=True)
    af1_avail = fields.Integer(string='AF1 (Available Professors)', compute='_compute_all', store=True)
    rf2_req = fields.Float(string='RF2 (Required Assoc Profs)', compute='_compute_cadre', store=True)
    af2_avail = fields.Integer(string='AF2 (Available Assoc Profs)', compute='_compute_all', store=True)
    rf3_req = fields.Float(string='RF3 (Required Asst Profs)', compute='_compute_cadre', store=True)
    af3_avail = fields.Integer(string='AF3 (Available Asst Profs)', compute='_compute_all', store=True)
    cadre_marks = fields.Float(
        string='Cadre Proportion Marks /25', compute='_compute_cadre', store=True, digits=(5, 2)
    )

    # ─── C5.5 Faculty Retention ───────────────────────────────────────────────
    fa_lt1yr = fields.Integer(string='A (<1 yr exp)', compute='_compute_all', store=True)
    fb_1to2yr = fields.Integer(string='B (1-2 yrs)', compute='_compute_all', store=True)
    fc_2to3yr = fields.Integer(string='C (2-3 yrs)', compute='_compute_all', store=True)
    fd_3to4yr = fields.Integer(string='D (3-4 yrs)', compute='_compute_all', store=True)
    fe_gt4yr = fields.Integer(string='E (>4 yrs)', compute='_compute_all', store=True)
    retention_marks = fields.Float(
        string='Retention Marks /10', compute='_compute_retention', store=True, digits=(5, 2)
    )

    is_manual_override = fields.Boolean(string='Manual Override', default=False)

    # ════════════════════════════════════════════════════════════════════════
    # Compute Methods
    # ════════════════════════════════════════════════════════════════════════

    def _compute_all(self):
        """Pull all data from faculty and student records."""
        for rec in self:
            if rec.is_manual_override:
                continue
            sar = rec.sar_id
            dept_ids = [sar.department_id.id] if sar.department_id else []
            dept_ids += sar.allied_dept_ids.ids

            if not dept_ids:
                rec.s_total = rec.f_total = 0
                continue

            # ── Student counts ──────────────────────────────────────────
            students = self.env['student.student'].search([
                ('department_id', 'in', dept_ids),
                ('state', 'in', ('active', 'registered')),
            ])

            # Group by current_year
            yr2 = yr3 = yr4 = pg1 = pg2 = 0
            for s in students:
                prog_type = s.program_id.program_type if s.program_id else ''
                yr = s.current_year if hasattr(s, 'current_year') else 0
                if prog_type == 'undergraduate':
                    if yr == 2:
                        yr2 += 1
                    elif yr == 3:
                        yr3 += 1
                    elif yr == 4:
                        yr4 += 1
                elif prog_type == 'postgraduate':
                    if yr == 1:
                        pg1 += 1
                    elif yr == 2:
                        pg2 += 1

            rec.s_ug_yr2 = yr2
            rec.s_ug_yr3 = yr3
            rec.s_ug_yr4 = yr4
            rec.s_pg_yr1 = pg1
            rec.s_pg_yr2 = pg2
            rec.s_total = yr2 + yr3 + yr4 + pg1 + pg2

            # ── Faculty counts ──────────────────────────────────────────
            full_time_types = ('permanent', 'temporary', 'contract')
            faculty_all = self.env['faculty.faculty'].search([
                ('department_id', 'in', dept_ids),
                ('employment_type', 'in', full_time_types),
            ])
            rec.f_total = len(faculty_all)

            # PhD and MTech counts
            rec.x_phd = sum(
                1 for f in faculty_all
                if f.highest_qualification == 'phd'
            )
            rec.y_mtech = sum(
                1 for f in faculty_all
                if f.highest_qualification == 'postgraduate'
            )

            # Cadre counts
            rec.af1_avail = sum(
                1 for f in faculty_all
                if f.designation_id and f.designation_id.level == 'professor'
            )
            rec.af2_avail = sum(
                1 for f in faculty_all
                if f.designation_id and f.designation_id.level == 'associate_professor'
            )
            rec.af3_avail = sum(
                1 for f in faculty_all
                if f.designation_id and f.designation_id.level == 'assistant_professor'
            )

            # Retention bands (by years of experience at current institute)
            today = date.today()
            a = b = c = d = e = 0
            for f in faculty_all:
                if not f.date_of_joining:
                    a += 1
                    continue
                months = (today.year - f.date_of_joining.year) * 12 + \
                         (today.month - f.date_of_joining.month)
                years = months / 12.0
                if years < 1:
                    a += 1
                elif years < 2:
                    b += 1
                elif years < 3:
                    c += 1
                elif years < 4:
                    d += 1
                else:
                    e += 1
            rec.fa_lt1yr = a
            rec.fb_1to2yr = b
            rec.fc_2to3yr = c
            rec.fd_3to4yr = d
            rec.fe_gt4yr = e

    @api.depends('s_total', 'f_total', 'ff_first_year_only')
    def _compute_sfr(self):
        for rec in self:
            tf = max(rec.f_total - rec.ff_first_year_only, 1)
            rec.tf_effective = tf
            sfr = (rec.s_total / tf) if tf else 99.0
            rec.sfr_value = round(sfr, 2)
            rec.rf_required = max(int(rec.s_total / 20), 1)

            # NBA SFR marks table
            if sfr < 15:
                marks = 30.0
            elif sfr < 17:
                marks = 27.0
            elif sfr < 19:
                marks = 24.0
            elif sfr < 21:
                marks = 21.0
            elif sfr < 23:
                marks = 18.0
            elif sfr < 25:
                marks = 15.0
            else:
                marks = 0.0
            rec.sfr_marks = marks

    @api.depends('x_phd', 'y_mtech', 'rf_required')
    def _compute_fqi(self):
        for rec in self:
            rf = max(rec.rf_required, 1)
            fqi = 2.5 * (10 * rec.x_phd + 4 * rec.y_mtech) / rf
            rec.fqi_score = round(min(fqi, 25.0), 2)

    @api.depends('rf_required', 'af1_avail', 'af2_avail', 'af3_avail')
    def _compute_cadre(self):
        for rec in self:
            rf = max(rec.rf_required, 1)
            rec.rf1_req = round(rf / 9.0, 2)
            rec.rf2_req = round(2 * rf / 9.0, 2)
            rec.rf3_req = round(6 * rf / 9.0, 2)

            rf1 = max(rec.rf1_req, 0.001)
            rf2 = max(rec.rf2_req, 0.001)
            rf3 = max(rec.rf3_req, 0.001)

            cadre = (rec.af1_avail / rf1 + (rec.af2_avail / rf2) * 0.6 +
                     (rec.af3_avail / rf3) * 0.4) * 12.5
            rec.cadre_marks = round(min(cadre, 25.0), 2)

    @api.depends('fa_lt1yr', 'fb_1to2yr', 'fc_2to3yr', 'fd_3to4yr',
                 'fe_gt4yr', 'rf_required')
    def _compute_retention(self):
        for rec in self:
            rf = max(rec.rf_required, 1)
            fr = ((rec.fa_lt1yr * 0 + rec.fb_1to2yr * 1 +
                   rec.fc_2to3yr * 2 + rec.fd_3to4yr * 3 +
                   rec.fe_gt4yr * 4) / rf) * 2.5
            rec.retention_marks = round(min(fr, 10.0), 2)