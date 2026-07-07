# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FacultyEvaluation(models.Model):
    _name = 'faculty.evaluation'
    _description = 'Faculty Performance Evaluation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'evaluation_date desc'

    name = fields.Char(string='Evaluation Number', required=True, readonly=True,
                       copy=False, default='/')

    faculty_id = fields.Many2one('faculty.faculty', string='Faculty',
                                 required=True, tracking=True, index=True)
    department_id = fields.Many2one(related='faculty_id.department_id', string='Department', store=True)
    designation_id = fields.Many2one(related='faculty_id.designation_id', string='Designation', store=True)

    evaluation_period = fields.Selection([
        ('monthly',   'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semester',  'Semester'),
        ('annual',    'Annual'),
    ], string='Evaluation Period', required=True, default='semester')

    evaluation_date = fields.Date(string='Evaluation Date', default=fields.Date.today(),
                                  required=True, tracking=True)
    academic_year_id = fields.Many2one('university.academic.year', string='Academic Year')
    semester_id = fields.Many2one('university.semester', string='Semester')

    evaluation_type = fields.Selection([
        ('student', 'Student Feedback'),
        ('peer',    'Peer Review'),
        ('hod',     'HOD Assessment'),
        ('self',    'Self Assessment'),
        ('annual',  'Annual Performance Review'),
    ], string='Evaluation Type', required=True, default='student', tracking=True)

    survey_id = fields.Many2one('survey.survey', string='Feedback Survey')
    evaluated_by = fields.Many2one('res.users', string='Evaluated By',
                                   default=lambda self: self.env.user)
    evaluator_faculty_id = fields.Many2one('faculty.faculty', string='Evaluator Faculty')

    # Ratings
    teaching_quality = fields.Float(string='Teaching Quality (1-10)', default=5.0)
    subject_knowledge = fields.Float(string='Subject Knowledge (1-10)', default=5.0)
    communication_skills = fields.Float(string='Communication Skills (1-10)', default=5.0)
    punctuality = fields.Float(string='Punctuality (1-10)', default=5.0)
    student_interaction = fields.Float(string='Student Interaction (1-10)', default=5.0)
    course_coverage = fields.Float(string='Course Coverage (1-10)', default=5.0)
    assessment_fairness = fields.Float(string='Assessment Fairness (1-10)', default=5.0)
    research_contribution = fields.Float(string='Research Contribution (1-10)', default=5.0)
    administrative_work = fields.Float(string='Administrative Work (1-10)', default=5.0)

    overall_rating = fields.Float(string='Overall Rating', compute='_compute_overall_rating', store=True, compute_sudo=True)
    performance_grade = fields.Selection([
        ('outstanding',       'Outstanding'),
        ('excellent',         'Excellent'),
        ('good',              'Good'),
        ('satisfactory',      'Satisfactory'),
        ('needs_improvement', 'Needs Improvement'),
    ], string='Performance Grade', compute='_compute_grade', store=True, compute_sudo=True)

    strengths = fields.Html(string='Strengths')
    areas_of_improvement = fields.Html(string='Areas of Improvement')
    recommendations = fields.Html(string='Recommendations')
    action_plan = fields.Html(string='Action Plan')
    evaluator_comments = fields.Text(string='Evaluator Comments')
    faculty_comments = fields.Text(string='Faculty Comments/Response')

    state = fields.Selection([
        ('draft',     'Draft'),
        ('submitted', 'Submitted'),
        ('reviewed',  'Reviewed by Faculty'),
        ('approved',  'Approved'),
    ], string='Status', default='draft', tracking=True)

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Evaluation Number must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('faculty.evaluation') or '/'
        return super().create(vals)

    @api.depends('teaching_quality', 'subject_knowledge', 'communication_skills',
                 'punctuality', 'student_interaction', 'course_coverage',
                 'assessment_fairness', 'research_contribution', 'administrative_work')
    def _compute_overall_rating(self):
        for record in self:
            total = (record.teaching_quality + record.subject_knowledge +
                     record.communication_skills + record.punctuality +
                     record.student_interaction + record.course_coverage +
                     record.assessment_fairness + record.research_contribution +
                     record.administrative_work)
            record.overall_rating = total / 9

    @api.depends('overall_rating')
    def _compute_grade(self):
        for record in self:
            if record.overall_rating >= 9:
                record.performance_grade = 'outstanding'
            elif record.overall_rating >= 8:
                record.performance_grade = 'excellent'
            elif record.overall_rating >= 7:
                record.performance_grade = 'good'
            elif record.overall_rating >= 6:
                record.performance_grade = 'satisfactory'
            else:
                record.performance_grade = 'needs_improvement'

    @api.constrains('teaching_quality', 'subject_knowledge', 'communication_skills',
                    'punctuality', 'student_interaction', 'course_coverage',
                    'assessment_fairness', 'research_contribution', 'administrative_work')
    def _check_ratings(self):
        for record in self:
            for fname in ['teaching_quality', 'subject_knowledge', 'communication_skills',
                          'punctuality', 'student_interaction', 'course_coverage',
                          'assessment_fairness', 'research_contribution', 'administrative_work']:
                value = getattr(record, fname)
                if value < 0 or value > 10:
                    raise ValidationError(_('Rating must be between 0 and 10!'))

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_review(self):
        self.write({'state': 'reviewed'})

    def action_approve(self):
        self.write({'state': 'approved'})
        # ── Sync last appraisal date to hr.employee ───────────────────────
        for rec in self:
            if rec.faculty_id and rec.faculty_id.employee_id:
                try:
                    rec.faculty_id.employee_id.sudo().write({
                        'last_appraisal_date': rec.evaluation_date,
                    })
                except Exception:
                    pass

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})