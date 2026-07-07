# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class UniversityEvent(models.Model):
    _name = 'university.event'
    _description = 'University Events (Fest, Seminar, Workshop)'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'website.published.mixin']
    _inherits = {'calendar.event': 'calendar_event_id'}  # Integration with calendar
    _order = 'start desc'

    # Calendar Event (inherited)
    calendar_event_id = fields.Many2one('calendar.event', string='Calendar Event', ondelete='cascade', auto_join=True, required=True)

    # Event Code
    event_code = fields.Char(string='Event Code', required=True, readonly=True,
                             copy=False, default='/')

    # Event Type
    event_type = fields.Selection([
        ('fest', 'Cultural Fest'),
        ('tech_fest', 'Technical Fest'),
        ('seminar', 'Seminar'),
        ('workshop', 'Workshop'),
        ('conference', 'Conference'),
        ('webinar', 'Webinar'),
        ('sports', 'Sports Event'),
        ('competition', 'Competition'),
        ('guest_lecture', 'Guest Lecture'),
        ('hackathon', 'Hackathon'),
        ('other', 'Other'),
    ], string='Event Type', required=True, tracking=True)

    # Event Category
    category = fields.Selection([
        ('cultural', 'Cultural'),
        ('technical', 'Technical'),
        ('sports', 'Sports'),
        ('academic', 'Academic'),
        ('social', 'Social'),
    ], string='Category')

    # Organizer
    organized_by = fields.Selection([
        ('department', 'Department'),
        ('club', 'Student Club'),
        ('university', 'University'),
        ('external', 'External'),
    ], string='Organized By', required=True)

    registration_number = fields.Char(string='Registration Number', readonly=True,
                                      copy=False, tracking=True)
    department_id = fields.Many2one('university.department', string='Department')
    program_id = fields.Many2one('university.program', string='Program', tracking=True, index=True)
    employee_id = fields.Many2one('hr.employee', string='Related Employee', ondelete='cascade', auto_join=True)
    personal_email = fields.Char(string='Personal Email')
    personal_mobile = fields.Char(string='Personal Mobile')
    student_id = fields.Many2one('student.student', string='Student')
    club_name = fields.Char(string='Club Name')

    # Coordinator
    coordinator_ids = fields.Many2many('faculty.faculty', string='Faculty Coordinators')
    student_coordinator_ids = fields.Many2many('student.student', string='Student Coordinators')

    # Venue Details
    venue_type = fields.Selection([
        ('offline', 'Offline'),
        ('online', 'Online'),
        ('hybrid', 'Hybrid'),
    ], string='Venue Type', default='offline')

    venue_address = fields.Text(string='Venue Address')
    online_meeting_url = fields.Char(string='Online Meeting URL')

    # Target Audience
    target_audience = fields.Selection([
        ('students', 'Students Only'),
        ('faculty', 'Faculty Only'),
        ('all', 'All (Students & Faculty)'),
        ('external', 'Open to External Participants'),
    ], string='Target Audience', default='students')

    target_program_ids = fields.Many2many('university.program', string='Target Programs')
    target_year = fields.Selection([
        ('1', 'First Year'), ('2', 'Second Year'),
        ('3', 'Third Year'), ('4', 'Fourth Year'), ('all', 'All Years')
    ], string='Target Year')

    # Registration
    requires_registration = fields.Boolean(string='Requires Registration', default=True)
    registration_open = fields.Boolean(string='Registration Open', default=False)
    registration_start = fields.Datetime(string='Registration Start')
    registration_end = fields.Datetime(string='Registration End')
    registration_date = fields.Datetime(string='Registration Date', default=fields.Datetime.now,
                                        required=True)
    max_participants = fields.Integer(string='Maximum Participants')

    registration_ids = fields.One2many('university.event.registration', 'event_id', string='Registrations')
    total_registrations = fields.Integer(string='Total Registrations',
                                         compute='_compute_registrations')

    # Fee
    has_registration_fee = fields.Boolean(string='Has Registration Fee')
    registration_fee = fields.Monetary(string='Registration Fee', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    # Sponsors
    sponsor_ids = fields.One2many('event.sponsor', 'event_id', string='Sponsors')

    # Budget
    estimated_budget = fields.Monetary(string='Estimated Budget', currency_field='currency_id')
    actual_expense = fields.Monetary(string='Actual Expense', currency_field='currency_id')

    # Event Details
    description = fields.Html(string='Description')
    agenda = fields.Html(string='Agenda/Schedule')

    # Guest/Speaker
    has_guest_speaker = fields.Boolean(string='Has Guest Speaker')
    speaker_name = fields.Char(string='Speaker Name')
    speaker_designation = fields.Char(string='Speaker Designation')
    speaker_bio = fields.Html(string='Speaker Biography')

    # Certificate
    provides_certificate = fields.Boolean(string='Provides Certificate')
    certificate_template = fields.Binary(string='Certificate Template')

    # Attachments
    poster = fields.Binary(string='Event Poster', attachment=True)
    brochure = fields.Binary(string='Brochure', attachment=True)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('registration_open', 'Registration Open'),
        ('registration_closed', 'Registration Closed'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    # Feedback (using survey module)
    feedback_survey_id = fields.Many2one('survey.survey', string='Feedback Survey')

    # Photos/Gallery
    photo_ids = fields.Many2many('ir.attachment', string='Event Photos')

    # Remarks
    remarks = fields.Text(string='Remarks')

    _sql_constraints = [
        ('event_code_unique', 'unique(event_code)', 'Event Code must be unique!'),
    ]

    @api.model
    def create(self, vals):
        if vals.get('event_code', '/') == '/':
            vals['event_code'] = self.env['ir.sequence'].next_by_code('university.event') or '/'

        # Create calendar event automatically if not provided
        if not vals.get('calendar_event_id'):
            calendar_vals = {
                'name': vals.get('name', 'New Event'),
                'start': vals.get('start'),
                'stop': vals.get('stop'),
                'location': vals.get('location', ''),
                'description': vals.get('description', ''),
            }
            calendar_event = self.env['calendar.event'].create(calendar_vals)
            vals['calendar_event_id'] = calendar_event.id

        return super(UniversityEvent, self).create(vals)

    @api.depends('registration_ids')
    def _compute_registrations(self):
        for record in self:
            record.total_registrations = len(record.registration_ids.filtered(
                lambda r: r.state in ['registered', 'attended']))

    def action_publish(self):
        self.write({'state': 'published', 'website_published': True})

    def action_open_registration(self):
        self.write({'state': 'registration_open', 'registration_open': True})

    def action_close_registration(self):
        self.write({'state': 'registration_closed', 'registration_open': False})

    def action_start_event(self):
        self.write({'state': 'ongoing'})

    def action_complete(self):
        self.write({'state': 'completed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def toggle_website_published(self):
        """Toggle website publication status."""
        for record in self:
            record.website_published = not record.website_published
        return True

    def action_event_registration(self):
        """Open the event registrations."""
        self.ensure_one()
        return {
            'name': _('Event Registrations'),
            'type': 'ir.actions.act_window',
            'res_model': 'university.event.registration',
            'view_mode': 'list,form',
            'domain': [('event_id', '=', self.id)],
            'context': {'default_event_id': self.id, 'search_default_event_id': 1},
        }

