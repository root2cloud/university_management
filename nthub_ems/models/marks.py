# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import json


class Marks(models.Model):
    _name = 'marks'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'marks'
    _rec_name = 'name'

    name = fields.Char(compute='_compute_name')
    student_id = fields.Many2one("res.partner", string=_('Student'), domain="[('is_student','=',True)]")
    sitting_number = fields.Char(string=_("Sitting Number"), related='education_record_id.sitting_number')
    education_record_id = fields.Many2one("education.record", string=_('Education Record'))
    office_year = fields.Integer(string=_('Office Year'))
    subject_id = fields.Many2one("subject", string=_('Subject'), required=True)
    subjects_domain_ids = fields.Many2many("subject", compute='_compute_subjects_domain_ids', store=True)
    oral_mark = fields.Integer(string=_("Oral Mark"))
    term_mark = fields.Integer(string=_("Mid Term Mark"))
    final_mark = fields.Integer(string=_("Final Mark"))
    total_mark = fields.Integer(string=_("Total Mark"), compute='_calc_total_mark', store=True)
    # subject_id_domain = fields.Char(compute='_compute_subject_id_domain', readonly=True, store=False)
    percentage = fields.Float(string=_("Percentage"), compute="_calc_subject_percentage", store=True)
    degree = fields.Selection(
        [('good', 'Good'), ('very_good', 'Very Good'), ('excellent', 'Excellent'), ('pass', 'Pass'), ('fall', 'Fall'),
         ('a', 'A'), ('b', 'B'), ('c', 'C'), ('d', 'D'), ('f', 'F')],
        string="Degree", compute='_calc_degree')
    state = fields.Selection([('draft', 'Draft'), ('confirm', 'Confirmed')], default='draft')
    is_readonly = fields.Boolean()

    _sql_constraints = [
        ('mrk_record_unique', 'UNIQUE(student_id,office_year,subject_id)',
         'Must be "Student and Office Year and Subject" Unique'),
    ]

    def action_confirm(self):
        """ This method confirms records by setting their state to 'confirm'.  """
        for rec in self:
            rec.state = 'confirm'

    def _get_value_letters(self):
        """
           This method retrieves the value for letters evaluation type from the configuration parameters.
           If the evaluation type is set to 'letters', it sets the 'is_letters' field to True for each record.
           Otherwise, it sets the field to False.
           """
        for rec in self:
            evaluation_type = self.env['ir.config_parameter'].search([('key', '=', 'nthub_ems.evaluation_type')])
            if evaluation_type.value == 'letters':
                rec.is_letters = True
            else:
                rec.is_letters = False

    @api.depends("education_record_id", "subject_id")
    def _compute_name(self):
        """
            This method computes the name for each record based on the education record and subject.
            If the sitting number and subject are available, it combines them to form the name.
            Otherwise, it sets a default name using the subject code
            """
        for rec in self:
            if rec.sitting_number and rec.subject_id:
                rec.name = f'{rec.subject_id.code} / {rec.sitting_number}'
            else:
                rec.name = f'{rec.subject_id.code} / 000'

    # @api.model_create_multi
    @api.model
    def create(self, vals_list):
        """
           This method creates multiple records with the provided values.
           It sets the 'is_readonly' field to True for the first record in the list.
           If the education record ID is provided in the values list, it retrieves related information such as student ID and office year.
           """
        res = super(Marks, self).create(vals_list)
        res.is_readonly = True
        if res.education_record_id:
            res.student_id = res.education_record_id.student_id
            res.office_year = res.education_record_id.yro
        else:
            edu_record = self.env['education.record'].sudo().search(
                [('student_id', '=', res.student_id.id), ('yro', '=', res.office_year)])
            if edu_record:
                res.education_record_id = edu_record
            else:
                raise ValidationError(_('This student has no Education Record in this year.'))
        return res

    @api.depends('percentage')
    def _calc_degree(self):
        """
           This method calculates the degree for each record based on the percentage.
           It checks the evaluation type from configuration parameters and assigns the degree accordingly.
           For the 'degree' evaluation type, it assigns degrees such as 'excellent', 'very_good', 'good', 'pass', or 'fail'
           based on percentage thresholds.
           """
        for record in self:
            evaluation_type = self.env['ir.config_parameter'].search([('key', '=', 'nthub_ems.evaluation_type')])
            if evaluation_type.value == 'degree' or evaluation_type.value == '':
                if record.percentage >= 0.85:
                    record.degree = 'excellent'
                elif record.percentage >= 0.75:
                    record.degree = 'very_good'
                elif record.percentage >= 0.65:
                    record.degree = 'good'
                elif record.percentage >= 0.50:
                    record.degree = 'pass'
                else:
                    record.degree = 'fall'
            elif evaluation_type.value == 'letters':
                if record.percentage >= 0.85:
                    record.degree = 'a'
                elif record.percentage >= 0.75:
                    record.degree = 'b'
                elif record.percentage >= 0.65:
                    record.degree = 'c'
                elif record.percentage >= 0.50:
                    record.degree = 'd'
                else:
                    record.degree = 'f'

    @api.depends('education_record_id.level_id')
    def _compute_subjects_domain_ids(self):
        """
    This method calculates the domain of subjects for each record based on the education record's level.
    It retrieves the subject IDs associated with the education record and its level.
    Then, it filters out subjects where the student has already scored below 50% and subjects the student has passed.
    Finally, it constructs a domain for subjects not yet taken by the student.e
    """
        for rec in self:
            subject_ids = self.env['subject'].search([('level_id', '=', rec.education_record_id.level_id.id)])
            m_objects = self.search([('education_record_id.student_id', '=', rec.education_record_id.student_id.id)])
            if m_objects:
                full_subject_ids = m_objects.filtered(lambda s: s.percentage < 0.50).mapped('subject_id')
                pass_subject_ids = m_objects.filtered(lambda s: s.percentage >= 0.50).mapped('subject_id')
                diff_subject_ids = False
                for subject in full_subject_ids:
                    if subject in pass_subject_ids:
                        continue
                    else:
                        if diff_subject_ids == False:
                            diff_subject_ids = subject
                        else:
                            diff_subject_ids += subject
                if diff_subject_ids:
                    sum_subject_ids = subject_ids + diff_subject_ids
                else:
                    sum_subject_ids = subject_ids
                rec.subjects_domain_ids = sum_subject_ids
            else:
                rec.subjects_domain_ids = subject_ids
    # @api.depends('education_record_id.level_id')
    # def _compute_subject_id_domain(self):
    #     """
    # This method calculates the domain of subjects for each record based on the education record's level.
    # It retrieves the subject IDs associated with the education record and its level.
    # Then, it filters out subjects where the student has already scored below 50% and subjects the student has passed.
    # Finally, it constructs a domain for subjects not yet taken by the student.e
    # """
    #     for rec in self:
    #         selected_subject_ids = rec.education_record_id.marks_ids.mapped('subject_id.id')
    #         subject_ids = self.env['subject'].search([('level_id', '=', rec.education_record_id.level_id.id)]).ids
    #         m_objects = self.search([('education_record_id.student_id', '=', rec.education_record_id.student_id.id)])
    #         full_subject_ids = m_objects.filtered(lambda s: s.percentage < 0.50).mapped('subject_id.id')
    #         pass_subject_ids = m_objects.filtered(lambda s: s.percentage >= 0.50).mapped('subject_id.id')
    #         # Calculate the difference between full_subject_ids and pass_subject_ids
    #         subject_ids = subject_ids + list(set(full_subject_ids) - set(pass_subject_ids))
    #         available_subject_ids = [i for i in subject_ids if i not in selected_subject_ids]
    #         unique_subject_ids = available_subject_ids
    #         rec.subject_id_domain = json.dumps([('id', 'in', unique_subject_ids)])

    @api.onchange("subject_id", 'oral_mark')
    def check_oral_mark(self):
        """
            This method checks the validity of the oral mark for each record when the subject or oral mark changes.
            If both the subject and oral mark are provided, it compares the oral mark against the maximum allowed oral mark for the subject.
            If the oral mark exceeds the maximum or is negative, it resets the oral mark to the maximum allowed value for the subject.
            """
        if self.subject_id and self.oral_mark:
            if self.oral_mark > self.subject_id.oral_mark or self.oral_mark < 0:
                self.oral_mark = self.subject_id.oral_mark

    @api.onchange("subject_id", 'term_mark')
    def check_term_mark(self):
        """
            This method checks the validity of the term mark for each record when the subject or term mark changes.
            If both the subject and term mark are provided, it compares the term mark against the maximum allowed term mark for the subject.
            If the term mark exceeds the maximum or is negative, it resets the term mark to the maximum allowed value for the subject.
            """
        if self.subject_id and self.term_mark:
            if self.term_mark > self.subject_id.mid_term_mark or self.term_mark < 0:
                self.term_mark = self.subject_id.mid_term_mark

    @api.onchange("subject_id", 'final_mark')
    def check_final_mark(self):
        """
            This method checks the validity of the final mark for each record when the subject or final mark changes.
            If both the subject and final mark are provided, it compares the final mark against the maximum allowed final mark for the subject.
            If the final mark exceeds the maximum, it resets the final mark to the maximum allowed value for the subject.
            """
        if self.subject_id and self.final_mark:
            if self.final_mark > self.subject_id.final_full_mark:
                self.final_mark = self.subject_id.final_full_mark

    @api.depends("oral_mark", "term_mark", "final_mark")
    def _calc_total_mark(self):
        """
    This method calculates the total mark for each record based on the oral mark, term mark, and final mark.
    If the final mark is greater than 0, it includes it in the calculation; otherwise, it excludes it.
    """
        for rec in self:
            if rec.final_mark > 0:
                rec.total_mark = rec.oral_mark + rec.term_mark + rec.final_mark
            else:
                rec.total_mark = rec.oral_mark + rec.term_mark

    @api.depends('total_mark', 'subject_id')
    def _calc_subject_percentage(self):
        """
    This method calculates the percentage of the subject mark for each record based on the total mark and subject.
    If both the subject and total mark are provided, it computes the percentage by dividing the total mark by the subject's total mark.
    Otherwise, it sets the percentage to False.
    """
        for rec in self:
            if rec.subject_id or rec.total_mark:
                if rec.subject_id.total_mark > 0:
                    rec.percentage = rec.total_mark / rec.subject_id.total_mark
            else:
                rec.percentage = False
