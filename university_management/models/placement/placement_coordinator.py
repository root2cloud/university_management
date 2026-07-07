# -*- coding: utf-8 -*-

from odoo import models, fields, api


class PlacementCoordinator(models.Model):
    _name = 'placement.coordinator'
    _description = 'Placement Cell Coordinators'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    # Faculty
    faculty_id = fields.Many2one('faculty.faculty', string='Faculty',
                                 required=True, tracking=True)
    name = fields.Char(related='faculty_id.name', string='Name', store=True)
    email = fields.Char(related='faculty_id.work_email', string='Email')
    phone = fields.Char(related='faculty_id.work_mobile', string='Phone')
    image_1920 = fields.Image(
        related='faculty_id.image_1920',
        store=False,
        readonly=True,
        string='Photo',
    )
    image_128 = fields.Image(
        related='faculty_id.image_128',
        readonly=True,
        store=False,
        string='Photo (128px)',
    )

    # Role
    role = fields.Selection([
        ('head', 'Head - Placement Cell'),
        ('coordinator', 'Placement Coordinator'),
        ('assistant', 'Assistant Coordinator'),
    ], string='Role', required=True, tracking=True)

    # Department
    department_id = fields.Many2one(related='faculty_id.department_id',
                                    string='Department', store=True)

    # Placement Drives Managed
    drive_ids = fields.One2many('placement.drive', 'coordinator_id', string='Drives Managed')
    total_drives = fields.Integer(string='Total Drives', compute='_compute_total', store=True)

    # Status
    active = fields.Boolean(string='Active', default=True, store=True)

    @api.depends('drive_ids')
    def _compute_total(self):
        for record in self:
            record.total_drives = len(record.drive_ids)

    def action_placement_drive(self):
        """Open all placement drives managed by this coordinator."""
        self.ensure_one()
        return {
            'name': 'Placement Drives',
            'type': 'ir.actions.act_window',
            'res_model': 'placement.drive',
            'view_mode': 'list,form',
            'domain': [('coordinator_id', '=', self.id)],
            'context': {
                'default_coordinator_id': self.id,
            },
        }

