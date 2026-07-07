# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class IICSpeaker(models.Model):
    _name = 'iic.speaker'
    _description = 'IIC Speaker / Resource Person'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Speaker Name', required=True, tracking=True)
    designation = fields.Char(string='Designation', tracking=True)
    organization = fields.Char(string='Organization / Institution', tracking=True)
    email = fields.Char(string='Email')
    phone = fields.Char(string='Phone')
    photo = fields.Binary(string='Photo', attachment=True)
    profile = fields.Text(string='Speaker Profile / Bio')
    expertise = fields.Char(string='Area of Expertise')
    linkedin_url = fields.Char(string='LinkedIn Profile')

    event_ids = fields.One2many('iic.event', 'speaker_id', string='Events')
    event_count = fields.Integer(string='Total Events', compute='_compute_event_count')

    active = fields.Boolean(default=True)

    @api.depends('event_ids')
    def _compute_event_count(self):
        for rec in self:
            rec.event_count = len(rec.event_ids)

    def action_view_events(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Speaker Events',
            'res_model': 'iic.event',
            'view_mode': 'list,form',
            'domain': [('speaker_id', '=', self.id)],
        }
