# -*- coding: utf-8 -*-

from odoo import models, fields, api


class LibraryCategory(models.Model):
    _name = 'library.category'
    _description = 'Library Book Categories'
    _order = 'name'
    _parent_store = True

    name = fields.Char(string='Category Name', required=True)
    code = fields.Char(string='Category Code')

    parent_id = fields.Many2one('library.category', string='Parent Category', index=True)
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('library.category', 'parent_id', string='Subcategories')

    book_ids = fields.One2many('library.book', 'category_id', string='Books')
    total_books = fields.Integer(string='Total Books', compute='_compute_total', store=True)

    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)

    @api.depends('book_ids')
    def _compute_total(self):
        for record in self:
            record.total_books = len(record.book_ids)
