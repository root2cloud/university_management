from odoo import models, fields


class LibraryBook(models.Model):
    _name = 'library.book'
    _description = 'Library Book'

    title = fields.Char(string='Title', required=True)
    isbn = fields.Char(string='ISBN')
    author_id = fields.Many2one('library.author', string='Author')
    description = fields.Text(string='Description')
    published_date = fields.Date(string='Published Date')
    available_copies = fields.Integer(string='Available Copies', default=1)
    category_id = fields.Many2one('library.category', string='Book Category')

