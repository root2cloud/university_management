# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class LibraryDigitalResource(models.Model):
    """
    A single digital resource — an e-book, journal article, video lecture,
    thesis, dataset, etc. Can be a direct file upload or an external URL.
    Can optionally be linked to a physical library.book record.
    """
    _name = 'library.digital.resource'
    _description = 'Digital Library Resource'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'title'
    _rec_name = 'title'

    # -------------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------------

    title = fields.Char(string='Title', required=True, tracking=True, index=True)
    subtitle = fields.Char(string='Subtitle')
    code = fields.Char(string='Resource Code', copy=False, readonly=True, index=True)
    cover_image = fields.Binary(string='Cover / Thumbnail', attachment=True)

    resource_type = fields.Selection([
        ('ebook', 'E-Book'),
        ('journal', 'Journal / Article'),
        ('video', 'Video Lecture'),
        ('thesis', 'Thesis / Dissertation'),
        ('report', 'Research Report'),
        ('dataset', 'Dataset'),
        ('course', 'Online Course'),
        ('magazine', 'Magazine / Newsletter'),
        ('other', 'Other'),
    ], string='Resource Type', required=True, default='ebook', tracking=True, index=True)

    # -------------------------------------------------------------------------
    # Authorship / Publication
    # -------------------------------------------------------------------------

    author_ids = fields.Many2many(
        'library.author', string='Authors',
        relation='library_digital_resource_author_rel',
        column1='resource_id', column2='author_id')
    primary_author = fields.Char(
        string='Primary Author', compute='_compute_primary_author', store=True)
    publisher = fields.Char(string='Publisher / Source')
    publication_year = fields.Integer(string='Publication Year')
    edition = fields.Char(string='Edition / Volume')
    doi = fields.Char(string='DOI', help='Digital Object Identifier')
    issn = fields.Char(string='ISSN', help='For journals')
    isbn = fields.Char(string='ISBN', help='For e-books')
    language = fields.Char(string='Language', default='English')

    # -------------------------------------------------------------------------
    # Classification
    # -------------------------------------------------------------------------

    category_id = fields.Many2one(
        'library.category', string='Category', index=True)
    collection_id = fields.Many2one(
        'library.digital.collection', string='Collection / Database',
        tracking=True, index=True)
    subject_ids = fields.Many2many(
        'university.subject', string='Relevant Subjects',
        relation='library_digital_resource_subject_rel',
        column1='resource_id', column2='subject_id')
    tags = fields.Char(
        string='Tags / Keywords',
        help='Comma-separated keywords for OPAC search')

    # Link to physical book if this is the digital counterpart
    physical_book_id = fields.Many2one(
        'library.book', string='Linked Physical Book',
        help='Link to the physical copy of this resource if it exists')

    # -------------------------------------------------------------------------
    # Content / Access
    # -------------------------------------------------------------------------

    access_type = fields.Selection([
        ('open', 'Open Access — Public'),
        ('member', 'Members Only'),
        ('restricted', 'Restricted — Specific Groups'),
        ('subscribed', 'Subscription Required'),
    ], string='Access Level', required=True, default='member', tracking=True)

    content_type = fields.Selection([
        ('file', 'Uploaded File'),
        ('url', 'External URL / Link'),
        ('embed', 'Embedded (YouTube / NPTEL)'),
    ], string='Content Type', required=True, default='url')

    # External URL
    resource_url = fields.Char(
        string='Resource URL',
        help='Direct link to the resource or its landing page')
    embed_code = fields.Text(
        string='Embed Code',
        help='HTML embed code for video/iframe content')

    # Uploaded file
    resource_file = fields.Binary(
        string='Upload File', attachment=True,
        help='Upload the digital file (PDF, EPUB, etc.)')
    resource_filename = fields.Char(string='File Name')
    file_size_mb = fields.Float(
        string='File Size (MB)', compute='_compute_file_size', store=True)

    # Format / mime
    file_format = fields.Selection([
        ('pdf', 'PDF'),
        ('epub', 'EPUB'),
        ('mobi', 'MOBI'),
        ('mp4', 'MP4 Video'),
        ('html', 'HTML / Web'),
        ('docx', 'Word Document'),
        ('pptx', 'PowerPoint'),
        ('other', 'Other'),
    ], string='File Format')

    # -------------------------------------------------------------------------
    # Access restrictions
    # -------------------------------------------------------------------------

    allowed_member_types = fields.Many2many(
        'ir.model.fields.selection', string='Allowed Member Types',
        help='Leave empty to allow all member types')
    max_concurrent_access = fields.Integer(
        string='Max Concurrent Users', default=0,
        help='0 = unlimited')
    download_allowed = fields.Boolean(
        string='Allow Download', default=False)
    max_downloads_per_member = fields.Integer(
        string='Max Downloads per Member', default=3)

    # Availability window
    available_from = fields.Date(string='Available From')
    available_until = fields.Date(string='Available Until')
    is_available = fields.Boolean(
        string='Currently Available',
        compute='_compute_is_available', store=True)

    # -------------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------------

    access_ids = fields.One2many(
        'library.digital.access', 'resource_id',
        string='Access Logs')
    total_access_count = fields.Integer(
        string='Total Accesses',
        compute='_compute_access_stats', store=True)
    unique_member_count = fields.Integer(
        string='Unique Members',
        compute='_compute_access_stats', store=True)
    total_download_count = fields.Integer(
        string='Total Downloads',
        compute='_compute_access_stats', store=True)

    # -------------------------------------------------------------------------
    # Admin
    # -------------------------------------------------------------------------

    added_by = fields.Many2one(
        'res.users', string='Added By',
        default=lambda self: self.env.user, readonly=True)
    description = fields.Html(string='Abstract / Description')
    notes = fields.Text(string='Internal Notes')
    active = fields.Boolean(default=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ], string='Status', default='draft', tracking=True)

    # -------------------------------------------------------------------------
    # Compute
    # -------------------------------------------------------------------------

    @api.depends('author_ids')
    def _compute_primary_author(self):
        for rec in self:
            rec.primary_author = rec.author_ids[0].name if rec.author_ids else ''

    @api.depends('resource_file')
    def _compute_file_size(self):
        for rec in self:
            if rec.resource_file:
                import base64
                try:
                    decoded = base64.b64decode(rec.resource_file)
                    rec.file_size_mb = len(decoded) / (1024 * 1024)
                except Exception:
                    rec.file_size_mb = 0.0
            else:
                rec.file_size_mb = 0.0

    @api.depends('available_from', 'available_until', 'state')
    def _compute_is_available(self):
        today = fields.Date.today()
        for rec in self:
            if rec.state != 'published':
                rec.is_available = False
                continue
            from_ok = (not rec.available_from) or rec.available_from <= today
            until_ok = (not rec.available_until) or rec.available_until >= today
            rec.is_available = from_ok and until_ok

    @api.depends('access_ids', 'access_ids.access_type')
    def _compute_access_stats(self):
        for rec in self:
            logs = rec.access_ids
            rec.total_access_count = len(logs)
            rec.unique_member_count = len(logs.mapped('member_id'))
            rec.total_download_count = len(
                logs.filtered(lambda a: a.access_type == 'download'))

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    @api.constrains('available_from', 'available_until')
    def _check_dates(self):
        for rec in self:
            if rec.available_from and rec.available_until:
                if rec.available_until < rec.available_from:
                    raise ValidationError(
                        _('Available Until must be after Available From.'))

    @api.constrains('content_type', 'resource_url', 'resource_file')
    def _check_content(self):
        for rec in self:
            if rec.content_type == 'url' and not rec.resource_url:
                raise ValidationError(
                    _('Please provide a Resource URL for URL-type resources.'))
            if rec.content_type == 'embed' and not rec.embed_code:
                raise ValidationError(
                    _('Please provide Embed Code for embedded resources.'))
            if rec.content_type == 'file' and not rec.resource_file:
                raise ValidationError(
                    _('Please upload a file for file-type resources.'))

    # -------------------------------------------------------------------------
    # Sequence
    # -------------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = (
                    self.env['ir.sequence'].next_by_code('library.digital.resource')
                    or 'NEW')
        return super().create(vals_list)

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def action_publish(self):
        self.write({'state': 'published'})

    def action_archive_resource(self):
        self.write({'state': 'archived'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_view_access_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Access Logs — %s') % self.title,
            'res_model': 'library.digital.access',
            'view_mode': 'list,form',
            'domain': [('resource_id', '=', self.id)],
            'context': {'default_resource_id': self.id},
        }

    def action_log_access(self, member_id, access_type='view'):
        """Called programmatically to record an access event."""
        self.ensure_one()
        self.env['library.digital.access'].create({
            'resource_id': self.id,
            'member_id': member_id,
            'access_type': access_type,
            'access_date': fields.Datetime.now(),
        })