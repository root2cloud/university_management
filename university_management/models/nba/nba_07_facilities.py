# -*- coding: utf-8 -*-

from odoo import models, fields, api


class NBAC7Facilities(models.Model):
    _name = 'nba.c7.facilities'
    _description = 'NBA Criterion 7 - Facilities Summary'

    sar_id = fields.Many2one('nba.sar', string='SAR', required=True,
                             ondelete='cascade', index=True)

    # 7.3 Maintenance
    maintenance_narrative = fields.Html(string='7.3 Lab Maintenance & Ambiance')

    # 7.4 Safety
    safety_narrative = fields.Html(string='7.4 Safety Measures')

    # 7.5 Project/Research Lab
    project_lab_narrative = fields.Html(string='7.5 Project/Research Labs & CoE')

    # Counts (auto-computed)
    total_labs = fields.Integer(
        string='Total Laboratories', compute='_compute_lab_counts', store=True
    )
    total_equipment = fields.Integer(string='Total Major Equipment')
    technical_staff_count = fields.Integer(
        string='Technical Support Staff', compute='_compute_lab_counts', store=True
    )

    @api.depends('sar_id')
    def _compute_lab_counts(self):
        for rec in self:
            if rec.sar_id:
                rec.total_labs = len(rec.sar_id.lab_ids)
                rec.technical_staff_count = 0  # Override manually


class NBAC8Improvement(models.Model):
    _name = 'nba.c8.improvement'
    _description = 'NBA Criterion 8 - Continuous Improvement Actions'
    _order = 'sar_id, action_type'

    sar_id = fields.Many2one('nba.sar', string='SAR', required=True,
                             ondelete='cascade', index=True)
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year')

    action_type = fields.Selection([
        ('co_attainment', '8.1.1 CO Attainment Improvement'),
        ('po_attainment', '8.1.2 PO/PSO Attainment Improvement'),
        ('academic_audit', '8.2 Academic Audit'),
        ('faculty_improvement', '8.3 Faculty Qualification Improvement'),
        ('academic_performance', '8.4 Academic Performance Improvement'),
    ], string='Action Type', required=True)

    weakness_identified = fields.Text(string='Weakness / Gap Identified')
    action_taken = fields.Text(string='Action Taken')
    impact = fields.Text(string='Impact / Outcome')
    target_co_po = fields.Char(string='Targeted CO/PO/PSO')
    implementation_date = fields.Date(string='Implementation Date')
    responsible_faculty = fields.Many2one('faculty.faculty', string='Responsible Faculty')

    # C8.3 Faculty Improvement Trend
    phd_count = fields.Integer(string='No. of PhD Faculty')
    journal_papers = fields.Integer(string='Journal Publications')
    conference_papers = fields.Integer(string='Conference Papers')


class NBAC9Governance(models.Model):
    _name = 'nba.c9.governance'
    _description = 'NBA Criterion 9 - Student Support & Governance'

    sar_id = fields.Many2one('nba.sar', string='SAR', required=True,
                             ondelete='cascade', index=True)

    # ─── 9.1 FYSFR ───────────────────────────────────────────────────────────
    fysfr_ns1 = fields.Integer(
        string='NS1 (Basic Science + Humanities Faculty)',
        help='No. of faculty in Basic Sciences, HSS, Management courses'
    )
    fysfr_ns2 = fields.Integer(
        string='NS2 (Engineering Science Faculty)',
        help='No. of faculty in Engineering Science courses'
    )
    fysfr_s4 = fields.Integer(
        string='S4 (Total Sanctioned Intake all UG Programs)',
        compute='_compute_fysfr', store=True
    )
    fysfr_rf4 = fields.Float(
        string='RF4 (Required Faculty for FYSFR)',
        compute='_compute_fysfr', store=True
    )
    fysfr_pct = fields.Float(
        string='FYSFR %', compute='_compute_fysfr', store=True, digits=(5, 2)
    )
    fysfr_marks = fields.Float(
        string='FYSFR Marks /5', compute='_compute_fysfr', store=True
    )

    # ─── 9.7 Budget Tables ────────────────────────────────────────────────────
    budget_cfym1 = fields.Float(string='Budget CFYm1 (Lacs)')
    actual_cfym1 = fields.Float(string='Actual Expenditure CFYm1 (Lacs)')
    budget_cfym2 = fields.Float(string='Budget CFYm2 (Lacs)')
    actual_cfym2 = fields.Float(string='Actual Expenditure CFYm2 (Lacs)')
    budget_cfym3 = fields.Float(string='Budget CFYm3 (Lacs)')
    actual_cfym3 = fields.Float(string='Actual Expenditure CFYm3 (Lacs)')
    total_students_cfym1 = fields.Integer(string='Total Students CFYm1')
    expenditure_per_student = fields.Float(
        string='Expenditure per Student (Lacs)',
        compute='_compute_exp_per_student', store=True
    )

    # ─── 9.8 Program Budget ───────────────────────────────────────────────────
    prog_budget_cfym1 = fields.Float(string='Program Budget CFYm1 (Lacs)')
    prog_actual_cfym1 = fields.Float(string='Program Actual CFYm1 (Lacs)')

    # ─── 9.9-9.14 Counts ──────────────────────────────────────────────────────
    library_books_count = fields.Integer(
        string='Library Books Count', compute='_compute_library', store=True
    )
    eresources_count = fields.Integer(string='E-Resources / Journals')
    mentoring_count = fields.Integer(string='No. of Mentoring Sessions')

    @api.depends('fysfr_ns1', 'fysfr_ns2', 'sar_id')
    def _compute_fysfr(self):
        for rec in self:
            if not rec.sar_id or not rec.sar_id.program_id:
                rec.fysfr_s4 = rec.fysfr_rf4 = rec.fysfr_pct = rec.fysfr_marks = 0
                continue

            # S4 = total sanctioned intake of all UG programs
            ug_programs = self.env['university.program'].search([
                ('department_id', '=', rec.sar_id.department_id.id),
                ('program_type', '=', 'undergraduate'),
            ])
            s4 = sum(p.total_seats or 0 for p in ug_programs)
            rec.fysfr_s4 = s4
            rf4 = s4 / 20.0 if s4 else 1.0
            rec.fysfr_rf4 = rf4

            # FYSFR formula: ((NS1*0.8) + (NS2*0.2)) / RF4
            pct = ((rec.fysfr_ns1 * 0.8 + rec.fysfr_ns2 * 0.2) / rf4 * 100) if rf4 else 0.0
            rec.fysfr_pct = round(pct, 2)

            # Marks
            if pct >= 90:
                rec.fysfr_marks = 5.0
            elif pct >= 80:
                rec.fysfr_marks = 4.0
            elif pct >= 70:
                rec.fysfr_marks = 3.0
            elif pct >= 60:
                rec.fysfr_marks = 2.0
            elif pct >= 50:
                rec.fysfr_marks = 1.0
            else:
                rec.fysfr_marks = 0.0

    @api.depends('actual_cfym1', 'total_students_cfym1')
    def _compute_exp_per_student(self):
        for rec in self:
            if rec.total_students_cfym1:
                rec.expenditure_per_student = round(
                    rec.actual_cfym1 / rec.total_students_cfym1, 4
                )
            else:
                rec.expenditure_per_student = 0.0

    @api.depends('sar_id')
    def _compute_library(self):
        for rec in self:
            if rec.sar_id and rec.sar_id.department_id:
                rec.library_books_count = self.env['library.book'].search_count([
                    ('state', '!=', 'lost')
                ])
            else:
                rec.library_books_count = 0