
from odoo import models, fields

class ResUsers(models.Model):
    _inherit = 'res.users'

    faculty_id = fields.Many2one('faculty.faculty', string='Related Faculty',
                                 help='Link to faculty record if this user is a faculty member')

    def _get_parent_student_ids(self):
        """Get student IDs for parent users - used in record rules"""
        self.ensure_one()
        parent_records = self.env['student.parent'].search([
            ('user_id', '=', self.id)
        ])
        return parent_records.mapped('student_id').ids

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['faculty_id']

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['faculty_id']