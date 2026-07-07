# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class PlacementCompany(models.Model):
    _name = 'placement.company'
    _description = 'Placement Company Master'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _inherits = {'res.partner': 'partner_id'}  # Integration with contacts module
    _order = 'name'

    # Partner (for contact details)
    partner_id = fields.Many2one('res.partner', string='Related Partner',
                                 required=True, ondelete='cascade', auto_join=True)

    # Company Details
    company_type = fields.Selection([
        ('mnc', 'MNC'),
        ('corporate', 'Corporate'),
        ('startup', 'Startup'),
        ('psu', 'PSU'),
        ('government', 'Government'),
    ], string='Company Type', tracking=True)

    industry = fields.Selection([
        ('it', 'IT/Software'),
        ('core', 'Core Engineering'),
        ('finance', 'Finance/Banking'),
        ('consulting', 'Consulting'),
        ('manufacturing', 'Manufacturing'),
        ('healthcare', 'Healthcare'),
        ('education', 'Education'),
        ('retail', 'Retail'),
        ('other', 'Other'),
    ], string='Industry', tracking=True)

    # HR Contact
    hr_contact_name = fields.Char(string='HR Contact Name')
    hr_contact_email = fields.Char(string='HR Email')
    hr_contact_phone = fields.Char(string='HR Phone')

    # Placement History
    drive_ids = fields.One2many('placement.drive', 'company_id', string='Placement Drives')
    total_drives = fields.Integer(string='Total Drives', compute='_compute_stats', store=True)
    total_offers = fields.Integer(string='Total Offers', compute='_compute_stats')

    # Rating
    rating = fields.Selection([
        ('1', '1 Star'), ('2', '2 Stars'), ('3', '3 Stars'),
        ('4', '4 Stars'), ('5', '5 Stars'),
    ], string='Rating')

    # Status
    is_blacklisted = fields.Boolean(string='Blacklisted', tracking=True, store=True)
    blacklist_reason = fields.Text(string='Blacklist Reason')

    active = fields.Boolean(string='Active', default=True)

    @api.depends('drive_ids')
    def _compute_stats(self):
        for record in self:
            record.total_drives = len(record.drive_ids)
            record.total_offers = sum(record.drive_ids.mapped('total_offers'))

    def action_placement_drive(self):
        """Open all placement drives for this company."""
        self.ensure_one()
        return {
            'name': 'Placement Drives',
            'type': 'ir.actions.act_window',
            'res_model': 'placement.drive',
            'view_mode': 'list,form',
            'domain': [('company_id', '=', self.id)],
            'context': {
                'default_company_id': self.id,
            },
        }

    def action_placement_offer(self):
        """Open all placement offers for this company."""
        self.ensure_one()
        return {
            'name': 'Placement Offers',
            'type': 'ir.actions.act_window',
            'res_model': 'placement.offer',
            'view_mode': 'list,form',
            'domain': [('company_id', '=', self.id)],
            'context': {
                'default_company_id': self.id,
            },
        }



