from odoo import models, fields, api

class LibraryMember(models.Model):
    _name = 'library.member'
    _description = 'Library Member'

    name = fields.Char(string='Name', required=True)
    email = fields.Char(string='Email')
    phone = fields.Char(string='Phone')
    membership_start_date = fields.Date(string='Membership Start Date', default=fields.Date.today)
    membership_end_date = fields.Date(string='Membership End Date')
    status = fields.Selection([
        ('active', 'Active'),
        ('expired', 'Expired')
    ], string='Status', compute='_compute_status', store=True)

    @api.depends('membership_end_date')
    def _compute_status(self):
        today = fields.Date.today()
        for member in self:
            if member.membership_end_date and member.membership_end_date < today:
                member.status = 'expired'
            else:
                member.status = 'active'

    def action_view_borrowings(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Current Borrowings',
            'res_model': 'library.borrowing',
            'view_mode': 'list,form',
            'domain': [('borrower_id', '=', self.id), ('status', '=', 'borrowed')],
        }

    def action_view_reservations(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reservations',
            'res_model': 'library.borrowing',
            'view_mode': 'list,form',
            'domain': [('borrower_id', '=', self.id), ('reservation_date', '!=', False)],
        }
