# -*- coding: utf-8 -*-

import logging
from odoo import models, api

_logger = logging.getLogger(__name__)


class BiometricDeviceDetailsBridge(models.Model):
    """
    Bridge between hr_zk_attendance and faculty.attendance.

    Inherits biometric.device.details (from hr_zk_attendance module) and
    overrides action_download_attendance so that after the ZK module creates
    hr.attendance records, we automatically push the punch data into
    faculty.attendance and run the attendance classification engine.

    This is the PRODUCTION integration. For demos without a physical device,
    use the 'Simulate Punch' button on faculty.attendance instead.
    """
    _inherit = 'biometric.device.details'

    @api.model
    def _get_faculty_by_device_id(self, device_id_num):
        """Find faculty.faculty by their biometric device ID."""
        faculty = self.env['faculty.faculty'].search([
            ('device_id_num', '=', str(device_id_num)),
        ], limit=1)
        return faculty or False

    def action_download_attendance(self):
        """
        Override ZK download.
        1. Call the original ZK download (creates hr.attendance records).
        2. For each newly created hr.attendance belonging to a faculty member,
           fire process_punch() to create/update faculty.attendance.
        """
        # Capture hr.attendance IDs before download
        existing_ids = set(self.env['hr.attendance'].search([]).ids)

        # Call original ZK download
        result = super().action_download_attendance()

        # Find newly created hr.attendance records
        new_attendances = self.env['hr.attendance'].search([
            ('id', 'not in', list(existing_ids))
        ])

        FacultyAttendance = self.env['faculty.attendance']

        for att in new_attendances:
            # Check if this employee is a faculty member
            faculty = self.env['faculty.faculty'].search([
                ('employee_id', '=', att.employee_id.id)
            ], limit=1)

            if not faculty:
                # Also try matching by device_id_num
                device_id = getattr(att, 'device_id_num', False)
                if device_id:
                    faculty = self._get_faculty_by_device_id(device_id)

            if not faculty:
                _logger.debug(
                    'ZK Bridge: No faculty found for employee %s — skipping',
                    att.employee_id.name
                )
                continue

            try:
                FacultyAttendance.process_punch(
                    faculty_id=faculty.id,
                    check_in=att.check_in,
                    check_out=att.check_out or False,
                    hr_attendance_id=att.id,
                )
                _logger.info(
                    'ZK Bridge: Processed punch for faculty %s on %s',
                    faculty.name,
                    att.check_in.date() if att.check_in else 'unknown date',
                )
            except Exception as e:
                _logger.error(
                    'ZK Bridge: Failed to process punch for faculty %s — %s',
                    faculty.name, str(e)
                )

        return result