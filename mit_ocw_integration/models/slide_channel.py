import requests
from bs4 import BeautifulSoup
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class SlideChannel(models.Model):
    _inherit = 'slide.channel'

    ocw_course_url = fields.Char(string='OCW Course URL')

    @api.model
    def _sync_ocw_courses(self):
        """Sync MIT OCW courses to Odoo e-learning"""
        OCW_COURSE_URL = 'https://ocw.mit.edu/courses/'
        try:
            response = requests.get(OCW_COURSE_URL, headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            courses = []
            course_elements = soup.find_all('div', class_='course-card')  # Updated selector
            _logger.info(f"Found {len(course_elements)} course elements")
            for course in course_elements:
                title = course.find('h2', class_='card-title').text.strip() if course.find('h2',
                                                                                           class_='card-title') else 'No Title'
                link = course.find('a')['href'] if course.find('a') else ''
                description = course.find('p', class_='card-description').text.strip() if course.find('p',
                                                                                                      class_='card-description') else 'No Description'
                courses.append({
                    'title': title,
                    'link': f"https://ocw.mit.edu{link}" if link else '',
                    'description': description
                })
                _logger.info(f"Scraped course: {title}, Link: {link}, Description: {description}")

            _logger.info(f"Scraped {len(courses)} courses from OCW")

            existing_courses = self.search_read([('name', 'in', [course['title'] for course in courses])], ['name'])
            existing_titles = [course['name'] for course in existing_courses]

            for course in courses:
                if course['title'] not in existing_titles:
                    self.create({
                        'name': course['title'],
                        'description': course['description'],
                        'website_url': course['link'],
                        'channel_type': 'training',
                        'ocw_course_url': course['link'],
                    })
                    _logger.info(f"Created course: {course['title']}")
                else:
                    _logger.info(f"Course already exists: {course['title']}")
        except Exception as e:
            _logger.error(f"Error syncing OCW courses: {e}")