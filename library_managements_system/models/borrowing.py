from odoo import models, fields, api, exceptions
from datetime import timedelta


class LibraryBorrowing(models.Model):
    _name = 'library.borrowing'
    _description = 'Library Borrowing'

    borrower_id = fields.Many2one('library.member', string='Borrower', required=True)
    book_id = fields.Many2one('library.book', string='Book', required=True)
    borrow_date = fields.Date(string='Borrow Date', default=fields.Date.today)
    return_date = fields.Date(string='Return Date')
    status = fields.Selection([
        ('borrowed', 'Borrowed'),
        ('returned', 'Returned'),
        ('overdue', 'Overdue'),
        ('reserved', 'Reserved')
    ], string='Status', default='borrowed')
    reservation_date = fields.Date(string='Reservation Date')
    expiry_date = fields.Date(string='Expiry Date')
    completion_sequence = fields.Char(string='Completion Sequence', readonly=True, copy=False)

    @api.constrains('borrower_id', 'book_id', 'status', 'reservation_date', 'expiry_date')
    def _check_borrowing_limits(self):
        for record in self:
            # Check membership status
            if not record.borrower_id or record.borrower_id.status != 'active':
                raise exceptions.UserError("Member's membership is not active or invalid!")

            # Check borrowing limit (max 3 books)
            if record.status == 'borrowed':
                active_borrowings = self.search_count([
                    ('borrower_id', '=', record.borrower_id.id),
                    ('status', '=', 'borrowed'),
                    ('id', '!=', record.id)
                ])
                if active_borrowings >= 3:
                    raise exceptions.UserError("Cannot borrow more than 3 books at a time!")

            # Check if book is reserved by someone else
            if record.status in ('borrowed', 'reserved'):
                active_reservations = self.search([
                    ('book_id', '=', record.book_id.id),
                    ('status', '=', 'reserved'),
                    ('reservation_date', '!=', False),
                    ('expiry_date', '>=', fields.Date.today()),
                    ('borrower_id', '!=', record.borrower_id.id),
                    ('id', '!=', record.id)
                ])
                if active_reservations:
                    reserved_by = active_reservations[0].borrower_id.name
                    raise exceptions.UserError(
                        f"This book is reserved by {reserved_by} until {active_reservations[0].expiry_date}!"
                    )

            # Check available copies for borrowing
            if record.status == 'borrowed' and (not record.book_id or record.book_id.available_copies <= 0):
                raise exceptions.UserError("No available copies of this book or invalid book!")

            # Check reservation_date for reserved status
            if record.status == 'reserved' and not record.reservation_date:
                raise exceptions.UserError("Reservation Date is required for Reserved status!")

    def _check_return_after_borrow(self):
        for record in self:
            if record.return_date and record.return_date < record.borrow_date:
                raise ValidationError("Return Date cannot be earlier than Borrow Date.")

    @api.model
    def create(self, vals):
        if 'book_id' in vals:
            book = self.env['library.book'].browse(vals['book_id'])
            if not book.exists():
                raise exceptions.UserError("Invalid book ID!")
        if 'borrower_id' in vals:
            member = self.env['library.member'].browse(vals['borrower_id'])
            if not member.exists():
                raise exceptions.UserError("Invalid member ID!")
        if vals.get('status') == 'reserved':
            if not vals.get('reservation_date'):
                raise exceptions.UserError("Reservation Date is required for Reserved status!")
            vals['expiry_date'] = fields.Date.from_string(vals['reservation_date']) + timedelta(days=3)
        record = super(LibraryBorrowing, self).create(vals)
        if vals.get('status') == 'borrowed':
            record.book_id.available_copies -= 1
        return record

    def write(self, vals):
        if vals.get('status') == 'returned' and not self.completion_sequence:
            vals['completion_sequence'] = self.env['ir.sequence'].next_by_code('library.service.completion')
        if vals.get('status') == 'reserved':
            if 'reservation_date' in vals and vals['reservation_date']:
                vals['expiry_date'] = fields.Date.from_string(vals['reservation_date']) + timedelta(days=3)
            elif vals.get('status') == 'reserved' and not self.reservation_date and not vals.get('reservation_date'):
                raise exceptions.UserError("Reservation Date is required for Reserved status!")
        res = super(LibraryBorrowing, self).write(vals)
        if vals.get('status') == 'borrowed':
            self.book_id.available_copies -= 1
        elif vals.get('status') == 'returned':
            self.book_id.available_copies += 1
        return res

    @api.model
    def check_overdue_books(self):
        today = fields.Date.today()
        overdue_books = self.search([
            ('status', '=', 'borrowed'),
            ('borrow_date', '<', today - timedelta(days=14))
        ])
        for book in overdue_books:
            book.status = 'overdue'