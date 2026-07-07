# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class LibraryBook(models.Model):
    _name = 'library.book'
    _description = 'Library Book Master'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _inherits = {'product.product': 'product_id'}  # Integration with stock module
    _order = 'name'

    # Product (for inventory management)
    product_id = fields.Many2one('product.product', string='Product',
                                 required=True, ondelete='cascade', auto_join=True)

    # Book Details
    isbn = fields.Char(string='ISBN', tracking=True, index=True)
    isbn13 = fields.Char(string='ISBN-13', tracking=True)

    title = fields.Char(string='Book Title', required=True, tracking=True)
    subtitle = fields.Char(string='Subtitle')

    # Author
    author_ids = fields.Many2many('library.author', string='Authors', required=True)
    primary_author = fields.Char(string='Primary Author', compute='_compute_primary_author',
                                 store=True, index=True)

    # Publisher
    publisher_id = fields.Many2one('res.partner', string='Publisher',
                                   domain=[('is_company', '=', True)])
    publication_year = fields.Integer(string='Publication Year')
    edition = fields.Char(string='Edition')

    # Category
    category_id = fields.Many2one('library.category', string='Category', required=True)
    subject = fields.Char(string='Subject')

    # Language
    language = fields.Char(string='Language', default='English')

    # Physical Details
    pages = fields.Integer(string='Number of Pages')
    binding_type = fields.Selection([
        ('hardcover', 'Hardcover'),
        ('paperback', 'Paperback'),
        ('spiral', 'Spiral Bound'),
        ('ebook', 'E-Book'),
    ], string='Binding Type', default='paperback')

    # Stock/Inventory (using product.product)
    total_copies = fields.Integer(string='Total Copies', default=1)
    available_copies = fields.Integer(string='Available Copies',
                                      compute='_compute_availability', store=True)
    issued_copies = fields.Integer(string='Issued Copies',
                                   compute='_compute_availability', store=True)
    reserved_copies = fields.Integer(string='Reserved Copies',
                                     compute='_compute_availability', store=True)

    # Location
    rack_id = fields.Many2one('library.rack', string='Rack/Shelf Location')
    code_id = fields.Many2one('library.rack', string='Rack Number')

    # Purchase Details
    purchase_date = fields.Date(string='Purchase Date')
    purchase_price = fields.Monetary(string='Purchase Price', currency_field='currency_id')
    vendor_id = fields.Many2one('res.partner', string='Vendor',
                                domain=[('supplier_rank', '>', 0)])

    currency_id = fields.Many2one('res.currency',
                                  default=lambda self: self.env.company.currency_id)

    # Issue Details
    issue_ids = fields.One2many('library.issue', 'book_id', string='Issue History')
    reservation_ids = fields.One2many('library.reservation', 'book_id', string='Reservations')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('available', 'Available'),
        ('issued', 'Issued'),
        ('reserved', 'Reserved'),
        ('maintenance', 'Under Maintenance'),
        ('lost', 'Lost'),
        ('damaged', 'Damaged'),
    ], string='Status', default='available', tracking=True,
        compute='_compute_state', store=True)

    active = fields.Boolean(string='Active', default=True)

    # Description
    description = fields.Html(string='Description')

    # Cover Image
    cover_image = fields.Binary(string='Cover Image', attachment=True)

    # Computed percentages for progress bars (0-100 range)
    available_pct = fields.Float(string='Available %',
                                 compute='_compute_copy_percents', store=True)
    issued_pct = fields.Float(string='Issued %',
                              compute='_compute_copy_percents', store=True)
    reserved_pct = fields.Float(string='Reserved %',
                                compute='_compute_copy_percents', store=True)

    # -------------------------------------------------------------------------
    # OPAC & Digital E-Library fields
    # -------------------------------------------------------------------------
    opac_visible = fields.Boolean(
        string='Show in OPAC', default=True,
        help='When enabled, this book appears in the Online Public Access Catalog')
    opac_description = fields.Text(
        string='OPAC Abstract',
        help='Short description displayed in OPAC search results')
    tags = fields.Char(
        string='Tags / Keywords',
        help='Comma-separated keywords to improve OPAC discoverability')

    # Subjects linking for OPAC search
    subject_ids = fields.Many2many(
        'university.subject',
        relation='library_book_subject_rel',
        column1='book_id',
        column2='subject_id',
        string='Relevant Subjects',
        help='Tag subjects so students can find this book from subject-based searches')

    # Link to digital counterparts
    digital_resource_ids = fields.One2many(
        'library.digital.resource', 'physical_book_id',
        string='Digital Versions')
    has_digital = fields.Boolean(
        string='Has Digital Version',
        compute='_compute_has_digital', store=True)
    digital_count = fields.Integer(
        string='Digital Versions',
        compute='_compute_has_digital', store=True)

    # -------------------------------------------------------------------------
    # SQL Constraints
    # -------------------------------------------------------------------------

    _sql_constraints = [
        ('isbn_unique', 'unique(isbn)', 'ISBN must be unique!'),
    ]

    # -------------------------------------------------------------------------
    # Compute Methods
    # -------------------------------------------------------------------------

    @api.depends('author_ids')
    def _compute_primary_author(self):
        for record in self:
            record.primary_author = record.author_ids[0].name if record.author_ids else ''

    @api.depends('issue_ids', 'issue_ids.state', 'reservation_ids', 'reservation_ids.state',
                 'total_copies')
    def _compute_availability(self):
        for record in self:
            active_issues = record.issue_ids.filtered(lambda i: i.state in ['issued', 'overdue'])
            active_reservations = record.reservation_ids.filtered(
                lambda r: r.state == 'reserved')
            record.issued_copies = len(active_issues)
            record.reserved_copies = len(active_reservations)
            record.available_copies = (record.total_copies - record.issued_copies
                                       - record.reserved_copies)

    @api.depends('available_copies', 'issued_copies')
    def _compute_state(self):
        for record in self:
            if record.issued_copies >= record.total_copies:
                record.state = 'issued'
            elif record.available_copies > 0:
                record.state = 'available'
            elif record.reserved_copies > 0:
                record.state = 'reserved'
            else:
                record.state = 'available'

    @api.depends('total_copies', 'available_copies', 'issued_copies', 'reserved_copies')
    def _compute_copy_percents(self):
        for rec in self:
            if rec.total_copies:
                rec.available_pct = (rec.available_copies / rec.total_copies) * 100
                rec.issued_pct = (rec.issued_copies / rec.total_copies) * 100
                rec.reserved_pct = (rec.reserved_copies / rec.total_copies) * 100
            else:
                rec.available_pct = 0.0
                rec.issued_pct = 0.0
                rec.reserved_pct = 0.0

    @api.depends('digital_resource_ids')
    def _compute_has_digital(self):
        for rec in self:
            rec.digital_count = len(rec.digital_resource_ids)
            rec.has_digital = rec.digital_count > 0

    # -------------------------------------------------------------------------
    # Constraints
    # -------------------------------------------------------------------------

    @api.constrains('isbn')
    def _check_isbn(self):
        for record in self:
            if record.isbn:
                isbn = record.isbn.replace('-', '').replace(' ', '')
                if not (len(isbn) == 10 or len(isbn) == 13):
                    raise ValidationError(_('ISBN must be 10 or 13 digits!'))

    # -------------------------------------------------------------------------
    # ORM Overrides
    # -------------------------------------------------------------------------

    @api.model
    def create(self, vals):
        if vals.get('title') and not vals.get('product_id'):
            product_vals = {
                'name': vals.get('title'),
                'type': 'consu',
                'categ_id': self.env.ref('product.product_category_1').id,
                'list_price': vals.get('purchase_price', 0.0) or 0.0,
                'standard_price': vals.get('purchase_price', 0.0) or 0.0,
            }
            product = self.env['product.product'].create(product_vals)
            vals['product_id'] = product.id
        return super(LibraryBook, self).create(vals)

    def write(self, vals):
        if 'title' in vals:
            for book in self:
                if book.product_id:
                    book.product_id.write({'name': vals['title']})
        return super(LibraryBook, self).write(vals)

    # -------------------------------------------------------------------------
    # Workflow Actions
    # -------------------------------------------------------------------------

    def action_make_available(self):
        self.write({'state': 'available'})

    def action_maintenance(self):
        self.write({'state': 'maintenance'})

    def action_mark_lost(self):
        self.write({'state': 'lost'})

    def action_mark_damaged(self):
        self.write({'state': 'damaged'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def action_view_digital_versions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Digital Versions — %s') % self.title,
            'res_model': 'library.digital.resource',
            'view_mode': 'list,kanban,form',
            'domain': [('physical_book_id', '=', self.id)],
            'context': {'default_physical_book_id': self.id},
        }


class LibraryAuthor(models.Model):
    _name = 'library.author'
    _description = 'Book Author'
    _order = 'name'

    name = fields.Char(string='Author Name', required=True)
    biography = fields.Html(string='Biography')
    photo = fields.Binary(string='Photo', attachment=True)

    book_ids = fields.Many2many('library.book', string='Books')
    total_books = fields.Integer(string='Total Books', compute='_compute_total')

    active = fields.Boolean(string='Active', default=True)
    color = fields.Integer(string='Color Index', default=0)

    @api.depends('book_ids')
    def _compute_total(self):
        for record in self:
            record.total_books = len(record.book_ids)


class LibraryRack(models.Model):
    _name = 'library.rack'
    _description = 'Library Rack/Shelf'
    _order = 'name'

    name = fields.Char(string='Rack Name', required=True)
    code = fields.Char(string='Rack Number', required=True)
    location = fields.Char(string='Location')
    floor = fields.Char(string='Floor')

    book_ids = fields.One2many('library.book', 'rack_id', string='Books')
    total_books = fields.Integer(string='Total Books', compute='_compute_total')
    capacity = fields.Integer(string='Capacity')
    active = fields.Boolean(string='Active', default=True)

    @api.depends('book_ids')
    def _compute_total(self):
        for record in self:
            record.total_books = len(record.book_ids)