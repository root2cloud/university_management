# -*- coding: utf-8 -*-

from odoo import models, fields, api


class NBAC1Curriculum(models.Model):
    _name = 'nba.c1.curriculum'
    _description = 'NBA Criterion 1 - Curriculum Component Details'
    _order = 'sar_id, component'

    sar_id = fields.Many2one('nba.sar', string='SAR', required=True,
                             ondelete='cascade', index=True)

    component = fields.Selection([
        ('basic_sciences', 'Basic Sciences'),
        ('basic_engineering', 'Basic Engineering'),
        ('humanities_social', 'Humanities & Social Sciences'),
        ('program_core', 'Program Core'),
        ('program_electives', 'Program Electives'),
        ('open_electives', 'Open Electives'),
        ('projects', 'Project(s)'),
        ('internships', 'Internships / Seminars'),
        ('other', 'Any Other'),
    ], string='Curriculum Component', required=True)

    component_other = fields.Char(string='Other Component Name')

    total_credits = fields.Integer(string='Total Credits')
    total_contact_hours = fields.Integer(string='Total Contact Hours')
    percentage_credits = fields.Float(
        string='% of Total Credits',
        compute='_compute_percentage', store=True
    )

    # Computed from courses
    total_program_credits = fields.Integer(
        string='Total Program Credits',
        related='sar_id.program_id.total_seats',  # placeholder; computed separately
        readonly=True
    )

    @api.depends('total_credits', 'sar_id')
    def _compute_percentage(self):
        for rec in self:
            # Get total credits across all components in this SAR
            siblings = self.env['nba.c1.curriculum'].search([('sar_id', '=', rec.sar_id.id)])
            total = sum(s.total_credits for s in siblings)
            rec.percentage_credits = round((rec.total_credits / total * 100) if total else 0.0, 2)

    @api.model
    def populate_from_courses(self, sar_id):
        """Auto-populate curriculum components by scanning course types."""
        sar = self.env['nba.sar'].browse(sar_id)
        if not sar.program_id:
            return
        courses = self.env['university.course'].search([
            ('program_id', '=', sar.program_id.id)
        ])
        component_map = {
            'theory': 'program_core',
            'practical': 'basic_engineering',
            'lab': 'basic_engineering',
            'project': 'projects',
            'seminar': 'internships',
            'elective': 'program_electives',
        }
        totals = {}
        for course in courses:
            comp = component_map.get(course.course_type, 'program_core')
            if comp not in totals:
                totals[comp] = {'credits': 0, 'hours': 0}
            totals[comp]['credits'] += course.credits or 0
            totals[comp]['hours'] += course.total_hours or 0

        for comp, vals in totals.items():
            existing = self.search([('sar_id', '=', sar_id), ('component', '=', comp)])
            if existing:
                existing.write({'total_credits': vals['credits'], 'total_contact_hours': vals['hours']})
            else:
                self.create({
                    'sar_id': sar_id,
                    'component': comp,
                    'total_credits': vals['credits'],
                    'total_contact_hours': vals['hours'],
                })


class NBAC1CourseScheme(models.Model):
    """
    Table No. 1.2.2.1: Course teaching & learning scheme with L/T/P/SL hours.
    Required by NBA SAR Section 1.2.2 - one row per course in the program.
    """
    _name = 'nba.c1.course.scheme'
    _description = 'NBA C1.2.2 - Course Teaching & Learning Scheme (L/T/P/SL)'
    _order = 'sar_id, semester_id, course_code'

    sar_id = fields.Many2one('nba.sar', string='SAR', required=True,
                             ondelete='cascade', index=True)
    course_id = fields.Many2one('university.course', string='Course', index=True)
    semester_id = fields.Many2one('university.semester', string='Semester',
                                  related='course_id.semester_id', store=True)

    # Filled from course_id or manually entered
    course_code = fields.Char(string='Course Code', required=True)
    course_title = fields.Char(string='Course Title', required=True)

    # ── Classroom Instruction (CI) hours/semester ─────────────────────────────
    ci_lecture = fields.Integer(string='L – Lecture Hours/Sem', default=0)
    ci_tutorial = fields.Integer(string='T – Tutorial Hours/Sem', default=0)
    # Lab Instruction
    li_practical = fields.Integer(string='P – Practical Hours/Sem', default=0)
    # Term Work / Self Learning
    tw_term_work = fields.Integer(string='TW – Term Work Hours/Sem', default=0)
    sl_self_learning = fields.Integer(string='SL – Self Learning Hours/Sem', default=0)

    # Computed totals
    total_hours_per_sem = fields.Integer(
        string='Total Hours/Semester',
        compute='_compute_totals', store=True
    )
    total_credits = fields.Float(
        string='Total Credits (Total Hours / 30)',
        compute='_compute_totals', store=True,
        digits=(5, 2)
    )

    course_type = fields.Selection(related='course_id.course_type', store=True, readonly=True)

    @api.depends('ci_lecture', 'ci_tutorial', 'li_practical', 'tw_term_work', 'sl_self_learning')
    def _compute_totals(self):
        for rec in self:
            total = (rec.ci_lecture + rec.ci_tutorial + rec.li_practical +
                     rec.tw_term_work + rec.sl_self_learning)
            rec.total_hours_per_sem = total
            # NBA National Credit Framework: 30 hrs = 1 credit
            rec.total_credits = round(total / 30.0, 2)

    @api.onchange('course_id')
    def _onchange_course_id(self):
        if self.course_id:
            self.course_code = self.course_id.code or ''
            self.course_title = self.course_id.name or ''
            # Auto-fill hours from course model if available
            c = self.course_id
            self.ci_lecture = getattr(c, 'theory_credits', 0) * 14 or 0
            self.li_practical = getattr(c, 'practical_credits', 0) * 28 or 0

    @api.model
    def populate_from_program(self, sar_id):
        """Auto-populate Table 1.2.2.1 from all courses in the program."""
        sar = self.env['nba.sar'].browse(sar_id)
        if not sar.program_id:
            return
        courses = self.env['university.course'].search([
            ('program_id', '=', sar.program_id.id)
        ], order='semester_id, id')
        for c in courses:
            existing = self.search([('sar_id', '=', sar_id), ('course_id', '=', c.id)])
            if existing:
                continue
            # Estimate hours: theory courses use lecture+tutorial, labs use practical
            is_lab = c.course_type in ('practical', 'lab')
            total_h = c.total_hours or (c.credits * 30 if c.credits else 0)
            li_h = total_h if is_lab else 0
            ci_l = 0 if is_lab else int(total_h * 0.75)
            ci_t = 0 if is_lab else int(total_h * 0.25)
            self.create({
                'sar_id': sar_id,
                'course_id': c.id,
                'course_code': c.code or '',
                'course_title': c.name or '',
                'ci_lecture': ci_l,
                'ci_tutorial': ci_t,
                'li_practical': li_h,
            })