# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class MultipleMarksWizard(models.TransientModel):
    _name = "multiple.marks"
    _description = "Wizard: 'Create Multiple Records' "

    yro = fields.Integer(default=fields.date.today().year, string=_("Office Year"), required=True)
    level_id = fields.Many2one("level", string=_('Level'))
    department_id = fields.Many2one("department", string=_('Department'))
    sub_department_id = fields.Many2one("sub.department", string=_('Division'),
                                        domain="[('department_id', '=', department_id)]")
    subject_id = fields.Many2one("subject", string=_("Subject"), required=True, domain="[('level_id','=',level_id)]")

    def action_create_multiple_records(self):
        """
         This method searches for education records based on the provided level, department,
         sub-department, and year of study. Then, it creates marks records for each matching
         education record, linking them to the specified subject.
         """
        if self.level_id and self.department_id and self.sub_department_id and self.yro:
            education_records = self.env['education.record'].search(
                [('level_id', '=', self.level_id.id), ('department_id', '=', self.department_id.id),
                 ('sub_department_id', '=', self.sub_department_id.id), ('yro', '=', self.yro)])
            for rec in education_records:
                self.env['marks'].sudo().create({
                    'student_id': rec.student_id.id,
                    'office_year': self.yro,
                    'subject_id': self.subject_id.id,
                })
            return {
                'name': 'Marks',
                'view_mode': 'tree,form',
                'res_model': 'marks',
                'type': 'ir.actions.act_window',
                'target': 'main',
            }

    # @api.onchange('level_id', 'department_id', 'sub_department_id', 'yro')
    # def get_students(self):
    #     self.student_ids = [(5, 0, 0)]
    #     if self.level_id and self.department_id and self.sub_department_id and self.yro:
    #         education_records = self.env['education.record'].search(
    #             [('level_id', '=', self.level_id.id), ('department_id', '=', self.department_id.id),
    #              ('sub_department_id', '=', self.sub_department_id.id), ('yro', '=', self.yro)])
    #         student_records = [line.student_id for line in education_records]
    #         for s in student_records:
    #             self.student_ids += s
    #     else:
    #         self.student_ids = False

