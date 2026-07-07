from odoo import models, fields

class StudentWizard(models.TransientModel):
    _name = "student.wizard"
    _description = "Student Wizard"

    message = fields.Char("Message")

    def confirm_action(self):
        return {
            'effect': {
                'fadeout': 'slow',
                'message': 'Action Completed!',
                'type': 'rainbow_man',
            }
        }
