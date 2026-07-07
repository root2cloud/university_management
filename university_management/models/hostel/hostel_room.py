# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class HostelRoom(models.Model):
    _name = 'hostel.room'
    _description = 'Hostel Room Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'hostel_id, room_number'

    name = fields.Char(string='Room Name', compute='_compute_name', store=True)

    # Hostel
    hostel_id = fields.Many2one('hostel.hostel', string='Hostel',
                                required=True, tracking=True, index=True)

    # Room Details
    room_number = fields.Char(string='Room Number', required=True, tracking=True)
    floor = fields.Char(string='Floor')
    block = fields.Char(string='Block/Wing')

    # Room Type
    room_type = fields.Selection([
        ('single', 'Single Occupancy'),
        ('double', 'Double Sharing'),
        ('triple', 'Triple Sharing'),
        ('quad', 'Four Sharing'),
        ('dormitory', 'Dormitory'),
    ], string='Room Type', required=True, default='double', tracking=True)

    # Capacity
    capacity = fields.Integer(string='Bed Capacity', required=True, default=2)
    occupied_beds = fields.Integer(string='Occupied Beds', compute='_compute_occupancy', store=True)
    available_beds = fields.Integer(string='Available Beds', compute='_compute_occupancy', store=True)

    # Allocations
    allocation_ids = fields.One2many('hostel.allocation', 'room_id', string='Allocations')

    # Facilities
    has_ac = fields.Boolean(string='AC Available')
    has_attached_bathroom = fields.Boolean(string='Attached Bathroom')
    has_balcony = fields.Boolean(string='Balcony')
    has_study_table = fields.Boolean(string='Study Table')
    has_wardrobe = fields.Boolean(string='Wardrobe')

    # Furniture
    furniture_details = fields.Text(string='Furniture Details')

    # Rent
    monthly_rent = fields.Monetary(string='Monthly Rent', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Status
    state = fields.Selection([
        ('available', 'Available'),
        ('occupied', 'Occupied'),
        ('full', 'Full'),
        ('maintenance', 'Under Maintenance'),
        ('reserved', 'Reserved'),
    ], string='Status', default='available', tracking=True, compute='_compute_state', store=True)

    # Remarks
    remarks = fields.Text(string='Remarks')

    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('unique_room', 'unique(hostel_id, room_number)',
         'Room number must be unique per hostel!'),
    ]

    @api.depends('hostel_id', 'room_number')
    def _compute_name(self):
        for record in self:
            record.name = f"{record.hostel_id.name} - {record.room_number}"

    @api.depends('allocation_ids', 'allocation_ids.state', 'capacity')
    def _compute_occupancy(self):
        for record in self:
            active_allocations = record.allocation_ids.filtered(lambda a: a.state == 'allocated')
            record.occupied_beds = len(active_allocations)
            record.available_beds = record.capacity - record.occupied_beds

    @api.depends('available_beds')
    def _compute_state(self):
        for record in self:
            if record.available_beds == 0:
                record.state = 'full'
            elif record.occupied_beds > 0:
                record.state = 'occupied'
            else:
                record.state = 'available'

    # Workflow Actions
    def action_make_available(self):
        """Make room available"""
        self.write({'state': 'available'})

    def action_maintenance(self):
        """Put room under maintenance"""
        self.write({'state': 'maintenance'})

    def action_reserve(self):
        """Reserve the room"""
        self.write({'state': 'reserved'})

    def action_reset_to_draft(self):
        """Reset room to draft state"""
        self.write({'state': 'draft'})