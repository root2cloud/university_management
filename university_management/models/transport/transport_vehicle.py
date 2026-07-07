# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TransportVehicle(models.Model):
    _name = 'transport.vehicle'
    _description = 'Transport Vehicle/Bus Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Vehicle Name', required=True, tracking=True)
    vehicle_number = fields.Char(string='Vehicle Number', required=True, tracking=True)

    # Vehicle Type
    vehicle_type = fields.Selection([
        ('bus', 'Bus'),
        ('mini_bus', 'Mini Bus'),
        ('van', 'Van'),
    ], string='Vehicle Type', required=True, default='bus')

    # Capacity
    seating_capacity = fields.Integer(string='Seating Capacity', required=True)
    occupied_seats = fields.Integer(string='Occupied Seats', compute='_compute_occupancy')
    available_seats = fields.Integer(string='Available Seats', compute='_compute_occupancy', store=True)

    # Driver
    driver_id = fields.Many2one('transport.driver', string='Driver', tracking=True)

    # Routes
    route_ids = fields.Many2many('transport.route', 'route_vehicle_rel',
                                 'vehicle_id', 'route_id',
                                 string='Routes Assigned')
    allocation_ids = fields.One2many('transport.allocation', 'vehicle_id', string='Student Allocations')

    # Vehicle Details
    make = fields.Char(string='Make/Brand')
    model = fields.Char(string='Model')
    year = fields.Integer(string='Year of Manufacture')
    color = fields.Char(string='Color')

    # Registration
    registration_date = fields.Date(string='Registration Date')
    registration_expiry = fields.Date(string='Registration Expiry')

    # Insurance
    insurance_company = fields.Char(string='Insurance Company')
    insurance_number = fields.Char(string='Insurance Policy Number')
    insurance_expiry = fields.Date(string='Insurance Expiry Date', tracking=True, store=True)

    # Fitness
    fitness_certificate = fields.Date(string='Fitness Certificate Expiry', tracking=True, store=True)

    # Pollution
    pollution_certificate = fields.Date(string='Pollution Certificate Expiry', tracking=True, store=True)

    # Maintenance
    last_service_date = fields.Date(string='Last Service Date')
    next_service_date = fields.Date(string='Next Service Date')
    service_km = fields.Integer(string='Service at KM')
    current_km = fields.Integer(string='Current KM Reading')

    # Fuel
    fuel_type = fields.Selection([
        ('petrol', 'Petrol'),
        ('diesel', 'Diesel'),
        ('cng', 'CNG'),
        ('electric', 'Electric'),
    ], string='Fuel Type')

    # GPS Tracking
    has_gps = fields.Boolean(string='GPS Tracking Available')
    gps_device_id = fields.Char(string='GPS Device ID')

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('maintenance', 'Under Maintenance'),
        ('breakdown', 'Breakdown'),
        ('inactive', 'Inactive'),
    ], string='Status', default='active', tracking=True)

    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('vehicle_number_unique', 'unique(vehicle_number)', 'Vehicle Number must be unique!'),
    ]

    @api.depends('allocation_ids', 'allocation_ids.state', 'seating_capacity')
    def _compute_occupancy(self):
        for record in self:
            active_allocations = record.allocation_ids.filtered(lambda a: a.state == 'active')
            record.occupied_seats = len(active_allocations)
            record.available_seats = record.seating_capacity - record.occupied_seats

    @api.constrains('insurance_expiry', 'fitness_certificate', 'pollution_certificate')
    def _check_documents_validity(self):
        """Check if documents are about to expire"""
        from datetime import timedelta
        today = fields.Date.today()
        warning_days = 30

        for record in self:
            if record.insurance_expiry and (record.insurance_expiry - today).days < warning_days:
                record.message_post(
                    body=f"Warning: Insurance expires on {record.insurance_expiry}",
                    subject="Insurance Expiry Alert"
                )

    # Workflow Actions
    def action_activate(self):
        """Activate the vehicle (move from draft to active)"""
        self.write({'state': 'active'})

    def action_maintenance(self):
        """Put vehicle under maintenance"""
        self.write({'state': 'maintenance'})

    def action_breakdown(self):
        """Mark vehicle as breakdown"""
        self.write({'state': 'breakdown'})

    def action_inactive(self):
        """Deactivate the vehicle"""
        self.write({'state': 'inactive'})

    def action_reset_to_draft(self):
        """Reset vehicle to draft state"""
        self.write({'state': 'draft'})
