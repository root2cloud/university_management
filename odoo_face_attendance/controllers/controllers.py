import io
import json
import base64
import numpy as np
import face_recognition
from odoo import http, fields
from odoo.http import request

class FaceAttendance(http.Controller):

    # @http.route('/face_attendance', type='http', auth='public', csrf=False)
    # def face_attendance(self, **kwargs):
    #     return """<!DOCTYPE html>
    #             <html>
    #             <head><title>Face Upload</title></head>
    #             <body>
    #                 <h1>Upload Face for Attendance</h1>
    #                 <form action="/submit_face" method="post" enctype="multipart/form-data">
    #                     <input type="file" name="face_image" accept="image/*" required />
    #                     <br><br>
    #                     <input type="submit" value="Submit">
    #                 </form>
    #             </body>
    #             </html>"""
    
    @http.route('/face_attendance', type='http', auth='public', csrf=False)
    def face_attendance(self, **kwargs):
        return """<!DOCTYPE html>
    <html>
    <head>
        <title>Face Attendance</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 0;
                text-align: center;
                background-color: #f2f2f2;
            }
            h1 {
                margin-top: 20px;
            }
            .container {
                max-width: 600px;
                margin: 0 auto;
                margin-top: 7%;
                padding: 20px;
                border: 1px solid #ccc;
                border-radius: 8px;
                background-color: #fff;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                
            }
            video, canvas {
                width: 100%;
                height: auto;
                border: 1px solid #ccc;
                border-radius: 8px;
            }
            button, input[type="submit"] {
                margin-top: 15px;
                padding: 10px 20px;
                font-size: 16px;
                border: none;
                background-color: #71639e;
                color: white;
                border-radius: 5px;
                cursor: pointer;
            }
            button:hover, input[type="submit"]:hover {
                background-color: #71639e;
            }
            #submit_photo {
                display: none;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Take a Photo for Attendance</h1>
            <video id="video" autoplay playsinline></video>
            <br>
            <button id="snap">Capture</button>
            <canvas id="canvas" style="display: none;"></canvas>
            <form id="uploadForm" action="/submit_face" method="post">
                <input type="hidden" name="face_image" id="face_image">
                <input type="submit" id="submit_photo" value="Submit Photo">
            </form>
        </div>

        <script>
            const video = document.getElementById('video');
            const canvas = document.getElementById('canvas');
            const snap = document.getElementById('snap');
            const faceImageInput = document.getElementById('face_image');
            const context = canvas.getContext('2d');

            navigator.mediaDevices.getUserMedia({ video: true })
                .then(stream => {
                    video.srcObject = stream;
                })
                .catch(err => {
                    alert("Camera access denied: " + err);
                });

            snap.addEventListener('click', () => {
                canvas.style.display = 'block';
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                context.drawImage(video, 0, 0, canvas.width, canvas.height);
                document.querySelector('video').style.display = 'none';
                document.getElementById('submit_photo').style.display = 'block';
                snap.style.display = 'none';
                const imageData = canvas.toDataURL('image/jpeg');
                faceImageInput.value = imageData;
            });
        </script>
    </body>
    </html>"""



    @http.route('/submit_face', type='http', auth='public', csrf=False, methods=['POST'])
    def submit_face(self, **kwargs):
        data_url = kwargs.get('face_image')

        if not data_url or not data_url.startswith('data:image'):
            return self._render_result("No image data received.")

        try:
            header, encoded = data_url.split(",", 1)
            image_bytes = base64.b64decode(encoded)
            image_stream = io.BytesIO(image_bytes)
            image = face_recognition.load_image_file(image_stream)
            encodings = face_recognition.face_encodings(image)

            if not encodings:
                return self._render_result("⚠️ No face detected.")

            input_encoding = encodings[0]
            employees = request.env['hr.employee'].sudo().search([('face_encoding', '!=', False)])

            for emp in employees:
                emp_encoding = json.loads(emp.face_encoding)
                match = face_recognition.compare_faces([np.array(emp_encoding)], input_encoding, tolerance=0.5)

                if match[0]:
                    Attendance = request.env['hr.attendance'].sudo()
                    last_att = Attendance.search([('employee_id', '=', emp.id)], order='check_in desc', limit=1)
                    now = fields.Datetime.now()

                    if last_att and not last_att.check_out:
                        last_att.check_out = now
                        status = "Checked out"
                    else:
                        Attendance.create({'employee_id': emp.id, 'check_in': now})
                        status = "Checked in"

                    return self._render_result(f"✅ Success: {emp.name} - {status}")

            return self._render_result("⚠️ No matching face found.")

        except Exception as e:
            return self._render_result(f"❌ Error: {str(e)}")

    def _render_result(self, message):
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Attendance Result</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f9f9f9;
                    margin: 0;
                    padding: 0;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    text-align: center;
                }}
                .message-box {{
                    background-color: white;
                    padding: 30px;
                    border-radius: 12px;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                    max-width: 90%;
                    width: 400px;
                }}
                .message {{
                    font-size: 1.5em;
                    margin: 0;
                    word-wrap: break-word;
                }}
            </style>
        </head>
        <body>
            <div class="message-box">
                <p class="message">{message}</p>
            </div>
        </body>
        </html>
        """
