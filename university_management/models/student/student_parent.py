# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class StudentParent(models.Model):
    _name = 'student.parent'
    _description = 'Student Parent/Guardian Details'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _inherits = {'res.partner': 'partner_id'}
    _order = 'student_id, relationship'

    # Partner (inherited)
    partner_id = fields.Many2one('res.partner', string='Related Partner',
                                 required=True, ondelete='cascade', auto_join=True)

    # Student
    student_id = fields.Many2one('student.student', string='Student',
                                 required=True, tracking=True, index=True, ondelete='cascade')
    student_name = fields.Char(related='student_id.name', string='Student Name')

    # Relationship
    relationship = fields.Selection([
        ('father', 'Father'),
        ('mother', 'Mother'),
        ('guardian', 'Guardian'),
        ('brother', 'Brother'),
        ('sister', 'Sister'),
        ('grandfather', 'Grandfather'),
        ('grandmother', 'Grandmother'),
        ('uncle', 'Uncle'),
        ('aunt', 'Aunt'),
        ('other', 'Other'),
    ], string='Relationship', required=True, tracking=True)

    # Photo
    photo = fields.Binary(string='Photo', attachment=True)

    # Occupation
    occupation = fields.Char(string='Occupation')
    company_name = fields.Char(string='Company Name')
    designation = fields.Char(string='Designation')
    annual_income = fields.Monetary(string='Annual Income', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Education
    education_qualification = fields.Char(string='Education Qualification')

    # Office Contact
    office_phone = fields.Char(string='Office Phone')
    office_address = fields.Text(string='Office Address')

    # Contact Preferences
    is_primary_contact = fields.Boolean(string='Primary Contact', default=False)
    is_emergency_contact = fields.Boolean(string='Emergency Contact', default=False)
    contact_time_preference = fields.Selection([
        ('morning', 'Morning (9 AM - 12 PM)'),
        ('afternoon', 'Afternoon (12 PM - 4 PM)'),
        ('evening', 'Evening (4 PM - 8 PM)'),
        ('anytime', 'Anytime'),
    ], string='Preferred Contact Time', default='anytime')

    # Portal Access
    user_id = fields.Many2one('res.users', string='Portal User')
    has_portal_access = fields.Boolean(string='Has Portal Access',
                                       compute='_compute_portal_access', store=True)

    # Living Status
    is_alive = fields.Boolean(string='Alive', default=True)

    # Government IDs
    aadhar_number = fields.Char(string='Aadhar Number')
    pan_number = fields.Char(string='PAN Number')

    # Notes
    notes = fields.Text(string='Notes')

    @api.depends('user_id')
    def _compute_portal_access(self):
        for record in self:
            record.has_portal_access = bool(record.user_id)

    @api.constrains('is_primary_contact', 'student_id')
    def _check_primary_contact(self):
        for record in self:
            if record.is_primary_contact:
                other_primary = self.search([
                    ('id', '!=', record.id),
                    ('student_id', '=', record.student_id.id),
                    ('is_primary_contact', '=', True)
                ])
                if other_primary:
                    raise ValidationError(_('Only one parent can be primary contact!'))

    def action_create_portal_user(self):
        """Create portal user for parent.

            NOTE: Direct SQL is used intentionally for group assignment because
            Odoo's _check_one_user_type() constraint auto-assigns all groups in
            the same category when using ORM. Since group_parent_portal and
            group_student_portal are in module_category_university, the ORM
            always assigns both. Direct SQL bypasses this constraint safely
            since res_groups_users_rel is a stable core Odoo table.

        """
        self.ensure_one()
        if not self.user_id and self.email:
            group_portal = self.env.ref('base.group_portal')
            group_parent = self.env.ref('university_management.group_parent_portal')
            group_student = self.env.ref('university_management.group_student_portal')

            # Create user with base portal only
            user = self.env['res.users'].create({
                'name': self.name,
                'login': self.email,
                'email': self.email,
                'partner_id': self.partner_id.id,
                'groups_id': [(6, 0, [group_portal.id])],
            })

            # Use direct SQL to bypass Odoo ORM group constraints
            self.env.cr.execute(
                "DELETE FROM res_groups_users_rel WHERE uid = %s AND gid = %s",
                (user.id, group_student.id)
            )
            self.env.cr.execute(
                "INSERT INTO res_groups_users_rel (gid, uid) VALUES (%s, %s) "
                "ON CONFLICT DO NOTHING",
                (group_parent.id, user.id)
            )
            user.invalidate_recordset(['groups_id'])
            self.env['ir.rule'].clear_caches()
            self.user_id = user.id
