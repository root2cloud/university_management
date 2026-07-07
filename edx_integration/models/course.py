from odoo import models, fields, api
import logging
import requests
from odoo.exceptions import UserError
from datetime import datetime

_logger = logging.getLogger(__name__)

class ELearningCourse(models.Model):
    _name = 'elearning.course'
    _description = 'eLearning Course'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Course Title", required=True, tracking=True)
    description = fields.Text(string="Description", tracking=True)
    source = fields.Char(string="Source", default="eDX", tracking=True)
    external_id = fields.Char(string="External Course ID", index=True, tracking=True)
    course_url = fields.Char(string="Course URL", tracking=True)
    last_sync = fields.Datetime(string="Last Synced", tracking=True)
    video_url = fields.Char(string="Video URL", tracking=True)
    slide_channel_id = fields.Many2one('slide.channel', string="eLearning Course", tracking=True)

    def _get_edx_access_token(self):
        """Fetch OAuth 2.0 access token from eDX API"""
        try:
            config = self.env['ir.config_parameter'].sudo()
            client_id = config.get_param('edx_client_id', default='')
            client_secret = config.get_param('edx_client_secret', default='')
            if not client_id or not client_secret:
                raise UserError("eDX Client ID or Client Secret not configured in Odoo settings.")

            token_url = "https://api.edx.org/oauth2/v1/access_token"
            data = {
                'grant_type': 'client_credentials',
                'client_id': client_id,
                'client_secret': client_secret,
                'scope': 'read',
            }
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            return response.json().get('access_token')
        except Exception as e:
            _logger.error(f"Error fetching eDX access token: {str(e)}")
            raise UserError(f"Failed to authenticate with eDX API: {str(e)}")

    @api.model
    def sync_edx_courses(self):
        """Sync real eDX courses and videos"""
        try:
            access_token = self._get_edx_access_token()
            if not access_token:
                raise UserError("Unable to obtain eDX access token.")

            # Fetch courses from eDX API
            api_url = "https://api.edx.org/catalog/v2/courses"
            headers = {'Authorization': f'Bearer {access_token}'}
            courses = []
            while api_url:
                response = requests.get(api_url, headers=headers)
                response.raise_for_status()
                data = response.json()
                courses.extend(data.get('results', []))
                api_url = data.get('next')  # Handle pagination

            # Sync to elearning.course and slide.channel
            for course in courses:
                course_data = {
                    'name': course.get('name', ''),
                    'description': course.get('overview', course.get('description', '')),
                    'source': 'eDX',
                    'external_id': course.get('course_id', course.get('id', '')),
                    'course_url': course.get('course_url', ''),
                    'video_url': course.get('media', {}).get('course_video', {}).get('uri', ''),
                    'last_sync': fields.Datetime.now(),
                }
                existing_course = self.search([('external_id', '=', course.get('course_id', course.get('id', '')))])
                if existing_course:
                    existing_course.write(course_data)
                else:
                    existing_course = self.create(course_data)

                # Sync to slide.channel
                slide_channel = self.env['slide.channel'].search([('name', '=', course.get('name'))])
                if not slide_channel:
                    slide_channel = self.env['slide.channel'].create({
                        'name': course.get('name'),
                        'description': course.get('overview', course.get('description', '')),
                        'channel_type': 'training',
                        'website_published': True,
                    })
                    # Add video as slide if video_url exists
                    if course_data['video_url']:
                        self.env['slide.slide'].create({
                            'name': f"{course.get('name')} Video",
                            'channel_id': slide_channel.id,
                            'slide_type': 'video',
                            'url': course_data['video_url'],
                            'is_published': True,
                        })
                existing_course.slide_channel_id = slide_channel.id
                _logger.info(f"Synced course: {course.get('name')}")
            return True
        except Exception as e:
            _logger.error(f"Error syncing eDX courses: {str(e)}")
            return False