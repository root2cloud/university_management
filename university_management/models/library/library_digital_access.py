# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class LibraryDigitalAccess(models.Model):
    """
    Tracks every access event for a digital resource —
    view, download, or share. One record per access event.
    Used for usage analytics, quota enforcement, and audit.
    """
    _name = 'library.digital.access'
    _description = 'Digital Resource Access Log'
    _order = 'access_date desc'
    _rec_name = 'display_name'

    # -------------------------------------------------------------------------
    # Core fields
    # -------------------------------------------------------------------------

    resource_id = fields.Many2one(
        'library.digital.resource', string='Resource',
        required=True, ondelete='cascade', index=True)
    member_id = fields.Many2one(
        'library.member', string='Member',
        required=True, index=True)

    # Related stored for reporting/filtering
    member_name = fields.Char(
        related='member_id.member_name', string='Member Name', store=True)
    member_type = fields.Selection(
        related='member_id.member_type', string='Member Type', store=True)
    resource_type = fields.Selection(
        related='resource_id.resource_type', string='Resource Type', store=True)
    collection_id = fields.Many2one(
        related='resource_id.collection_id', string='Collection',
        store=True, readonly=True)

    # -------------------------------------------------------------------------
    # Access details
    # -------------------------------------------------------------------------

    access_date = fields.Datetime(
        string='Accessed On', default=fields.Datetime.now,
        required=True, index=True)
    access_type = fields.Selection([
        ('view', 'Viewed'),
        ('download', 'Downloaded'),
        ('stream', 'Streamed'),
        ('share', 'Shared'),
    ], string='Access Type', required=True, default='view')

    # Session duration in minutes (set on close/logout)
    duration_minutes = fields.Integer(
        string='Duration (min)',
        help='Time spent on resource in minutes')

    # Device / browser info from request
    ip_address = fields.Char(string='IP Address')
    user_agent = fields.Char(string='User Agent')
    device_type = fields.Selection([
        ('desktop', 'Desktop'),
        ('mobile', 'Mobile'),
        ('tablet', 'Tablet'),
        ('other', 'Other'),
    ], string='Device')

    # For downloads — which page/section
    notes = fields.Char(string='Notes')

    display_name = fields.Char(
        compute='_compute_display_name', store=True)

    # -------------------------------------------------------------------------
    # Compute
    # -------------------------------------------------------------------------

    @api.depends('resource_id', 'member_id', 'access_date')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s — %s — %s' % (
                rec.resource_id.title or '',
                rec.member_name or '',
                rec.access_date.strftime('%d/%m/%Y %H:%M') if rec.access_date else '')

    # -------------------------------------------------------------------------
    # Read-only — access logs are never edited
    # -------------------------------------------------------------------------

    def write(self, vals):
        # Allow only duration and notes to be updated after creation
        allowed = {'duration_minutes', 'notes'}
        if not set(vals.keys()).issubset(allowed):
            vals = {k: v for k, v in vals.items() if k in allowed}
        return super().write(vals)


class LibraryOPACSearchLog(models.Model):
    """
    Logs every search made in the OPAC portal.
    Helps librarians understand what students are looking for,
    identify gaps in the collection, and improve discoverability.
    """
    _name = 'library.opac.search.log'
    _description = 'OPAC Search Log'
    _order = 'search_date desc'
    _rec_name = 'query'

    query = fields.Char(string='Search Query', required=True, index=True)
    search_date = fields.Datetime(
        string='Searched On', default=fields.Datetime.now, required=True)

    # Who searched
    member_id = fields.Many2one(
        'library.member', string='Member', index=True)
    member_name = fields.Char(
        related='member_id.member_name', string='Member Name', store=True)
    is_anonymous = fields.Boolean(
        string='Anonymous Search', default=False)

    # Filters applied
    filter_type = fields.Char(
        string='Type Filter',
        help='Resource type filter applied during search')
    filter_category = fields.Char(string='Category Filter')
    filter_language = fields.Char(string='Language Filter')

    # Result stats
    results_count = fields.Integer(string='Results Found', default=0)
    clicked_resource_id = fields.Many2one(
        'library.digital.resource', string='Clicked Resource')
    clicked_book_id = fields.Many2one(
        'library.book', string='Clicked Book')

    ip_address = fields.Char(string='IP Address')