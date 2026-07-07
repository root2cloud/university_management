# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ExaminationSeating(models.Model):
    _name = 'examination.seating'
    _description = 'Exam Seating Arrangement'
    _order = 'examination_id, room_number_id, seat_number'

    name = fields.Char(string='Reference', compute='_compute_name', store=True)

    # Examination
    examination_id = fields.Many2one('examination.examination', string='Examination',
                                     required=True, index=True, ondelete='cascade')

    # Exam Timetable
    timetable_id = fields.Many2one('examination.timetable', string='Exam Schedule')
    exam_date = fields.Date(related='timetable_id.exam_date', string='Exam Date', store=True)
    subject_id = fields.Many2one(related='timetable_id.subject_id', string='Subject', store=True)

    # Student
    student_id = fields.Many2one('student.student', string='Student',
                                 required=True, index=True)
    registration_number = fields.Char(related='student_id.registration_number',
                                      string='Registration Number')

    # Hall Ticket
    hall_ticket_id = fields.Many2one('examination.hall.ticket', string='Hall Ticket')

    # Seating Details
    building_name_id = fields.Many2one('university.classroom', string='Building Name')
    floor_id = fields.Many2one('university.classroom', string='Floor')
    room_number_id = fields.Many2one('university.classroom', string='Room Number')

    seat_number = fields.Char(string='Seat Number', required=True)
    row_number = fields.Char(string='Row')
    column_number = fields.Char(string='Column')

    # Venue Details
    venue = fields.Char(string='Venue Name')

    # Invigilators
    invigilator_ids = fields.Many2many('faculty.faculty', 'seating_invigilator_rel',
                                       'seating_id', 'faculty_id',
                                       string='Invigilators')

    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        tracking=True,
    )

    # Status
    is_confirmed = fields.Boolean(string='Confirmed', compute='_compute_is_confirmed', store=True)

    # Remarks
    remarks = fields.Text(string='Remarks')

    _sql_constraints = [
        ('unique_seat', 'unique(examination_id, timetable_id, room_number_id, seat_number)',
         'Seat already allocated for this exam!'),
        ('unique_student_exam', 'unique(examination_id, timetable_id, student_id)',
         'Student already has a seat for this exam!'),
    ]

    @api.depends('student_id', 'room_number_id', 'seat_number')
    def _compute_name(self):
        for record in self:
            record.name = f"{record.student_id.registration_number} - {record.room_number_id}/{record.seat_number}"

    def action_confirm(self):
        self.write({'is_confirmed': True})

    @api.model
    def generate_seating_arrangement(self, examination_id, students_per_room=30):
        """Auto-generate seating arrangement"""
        examination = self.env['examination.examination'].browse(examination_id)

        # Get all students registered for examination
        hall_tickets = self.env['examination.hall.ticket'].search([
            ('examination_id', '=', examination_id),
            ('is_eligible', '=', True),
            ('state', 'in', ['issued', 'printed'])
        ])

        students = hall_tickets.mapped('student_id')

        # Simple room allocation logic
        room_counter = 1
        seat_counter = 1

        for student in students:
            room_number_id = f"R{room_counter:03d}"
            seat_number = f"S{seat_counter:03d}"

            self.create({
                'examination_id': examination_id,
                'student_id': student.id,
                'hall_ticket_id': hall_tickets.filtered(lambda h: h.student_id == student).id,
                'room_number_id': room_number_id,
                'seat_number': seat_number,
            })

            seat_counter += 1
            if seat_counter > students_per_room:
                room_counter += 1
                seat_counter = 1

    @api.depends('state')
    def _compute_is_confirmed(self):
        for rec in self:
            rec.is_confirmed = rec.state == 'confirmed'

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})
