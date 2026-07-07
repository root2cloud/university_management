import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class EdxCourseSync(models.Model):
    _name = 'edx.course.sync'
    _description = 'edX Course Sync Utility'

    @api.model
    def fetch_edx_courses(self):
        # Step 1: Auth (if needed)
        client_id = 'YOUR_CLIENT_ID'
        client_secret = 'YOUR_CLIENT_SECRET'
        token_url = 'https://courses.edx.org/oauth2/v1/access_token'
        course_url = 'https://courses.edx.org/api/courses/v1/courses/'

        auth_data = {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret
        }

        response = requests.post(token_url, data=auth_data)
        if response.status_code != 200:
            raise UserError(_("Failed to authenticate with edX API"))

        access_token = response.json().get('access_token')
        headers = {
            'Authorization': f'Bearer {access_token}',
        }

        # Step 2: Get Courses
        course_response = requests.get(course_url, headers=headers)
        if course_response.status_code != 200:
            raise UserError(_("Failed to fetch courses from edX"))

        courses = course_response.json().get('results', [])

        for course in courses:
            code = course.get('course_id')
            title = course.get('title')
            short_desc = course.get('short_description')

            existing = self.env['slide.channel'].search([('code', '=', code)], limit=1)

            if existing:
                existing.write({
                    'name': title,
                    'description': short_desc
                })
            else:
                self.env['slide.channel'].create({
                    'name': title,
                    'description': short_desc,
                    'code': code,
                    'channel_type': 'training',
                    'visibility': 'public'
                })
