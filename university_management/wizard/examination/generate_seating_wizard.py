# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class GenerateSeatingWizard(models.TransientModel):
    """
    Wizard for generating seating arrangements for an examination
    """
    _name = 'generate.examination.seating.wizard'
    _description = 'Generate Seating Arrangement Wizard'

    examination_id = fields.Many2one(
        'examination.examination',
        string='Examination',
        required=True,
        domain=[('state', 'in', ['scheduled', 'registration_open', 'registration_closed', 'ongoing'])]
    )
    students_per_room = fields.Integer(
        string='Students Per Room',
        default=30,
        required=True
    )
    clear_existing = fields.Boolean(
        string='Clear Existing Seating',
        default=False,
        help='If checked, existing seating arrangements for this examination will be removed before generating new ones.'
    )

    def action_generate(self):
        """Generate seating arrangement for the examination"""
        self.ensure_one()

        examination = self.examination_id

        if self.clear_existing:
            existing = self.env['examination.seating'].search([
                ('examination_id', '=', examination.id)
            ])
            existing.unlink()

        # Get all eligible issued hall tickets
        hall_tickets = self.env['examination.hall.ticket'].search([
            ('examination_id', '=', examination.id),
            ('is_eligible', '=', True),
            ('state', 'in', ['issued', 'printed'])
        ])

        if not hall_tickets:
            raise UserError(_(
                'No eligible issued hall tickets found for this examination. '
                'Please generate and issue hall tickets first.'
            ))

        students_per_room = self.students_per_room or 30
        room_counter = 1
        seat_counter = 1
        created = 0

        for ticket in hall_tickets:
            student = ticket.student_id

            # Skip if already seated
            existing_seat = self.env['examination.seating'].search([
                ('examination_id', '=', examination.id),
                ('student_id', '=', student.id),
            ], limit=1)
            if existing_seat:
                continue

            seat_number = f"S{seat_counter:03d}"

            self.env['examination.seating'].create({
                'examination_id': examination.id,
                'student_id': student.id,
                'hall_ticket_id': ticket.id,
                'seat_number': seat_number,
                'row_number': str(room_counter),
                'venue': f"Room {room_counter:03d}",
            })

            created += 1
            seat_counter += 1
            if seat_counter > students_per_room:
                room_counter += 1
                seat_counter = 1

        return {
            'name': _('Seating Arrangement'),
            'type': 'ir.actions.act_window',
            'res_model': 'examination.seating',
            'view_mode': 'list,form',
            'domain': [('examination_id', '=', examination.id)],
            'target': 'current',
            'context': {
                'create': False,
            }
        }