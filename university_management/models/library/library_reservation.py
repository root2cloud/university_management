# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class LibraryReservation(models.Model):
    _name = 'library.reservation'
    _description = 'Book Reservation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'reservation_date desc'

    name = fields.Char(string='Reservation Number', required=True, readonly=True,
                       copy=False, default='/')

    # Member
    member_id = fields.Many2one('library.member', string='Member',
                                required=True, tracking=True, index=True)
    member_name = fields.Char(related='member_id.member_name', string='Member Name')

    # Book
    book_id = fields.Many2one('library.book', string='Book',
                              required=True, tracking=True, index=True)

    # Reservation Details
    reservation_date = fields.Date(string='Reservation Date', default=fields.Date.today(),
                                   required=True, tracking=True)
    expiry_date = fields.Date(string='Expiry Date', required=True)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('reserved', 'Reserved'),
        ('issued', 'Issued'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='reserved', tracking=True)

    # Notes
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Reservation Number must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('library.reservation') or '/'
        return super(LibraryReservation, self).create(vals)

    def action_confirm(self):
        """Confirm the reservation (move from draft to reserved)"""
        self.write({'state': 'reserved'})

    def action_issue(self):
        """Issue reserved book"""
        self.ensure_one()

        issue = self.env['library.issue'].create({
            'member_id': self.member_id.id,
            'book_id': self.book_id.id,
            'issue_date': fields.Date.today(),
        })

        self.write({'state': 'issued'})

        return {
            'type': 'ir.actions.act_window',
            'name': _('Book Issue'),
            'res_model': 'library.issue',
            'res_id': issue.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        """Reset reservation to draft state"""
        self.write({'state': 'draft'})

    @api.model
    def _cron_check_expired_reservations(self):
        """Check and expire old reservations"""
        today = fields.Date.today()
        expired = self.search([
            ('state', '=', 'reserved'),
            ('expiry_date', '<', today)
        ])
        expired.write({'state': 'expired'})