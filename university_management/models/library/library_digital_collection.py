# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class LibraryDigitalCollection(models.Model):
    """
    Represents a digital database or collection — e.g. IEEE Xplore,
    Springer Link, JSTOR, NPTEL, ShodhGanga, internal repository.
    Resources belong to collections; access can be licensed or open.
    """
    _name = 'library.digital.collection'
    _description = 'Digital Library Collection / Database'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char(string='Collection Name', required=True, tracking=True)
    code = fields.Char(string='Code', copy=False)
    logo = fields.Binary(string='Logo / Icon', attachment=True)

    collection_type = fields.Selection([
        ('ebook_platform', 'E-Book Platform'),
        ('journal_database', 'Journal / Article Database'),
        ('video_lectures', 'Video Lecture Platform'),
        ('research_thesis', 'Research & Thesis Repository'),
        ('open_access', 'Open Access Repository'),
        ('internal', 'Internal Repository'),
        ('other', 'Other'),
    ], string='Type', required=True, default='ebook_platform', tracking=True)

    provider = fields.Char(string='Provider / Publisher')
    website_url = fields.Char(string='Platform URL')
    access_url = fields.Char(
        string='Authenticated Access URL',
        help='URL used for IP-authenticated or login-based access')
    description = fields.Html(string='Description')

    # License / Subscription
    is_subscribed = fields.Boolean(
        string='Subscribed / Licensed', default=True, tracking=True)
    subscription_start = fields.Date(string='Subscription Start')
    subscription_end = fields.Date(string='Subscription End')
    is_subscription_active = fields.Boolean(
        string='Subscription Active',
        compute='_compute_subscription_active', store=True)
    license_note = fields.Text(string='License / Usage Terms')

    # Access control
    access_type = fields.Selection([
        ('open', 'Open Access — No login required'),
        ('ip', 'IP-Based — Campus network only'),
        ('login', 'Login Required'),
        ('vpn', 'VPN / Proxy Required'),
    ], string='Access Method', default='login')

    # Resources under this collection
    resource_ids = fields.One2many(
        'library.digital.resource', 'collection_id',
        string='Digital Resources')
    resource_count = fields.Integer(
        string='Resources', compute='_compute_resource_count', store=True)

    # Contact
    contact_person = fields.Char(string='Contact / Rep Name')
    contact_email = fields.Char(string='Contact Email')

    active = fields.Boolean(default=True)
    notes = fields.Text(string='Internal Notes')

    # -------------------------------------------------------------------------
    # Compute
    # -------------------------------------------------------------------------

    @api.depends('subscription_start', 'subscription_end', 'is_subscribed')
    def _compute_subscription_active(self):
        today = fields.Date.today()
        for rec in self:
            if not rec.is_subscribed:
                rec.is_subscription_active = False
            elif rec.subscription_end:
                rec.is_subscription_active = rec.subscription_end >= today
            else:
                rec.is_subscription_active = True

    @api.depends('resource_ids')
    def _compute_resource_count(self):
        for rec in self:
            rec.resource_count = len(rec.resource_ids)

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    @api.constrains('subscription_start', 'subscription_end')
    def _check_subscription_dates(self):
        for rec in self:
            if rec.subscription_start and rec.subscription_end:
                if rec.subscription_end < rec.subscription_start:
                    raise ValidationError(
                        _('Subscription end date must be after start date.'))

    def action_view_resources(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Resources — %s') % self.name,
            'res_model': 'library.digital.resource',
            'view_mode': 'list,kanban,form',
            'domain': [('collection_id', '=', self.id)],
            'context': {'default_collection_id': self.id},
        }