from odoo import models, fields


class LibraryBook(models.Model):
    _name = 'school.library.book'
    _description = 'Library Book'

    title = fields.Char(string="Title", required=True)
    author = fields.Char(string="Author")
    ISBN = fields.Char(string="ISBN")
    total_copies = fields.Integer(string="Total Copies")
    available_copies = fields.Integer(string="Available Copies")