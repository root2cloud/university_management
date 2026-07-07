from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class LibraryBookIssue(models.Model):
    _name = 'school.library.issue'
    _description = 'Library Book Issue'
    _order = 'issue_date desc'

    student_id = fields.Many2one('school.student', string='Student', required=True)
    book_id = fields.Many2one('school.library.book', string='Book', required=True)
    issue_date = fields.Date(string='Issue Date', default=fields.Date.today, required=True)
    return_date = fields.Date(string='Return Date')
    state = fields.Selection([
        ('issued', 'Issued'),
        ('returned', 'Returned'),
    ], string='Status', default='issued', required=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            book = self.env['school.library.book'].browse(vals.get('book_id'))
            if book.available_copies <= 0:
                raise ValidationError(f"No available copies for book: {book.title}")
            book.available_copies -= 1
        return super().create(vals_list)

    def return_book(self):
        for record in self:
            if record.state != 'returned':
                book = record.book_id
                book.available_copies += 1
                record.return_date = fields.Date.today()
                record.state = 'returned'

