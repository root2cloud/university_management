# -*- coding: utf-8 -*-

from odoo import models, fields, api


class EventSponsor(models.Model):
    _name = 'event.sponsor'
    _description = 'Event Sponsors'
    _order = 'sequence, name'

    sequence = fields.Integer(string='Sequence', default=10)
    name = fields.Char(string='Sponsor Name', required=True)

    # Event
    event_id = fields.Many2one('university.event', string='Event',
                               required=True, index=True, ondelete='cascade')

    # Sponsor Type
    sponsor_type = fields.Selection([
        ('title', 'Title Sponsor'),
        ('platinum', 'Platinum Sponsor'),
        ('gold', 'Gold Sponsor'),
        ('silver', 'Silver Sponsor'),
        ('bronze', 'Bronze Sponsor'),
        ('associate', 'Associate Partner'),
    ], string='Sponsor Type', required=True)

    # Company (using res.partner)
    company_id = fields.Many2one('res.partner', string='Company',
                                 domain=[('is_company', '=', True)])

    # Contribution
    contribution_amount = fields.Monetary(string='Contribution Amount',
                                          currency_field='currency_id')
    contribution_type = fields.Selection([
        ('cash', 'Cash'),
        ('kind', 'In-Kind'),
        ('both', 'Both'),
    ], string='Contribution Type')

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Contact Person
    contact_person = fields.Char(string='Contact Person')
    contact_email = fields.Char(string='Email')
    contact_phone = fields.Char(string='Phone')

    # Logo
    logo = fields.Binary(string='Sponsor Logo', attachment=True)

    # Website
    website = fields.Char(string='Website')

    # Description
    description = fields.Text(string='Description')
