# -*- coding: utf-8 -*-

from odoo import models, fields, api,_


class Level(models.Model):
    _name = 'level'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Level'
    _rec_name = "name"

    name = fields.Char(string=_("Name"))
    alternative_name = fields.Char(string=_("Alternative Name"))
    subject_line_ids = fields.One2many("subject", "level_id")
    sum_mark_level = fields.Float(compute='_calc_sum_mark_level', store=True, string="Level Total Mark")
    final_year = fields.Boolean(string=_("Final Year"), default=False)

    @api.depends("subject_line_ids.total_mark")
    def _calc_sum_mark_level(self):
        """
           This method calculates the sum of marks for subjects within the level for each record.
           It sums the total marks of all subject lines associated with the record.
           """
        for rec in self:
            rec.sum_mark_level = sum(rec.subject_line_ids.mapped('total_mark'))


