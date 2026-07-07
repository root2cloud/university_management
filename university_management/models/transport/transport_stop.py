# -*- coding: utf-8 -*-

from odoo import models, fields, api


class TransportStop(models.Model):
    _name = 'transport.stop'
    _description = 'Transport Bus Stops'
    _order = 'route_id, sequence'

    name = fields.Char(string='Stop Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)

    # Route
    route_id = fields.Many2one('transport.route', string='Route',
                               required=True, index=True, ondelete='cascade')

    # Location
    location = fields.Char(string='Location/Landmark')
    latitude = fields.Float(string='Latitude', digits=(10, 6), store=True)
    longitude = fields.Float(string='Longitude', digits=(10, 6))

    # Timing
    arrival_time = fields.Char(string='Arrival Time (Morning)', help='e.g., 07:30 AM')
    departure_time = fields.Char(string='Departure Time (Evening)', help='e.g., 05:00 PM')

    # Distance from start
    distance_from_start = fields.Float(string='Distance from Start (KM)')

    # Students
    student_count = fields.Integer(string='Students at this Stop',
                                   compute='_compute_students', store=True)

    active = fields.Boolean(string='Active', default=True)

    date_localization = fields.Date(string='Localization Date', default=fields.Date.today)

    @api.depends('route_id')
    def _compute_students(self):
        for record in self:
            record.student_count = self.env['transport.allocation'].search_count([
                ('stop_id', '=', record.id),
                ('state', '=', 'active')
            ])
