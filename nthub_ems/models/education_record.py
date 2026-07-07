# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from lxml import etree


class EducationRecord(models.Model):
    _name = 'education.record'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Education Record'
    _rec_name = "yro"
    _order = "name"

    student_id = fields.Many2one("res.partner", string=_('Student'), required=True, domain="[('is_student','=',True)]")
    name = fields.Char(string=_('Name'), related='student_id.name', store=True)
    level_id = fields.Many2one("level", string=_('Level'))
    department_id = fields.Many2one("department", string=_('Department'))
    sub_department_id = fields.Many2one("sub.department", string=_('Division'),
                                        domain="[('department_id', '=', department_id)]")
    yro = fields.Integer(default=fields.date.today().year, string=_("Office Year"), required=True)
    eds = fields.Selection([('fresh', 'Fresh'), ('remaining', 'Remaining'), ('chance', 'Chance')],
                           string=_("Education State"))
    state = fields.Selection([('active', 'Active'), ('finished', 'Finished')], default='active', string=_("State"))
    class_number = fields.Integer(string=_('Class'))
    sitting_number = fields.Char(string=_("Sitting Number"))
    committees_number = fields.Integer(string=_("Committees Number"))
    chair_number = fields.Integer(string=_("Chair Number"))
    marks_ids = fields.One2many('marks', 'education_record_id')
    total_mark = fields.Float(compute='calc_total_mark', store=True, string=_("Total Marks"))
    year_percentage = fields.Float(compute='calc_year_percentage', store=True, string=_("Year Percentage"))
    nofs = fields.Float(string=_("No. of Failed Subjects"))
    is_readonly = fields.Boolean()

    _sql_constraints = [
        ('edu_record_unique', 'UNIQUE(student_id,yro)',
         'Must be "Student and Office Year" Unique'),
    ]

    def auto_change_state_eduction_record(self):
        max_year = self.env['ir.config_parameter'].search([('key', '=', 'nthub_ems.maxyro')])
        records = self.search([('state', '=', 'active'), ('yro', '<', max_year.value)])
        for rec in records:
            rec.state = 'finished'
            if rec.year_percentage >= 0.50 and rec.level_id.final_year == True:
                rec.student_id.is_graduate = True

    def action_active(self):
        """
           This method sets the state of records to 'active'.
           """
        for rec in self:
            rec.state = 'active'
            for mark in rec.marks_ids:
                mark.state = 'draft'

    def action_finished(self):
        """
           This method sets the state of records to 'finished'.
           """
        for rec in self:
            rec.state = 'finished'
            for mark in rec.marks_ids:
                mark.state = 'confirm'

    @api.model
    def get_view(self, view_id=None, view_type='search', **options):
        """
           This method fetches a specific view by its ID and type, and optionally applies additional options.
           If the view type is 'search', it modifies the search filter to restrict results based on a maximum year parameter.
           :param view_id: The ID of the view to retrieve.
           """
        res = super(EducationRecord, self).get_view(view_id=view_id, view_type=view_type, options=options)
        if view_type == 'search':
            doc = etree.XML(res['arch'])
            search_filter = doc.xpath("//filter[@name='max_year']")
            if search_filter:
                max_year_parameter_id = self.env['ir.config_parameter'].search([('key', '=', 'nthub_ems.maxyro')])
                # self.env.cr.execute("select max(yro) from education_record as yro;")
                # result = self.env.cr.fetchone()
                search_filter[0].set("domain", f"[('yro', '=', {max_year_parameter_id.value})]")
            res['arch'] = etree.tostring(doc, encoding='unicode')
        return res

    @api.model_create_multi
    def create(self, vals_list):
        """
            This method creates multiple records with the provided values.
            It sets the 'is_readonly' field to True for each created record.
            Additionally, it retrieves the maximum year value from the created records and updates a configuration parameter accordingly.
            :return: A recordset containing the created records.
            """
        for vals in vals_list:
            vals['is_readonly'] = True
        res = super(EducationRecord, self).create(vals_list)
        self.env.cr.execute("select max(yro) from education_record as yro;")
        result = self.env.cr.fetchone()
        self.env['ir.config_parameter'].set_param('nthub_ems.maxyro', result[0])
        return res

    @api.depends('marks_ids.total_mark', 'marks_ids')
    def calc_total_mark(self):
        """
           Calculate total marks.
           This method calculates the total marks for each record.
           It sums the total marks of searched in model Marks where the subject level percentage is greater than or equal to 50%.
           :return: None
           """
        for rec in self:
            total = 0
            search_marks = self.env['marks'].search(
                [('student_id', '=', rec.student_id.id), ('subject_id.level_id', '=', rec.level_id.id),
                 ('percentage', '>=', 0.50)])
            for line in search_marks:
                if line.percentage >= 0.50:
                    total += line.total_mark
                else:
                    total = 0
                    break
            rec.total_mark = total

    @api.depends("total_mark", "level_id")
    def calc_year_percentage(self):
        """
           This method calculates the year percentage for each record based on the total mark and the sum of marks for the level.
           If the total mark and the sum of marks for the level are both available, it computes the percentage.
           """
        for rec in self:
            if rec.total_mark > 0 and rec.level_id.sum_mark_level > 0:
                rec.year_percentage = rec.total_mark / rec.level_id.sum_mark_level
            else:
                rec.year_percentage = False

    def action_multiple_academic_records(self):
        """
            Action for opening multiple academic records form
            This method returns an action dictionary to open a form for multiple academic records.
            It specifies the name of the action, view mode, view type, model, and target window.
            """
        return {
            'name': 'Multiple Academic Records',
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'multiple.academic.records',
            'type': 'ir.actions.act_window',
            'target': 'new',
        }
