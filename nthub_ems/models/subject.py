# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class Subject(models.Model):
    _name = 'subject'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Subject'
    _rec_name = "name"

    name = fields.Char(string=_("Name"))
    alternative_name = fields.Char(string=_("Alternative Name"))
    level_id = fields.Many2one("level", string='Level')
    department_id = fields.Many2one("department", string='Department')
    sub_department_id = fields.Many2one("sub.department", string='Division',
                                        domain="[('department_id', '=', department_id)]")
    instructor_ids = fields.Many2many("res.partner", string='Instructor', domain="[('is_teacher','=',True)]")
    code = fields.Char(string=_("Code"))
    oral_mark = fields.Integer(string=_("Oral Full Mark"))
    mid_term_mark = fields.Integer(string=_("Mid Term Full Mark"))
    final_full_mark = fields.Integer(string=_("Final Full Mark"))
    total_mark = fields.Integer(string=_("Total Mark"), compute="_calc_total_mark", store=True)
    lecture_hours = fields.Integer(string=_("Lecture Hours"))
    section_hours = fields.Integer(string=_("Section Hours"))
    practical_hours = fields.Integer(string=_("Practical Hours"))
    final_exam_hours = fields.Integer(string=_("Exam Hours"))
    is_readonly = fields.Boolean()

    @api.model_create_multi
    def create(self, vals_list):
        """
        This method creates multiple records with the provided values.
        It sets the 'is_readonly' field to True for each record in the values list,
        ensuring that the records are read-only and not editable after creation.
       """
        for vals in vals_list:
            vals['is_readonly'] = True
        return super(Subject, self).create(vals_list)

    @api.onchange('oral_mark')
    def check_oral_mark(self):
        """
           This method checks the validity of the oral mark for each record when the oral mark changes.
           It ensures that the oral mark is not negative, raising a UserError if it is.
           """
        if self.oral_mark:
            if self.oral_mark < 0:
                raise UserError("You must enter degree more than Zero")

    @api.onchange('mid_term_mark')
    def check_mid_term_mark(self):
        """
            This method checks the validity of the mid-term mark for each record when the mid-term mark changes.
            It ensures that the mid-term mark is not negative, raising a UserError if it is.
            """
        if self.mid_term_mark:
            if self.mid_term_mark < 0:
                raise UserError("You must enter degree more than Zero")

    @api.onchange('final_full_mark')
    def check_final_full_mark(self):
        """
           This method checks the validity of the final full mark for each record when the final full mark changes.
           It ensures that the final full mark is not negative, raising a UserError if it is.
           """
        if self.final_full_mark:
            if self.final_full_mark < 0:
                raise UserError("You must enter degree more than Zero")

    @api.onchange('lecture_hours')
    def check_lecture_hours(self):
        """
           This method checks the validity of the lecture hours for each record when the lecture hours change.
           It ensures that the lecture hours are not negative, raising a UserError if they are.
           """
        if self.lecture_hours:
            if self.lecture_hours < 0:
                raise UserError("You must enter degree more than Zero")

    @api.onchange('section_hour')
    def check_section_hour(self):
        """
           This method checks the validity of the section hour for each record when the section hour changes.
           It ensures that the section hour is not negative, raising a UserError if it is.
           """
        if self.section_hour:
            if self.section_hour < 0:
                raise UserError("You must enter degree more than Zero")

    @api.onchange('practical_hour')
    def check_practical_hour(self):
        """
            This method checks the validity of the practical hour for each record when the practical hour changes.
            It ensures that the practical hour is not negative, raising a UserError if it is.
            """
        if self.practical_hour:
            if self.practical_hour < 0:
                raise UserError("You must enter degree more than Zero")

    @api.onchange('exam_hours')
    def exam_hours(self):
        """
            This method checks the validity of the exam hours for each record when the exam hours change.
            It ensures that the exam hours are not negative, raising a UserError if they are.
            """
        if self.exam_hours:
            if self.exam_hours < 0:
                raise UserError("You must enter degree more than Zero")

    @api.depends("oral_mark", "mid_term_mark", "final_full_mark")
    def _calc_total_mark(self):
        """
            This method calculates the total mark for each subject record by summing the oral mark,
            mid-term mark, and final full mark.
      """
        for rec in self:
            rec.total_mark = rec.oral_mark + rec.mid_term_mark + rec.final_full_mark

    def action_show_details(self):
        """
            This method creates a view to display details of a subject, such as its name, code, total mark,
            department, sub-department, and level.
            """
        self.ensure_one()
        view = {
            'name': 'Subject details',
            'view_mode': 'form',
            'res_model': 'subject',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_id': self.id,
            'context': {'default_name': self.name, 'default_level_id': self.level_id.id,
                        'default_department_id': self.department_id.id}, 'default_code': self.code,
            'default_total_mark': self.total_mark, 'default_sub_department_id': self.sub_department_id.id,
        }
        return view
