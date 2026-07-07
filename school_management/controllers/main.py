from odoo import http
from odoo.http import request


class StudentAPI(http.Controller):

    @http.route('/api/student/create', type='json', auth='public', methods=['POST'], csrf=False)
    def create_student(self, **kwargs):
        try:
            name = kwargs.get('name')
            age = kwargs.get('age')
            date_of_birth = kwargs.get('date_of_birth')
            cls = kwargs.get('cls')
            rol_no = kwargs.get('rol_no')

            print(name, age, date_of_birth, cls, rol_no)

            if not name or not age or not date_of_birth:
                return {"status": "error", "message": "Missing required fields (name, age, date_of_birth)"}

            student = request.env['students.info'].sudo().create_student({
                'name': name,
                'age': age,
                'date_of_birth': date_of_birth,
                'cls': cls,
                'rol_no': rol_no,
            })

            return {
                "status": "success",
                "student_id": student.id,
                "name": student.name,
                "age": student.age,
                "class": student.cls,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
