# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class TransportRoute(models.Model):
    _name = 'transport.route'
    _description = 'Transport Bus Routes'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Route Name', required=True, tracking=True)
    code = fields.Char(string='Route Code', required=True)

    # Route Details
    start_location = fields.Char(string='Start Location', required=True)
    end_location = fields.Char(string='End Location', required=True)
    distance = fields.Float(string='Total Distance (KM)')
    estimated_time = fields.Float(string='Estimated Time (Hours)')

    # Stops
    stop_ids = fields.One2many('transport.stop', 'route_id', string='Bus Stops')
    total_stops = fields.Integer(string='Total Stops', compute='_compute_stops')

    # Vehicles Assigned
    vehicle_ids = fields.Many2many('transport.vehicle', 'route_vehicle_rel',
                                   'route_id', 'vehicle_id',
                                   string='Vehicles on this Route', store=True)

    # Students
    allocation_ids = fields.One2many('transport.allocation', 'route_id',
                                     string='Student Allocations')
    total_students = fields.Integer(string='Total Students', compute='_compute_students', store=True)

    # Fee
    monthly_fee = fields.Monetary(string='Monthly Transport Fee', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Status
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Route Code must be unique!'),
    ]

    @api.depends('stop_ids')
    def _compute_stops(self):
        for record in self:
            record.total_stops = len(record.stop_ids)

    @api.depends('allocation_ids')
    def _compute_students(self):
        for record in self:
            record.total_students = len(record.allocation_ids.filtered(
                lambda a: a.state == 'active'))
