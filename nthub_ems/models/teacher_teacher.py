# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class TeacherResPartnerInherit(models.Model):
    _inherit = 'res.partner'

    alternative_name = fields.Char(string=_('Alternative Name'))
    is_teacher = fields.Boolean(string=_('Is Teacher'), default=False)
    subject_ids = fields.Many2many("subject", string=_('Subjects'))
    subject_domain = fields.Char(compute="_get_subject_instructor_domain")

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Name must be unique!'),
        ('alternative_name_unique', 'UNIQUE(alternative_name)', 'Alternative Name must be unique!'),
    ]

    def _get_subject_instructor_domain(self):
        """
           This method retrieves subject records related to the instructor and sets the domain
           for the subject selection field based on those records.
           """
        for rec in self:
            subject_records = self.env['subject'].search([])
            subject_instructor_records = subject_records.filtered(lambda r: rec.id in r.instructor_ids.ids)
            if subject_instructor_records:
                rec.subject_domain = subject_instructor_records.ids
            else:
                rec.subject_domain = False

