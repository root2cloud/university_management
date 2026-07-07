# -*- coding: utf-8 -*-

from odoo import models, fields, api


class IICMediaImage(models.Model):
    _name = 'iic.media.image'
    _description = 'IIC Media Image'
    _order = 'media_id, sequence'

    media_id = fields.Many2one('iic.media', string='Media Record', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10)
    name = fields.Char(string='Caption')
    image = fields.Binary(string='Image', attachment=True, required=True)
    filename = fields.Char(string='Filename')
    is_cover = fields.Boolean(string='Use as Cover', default=False)


class IICMedia(models.Model):
    _name = 'iic.media'
    _description = 'IIC Event Media'
    _order = 'event_id, sequence'

    event_id = fields.Many2one('iic.event', string='Event', required=True, ondelete='cascade')
    name = fields.Char(string='Description', required=True)
    sequence = fields.Integer(string='Sequence', default=10)

    media_type = fields.Selection([
        ('photo', 'Photo'),
        ('video', 'Video Link'),
        ('document', 'Document'),
    ], string='Media Type', default='photo', required=True)

    image = fields.Binary(string='Image / File', attachment=True)
    filename = fields.Char(string='Filename')
    attachment = fields.Many2one('ir.attachment', string='Attachment')
    media_url = fields.Char(string='Media URL')
    video_url = fields.Char(string='Video URL')

    # Multiple images
    image_ids = fields.One2many('iic.media.image', 'media_id', string='Photo Gallery')

    summary = fields.Text(string='Event Summary')
    key_takeaways = fields.Text(string='Key Takeaways')
    student_insights = fields.Text(string='Student Participation Insights')

    uploaded_by = fields.Many2one('res.users', string='Uploaded By', default=lambda self: self.env.user)
    upload_date = fields.Datetime(string='Upload Date', default=fields.Datetime.now)