from odoo import models, fields

class LibraryAuthor(models.Model):
    _name = 'library.author'
    _description = 'Library Author'

    name = fields.Char(string='Name', required=True)
    biography = fields.Text(string='Biography')
    birth_date = fields.Date(string='Birth Date')