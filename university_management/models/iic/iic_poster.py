# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class IICPoster(models.Model):
    _name = 'iic.poster'
    _description = 'IIC Event Poster'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Poster Title', required=True)
    event_id = fields.Many2one('iic.event', string='Event', required=True, ondelete='cascade')

    template_type = fields.Selection([
        ('standard', 'Standard IIC Template'),
        ('workshop', 'Workshop Template'),
        ('seminar', 'Seminar Template'),
        ('custom', 'Custom Template'),
    ], string='Poster Template', default='standard', required=True)

    # Poster content fields (auto-populated)
    event_title = fields.Char(related='event_id.name', string='Event Title')
    event_date = fields.Datetime(related='event_id.event_date', string='Event Date')
    venue = fields.Char(related='event_id.venue', string='Venue')
    speaker_id = fields.Many2one('iic.speaker', related='event_id.speaker_id', string='Speaker')
    speaker_name = fields.Char(related='event_id.speaker_id.name', string='Speaker Name')
    speaker_designation = fields.Char(related='event_id.speaker_id.designation', string='Speaker Designation')
    speaker_profile = fields.Text(related='event_id.speaker_id.profile', string='Speaker Profile')
    speaker_photo = fields.Binary(related='event_id.speaker_id.photo', string='Speaker Photo')

    iic_president_id = fields.Many2one('hr.employee', related='event_id.iic_president_id', string='IIC President')
    iic_president_name = fields.Char(related='event_id.iic_president_id.name', string='IIC President Name', store=True)
    iic_president_designation = fields.Char(string='IIC President Designation')
    iic_convenor_id = fields.Many2one('hr.employee', related='event_id.iic_convenor_id', string='IIC Convenor')
    iic_convenor_name = fields.Char(related='event_id.iic_convenor_id.name', string='IIC Convenor Name', store=True)
    iic_convenor_designation = fields.Char(string='IIC Convenor Designation')
    iic_logo = fields.Binary(string='IIC Logo', attachment=True)
    institute_logo = fields.Binary(string='Institute Logo', attachment=True)
    highlight_text = fields.Char(string='Highlight Text')
    tagline = fields.Char(string='Tagline')
    publish_date = fields.Date(string='Publish Date')

    # Poster file
    poster_image = fields.Binary(string='Poster Image', attachment=True)
    poster_filename = fields.Char(string='Poster Filename')

    # Event photo gallery (fetched from iic.media photo records linked to this event)
    media_image_ids = fields.Many2many(
        'iic.media.image',
        relation='iic_poster_media_image_rel',
        column1='poster_id',
        column2='image_id',
        string='Event Photos',
        compute='_compute_media_image_ids',
        store=False,
    )

    # Pre-sliced rows for QWeb template (QWeb cannot call Python builtins like len/slice)
    gallery_row1 = fields.Many2many(
        'iic.media.image',
        relation='iic_poster_gallery_row1_rel',
        column1='poster_id',
        column2='image_id',
        string='Gallery Row 1',
        compute='_compute_media_image_ids',
        store=False,
    )

    gallery_row2 = fields.Many2many(
        'iic.media.image',
        relation='iic_poster_gallery_row2_rel',
        column1='poster_id',
        column2='image_id',
        string='Gallery Row 2',
        compute='_compute_media_image_ids',
        store=False,
    )

    @api.depends('event_id')
    def _compute_media_image_ids(self):
        for poster in self:
            if poster.event_id:
                media_records = self.env['iic.media'].search([
                    ('event_id', '=', poster.event_id.id),
                    ('media_type', '=', 'photo'),
                ])
                all_images = media_records.mapped('image_ids')
                poster.media_image_ids = all_images
                poster.gallery_row1 = all_images[:3]
                poster.gallery_row2 = all_images[3:6]
            else:
                poster.media_image_ids = self.env['iic.media.image']
                poster.gallery_row1 = self.env['iic.media.image']
                poster.gallery_row2 = self.env['iic.media.image']

    # Approval state
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('rejected', 'Rejected'),
        ('approved', 'Approved'),
        ('revision', 'Revision Required'),
        ('published', 'Published'),
    ], string='Approval Status', default='draft', tracking=True)

    approved_by = fields.Many2one('res.users', string='Approved By')
    approved_date = fields.Datetime(string='Approved Date')
    revision_notes = fields.Text(string='Revision Notes')

    # Social media publishing
    published_instagram = fields.Boolean(string='Published on Instagram')
    published_linkedin = fields.Boolean(string='Published on LinkedIn')
    published_facebook = fields.Boolean(string='Published on Facebook')
    published_website = fields.Boolean(string='Published on Website')

    def action_submit_approval(self):
        self.state = 'pending'

    def action_approve(self):
        self.state = 'approved'
        self.approved_by = self.env.user.id
        self.approved_date = fields.Datetime.now()
        # Update event state
        if self.event_id.iic_state in ('planning', 'poster_pending'):
            self.event_id.iic_state = 'poster_approved'
            self.event_id._log_approval('Poster approved')

    def action_reject(self):
        self.state = 'rejected'

    def action_print_poster(self):
        """Trigger QWeb PDF poster report."""
        return self.env.ref('university_management.action_report_iic_poster').report_action(self)

    def action_download_poster(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/?model=iic.poster&id=%d&field=poster_image&filename=%s&download=true' % (
                self.id, self.poster_filename or 'poster.png'),
            'target': 'self',
        }

    def action_request_revision(self):
        self.state = 'revision'

    def action_publish(self):
        self.state = 'published'