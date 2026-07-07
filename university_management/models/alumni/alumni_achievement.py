# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AlumniAchievement(models.Model):
    _name = 'alumni.achievement'
    _description = 'Alumni Achievements & Recognition'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'achievement_date desc'

    # Alumni
    alumni_id = fields.Many2one('alumni.alumni', string='Alumni',
                                required=True, tracking=True, index=True)
    alumni_name = fields.Char(related='alumni_id.name', string='Alumni Name')

    # Achievement Details
    achievement_type = fields.Selection([
        ('award', 'Award/Recognition'),
        ('publication', 'Research Publication'),
        ('patent', 'Patent'),
        ('entrepreneurship', 'Startup/Business Success'),
        ('promotion', 'Career Milestone/Promotion'),
        ('social', 'Social Impact'),
        ('other', 'Other'),
    ], string='Achievement Type', required=True, tracking=True)

    title = fields.Char(string='Achievement Title', required=True)
    description = fields.Html(string='Description')

    achievement_date = fields.Date(string='Achievement Date', tracking=True)

    # Organization/Institution
    organization = fields.Char(string='Organization/Institution')

    # Media
    image = fields.Binary(string='Image', attachment=True)
    certificate = fields.Binary(string='Certificate/Document', attachment=True)
    media_url = fields.Char(string='Media URL (News/Article)')

    # Visibility
    featured = fields.Boolean(string='Featured Achievement')
    publish_on_website = fields.Boolean(string='Publish on Website', default=True)

    # Status
    active = fields.Boolean(string='Active', default=True)
