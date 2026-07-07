# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class MultipleAcademicRecordsWizard(models.TransientModel):
    _name = "multiple.academic.records"
    _description = "Wizard: 'Create Multiple Academic Records'"

    yro = fields.Integer(default=fields.date.today().year, string=_("Office Year"), required=True)
    level_id = fields.Many2one("level", string=_('Level'))
    department_id = fields.Many2one("department", string=_('Department'))
    sub_department_id = fields.Many2one("sub.department", string=_('Division'),
                                        domain="[('department_id', '=', department_id)]")
    type = fields.Selection([('class', 'Number Of Classes'), ('student', 'Students In Classes')],
                            string=_('Distribution Type'))
    type_committees = fields.Selection(
        [('committee', 'Number Of Committees'), ('student_committee', 'Students In Committees')],
        string=_('Distribution Type'))
    number = fields.Integer(string=_("Number"), default=1)
    symbol = fields.Char(string=_("Symbol"))
    select_option = fields.Selection(
        [('classes', 'Classes'), ('committees', 'Committees'), ('sitting_number', 'Sitting Number')],
        string=_('Select Option'))
    is_print_report = fields.Boolean()
    number_two = fields.Char(string='Sitting Number')

    def action_multiple_academic_records(self):
        """
           This method performs different actions based on the selected options, such as generating reports,
           assigning class numbers, committee numbers, or sitting numbers to education records.
           """
        if self.level_id and self.department_id and self.sub_department_id and self.yro:
            no_of_student: int = 0
            education_records = self.env['education.record'].search(
                [('level_id', '=', self.level_id.id), ('department_id', '=', self.department_id.id),
                 ('sub_department_id', '=', self.sub_department_id.id), ('yro', '=', self.yro)], order='name')
            if self.select_option == 'classes':
                if self.select_option == 'classes' and self.is_print_report == False:
                    if self.type == 'student':
                        no_of_student = self.number
                    elif self.type == 'class':
                        no_of_student = int(len(education_records) / self.number)
                    cur_class: int = 1
                    cur_cap: int = 0
                    for rec in education_records:
                        rec.class_number = cur_class
                        cur_cap += 1
                        if cur_cap == no_of_student:
                            cur_class += 1
                            cur_cap = 0
                else:
                    records = self.env['education.record'].search(
                        [('level_id', '=', self.level_id.id), ('department_id', '=', self.department_id.id),
                         ('sub_department_id', '=', self.sub_department_id.id),
                         ('yro', '=', self.yro)])

                    get_records_classes= records.filtered(lambda x: x.class_number == self.number)
                    data = {
                        'form': {
                            'records_classes': get_records_classes.read(),
                            'records': records.read(),
                            'level_id': self.level_id.name,
                            'department_id': self.department_id.name,
                            'sub_department_id': self.sub_department_id.name,
                            'yro': self.yro,
                            'number': self.number,
                        }
                    }
                    return self.env.ref('nthub_ems.classes_wizard_reports').report_action(self, data=data)

            elif self.select_option == 'committees':
                if self.select_option == 'committees' and self.is_print_report == False:
                    if self.type_committees == 'student_committee':
                        no_of_student = self.number
                    elif self.type_committees == 'committee':
                        no_of_student = int(len(education_records) / self.number)
                    cur_committee: int = 1
                    cur_cap: int = 0
                    for rec in education_records:
                        rec.committees_number = cur_committee
                        cur_cap += 1
                        rec.chair_number = cur_cap
                        if cur_cap == no_of_student:
                            cur_committee += 1
                            cur_cap = 0
                else:
                    records = self.env['education.record'].search(
                        [('level_id', '=', self.level_id.id), ('department_id', '=', self.department_id.id),
                         ('sub_department_id', '=', self.sub_department_id.id),
                         ('yro', '=', self.yro)])

                    get_records_commites = records.filtered(lambda x: x.committees_number == self.number)
                    data = {
                        'form': {
                            'records_commites': get_records_commites.read(),
                            'records': records.read(),
                            'level_id': self.level_id.name,  # Convert records to dictionary format
                            'department_id': self.department_id.name,  # Convert records to dictionary format
                            'sub_department_id': self.sub_department_id.name,  # Convert records to dictionary format
                            'yro': self.yro,
                            'number': self.number,

                        }
                    }
                    return self.env.ref('nthub_ems.commit_wizard_reports').report_action(self, data=data)

            elif self.select_option == 'sitting_number':
                if self.select_option == 'sitting_number' and self.is_print_report == False:
                    count = 0
                    for sit in education_records:
                        if self.symbol:
                            sit.sitting_number = self.symbol + f"{self.number + count}"
                            count += 1
                else:
                    records = self.env['education.record'].search(
                        [('level_id', '=', self.level_id.id), ('department_id', '=', self.department_id.id),
                        ('sub_department_id', '=', self.sub_department_id.id),
                        ('yro', '=', self.yro)])
                    if self.number_two:
                        get_record_sitting = records.filtered(lambda x: x.sitting_number == self.number_two)
                        data = {
                            'form': {
                                'record': get_record_sitting.read()[0],  # Convert records to dictionary format
                                'level_id': self.level_id.name,  # Convert records to dictionary format
                                'department_id': self.department_id.name,  # Convert records to dictionary format
                                'sub_department_id': self.sub_department_id.name,
                                'yro': self.yro,  # Convert records to dictionary format
                                'number_two': self.number_two,  # Convert records to dictionary format
                                # Add any other required parameters to the 'form' dictionary
                            }
                        }
                        return self.env.ref('nthub_ems.sitting_wizard_reports').report_action(self, data=data)
                    else:
                        data = {
                            'form': {
                                'records': records.read(),  # Convert records to dictionary format
                                'level_id': self.level_id.name,  # Convert records to dictionary format
                                'department_id': self.department_id.name,  # Convert records to dictionary format
                                'sub_department_id': self.sub_department_id.name,
                                'number_two': self.number_two,
                                'yro': self.yro,  # Convert records to dictionary format
                                # Add any other required parameters to the 'form' dictionary
                            }
                        }
                        return self.env.ref('nthub_ems.sitting_wizard_reports').report_action(self, data=data)

            return {
                'name': 'Academic Records',
                'view_mode': 'tree,form',
                'res_model': 'education.record',
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