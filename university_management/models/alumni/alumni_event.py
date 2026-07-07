# -*- coding: utf-8 -*-

from odoo import models, fields, api,_


class AlumniEvent(models.Model):
    _name = 'alumni.event'
    _description = 'Alumni Events/Meets'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _inherits = {'calendar.event': 'calendar_event_id'}  # Integration with calendar
    _order = 'start desc'

    # Calendar Event (inherited)
    calendar_event_id = fields.Many2one('calendar.event', string='Calendar Event',
                                        required=True, ondelete='cascade', auto_join=True)

    # Event Type
    event_type = fields.Selection([
        ('reunion', 'Alumni Reunion'),
        ('meet', 'Alumni Meet'),
        ('seminar', 'Seminar/Workshop'),
        ('networking', 'Networking Event'),
        ('fundraiser', 'Fundraising Event'),
        ('cultural', 'Cultural Event'),
    ], string='Event Type', required=True, tracking=True)

    # Target Batch
    target_batch_ids = fields.Many2many('university.batch', string='Target Batches')
    target_graduation_year = fields.Integer(string='Target Graduation Year')

    # Venue
    venue_details = fields.Text(string='Venue Details')

    # Registrations
    registration_open = fields.Boolean(string='Registration Open', default=True)
    registration_deadline = fields.Date(string='Registration Deadline')

    registered_alumni_ids = fields.Many2many('alumni.alumni', string='Registered Alumni')
    total_registrations = fields.Integer(string='Total Registrations',
                                         compute='_compute_registrations')

    # Fee
    registration_fee = fields.Monetary(string='Registration Fee', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    @api.depends('registered_alumni_ids')
    def _compute_registrations(self):
        for record in self:
            record.total_registrations = len(record.registered_alumni_ids)

    # ---- State transition actions ----
    def action_publish(self):
        """Move event from Draft to Published."""
        for record in self:
            if record.state != 'draft':
                continue
            record.state = 'published'

    def action_start(self):
        """Start the event (Published -> Ongoing)."""
        for record in self:
            if record.state != 'published':
                continue
            record.state = 'ongoing'

    def action_complete(self):
        """Mark the event as Completed (Ongoing -> Completed)."""
        for record in self:
            if record.state != 'ongoing':
                continue
            record.state = 'completed'

    def action_cancel(self):
        """Cancel the event (any state except Completed/Cancelled)."""
        for record in self:
            if record.state in ('completed', 'cancelled'):
                continue
            record.state = 'cancelled'

    def action_reset_to_draft(self):
        """Reset the event to draft state."""
        for record in self:
            record.write({'state': 'draft'})

    def action_view_registrations(self):
        """Open the alumni registered for this event."""
        self.ensure_one()
        return {
            'name': _('Registered Alumni'),
            'type': 'ir.actions.act_window',
            'res_model': 'alumni.alumni',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.registered_alumni_ids.ids)],
            'context': {
                'default_event_registration_ids': [(6, 0, [self.id])],
            },
        }
