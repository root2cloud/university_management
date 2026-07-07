# from odoo import models, fields, api
# from odoo.exceptions import ValidationError
# from google.cloud import vision
# import base64
# import logging
# import os
# from reportlab.pdfgen import canvas
# from reportlab.lib.pagesizes import letter
# from reportlab.lib.utils import ImageReader
# from io import BytesIO
# from datetime import timedelta
# import torch
# import trimesh
# import numpy as np
# from PIL import Image
# try:
#     from threestudio.models import DreamFusionPipeline  # Hypothetical threestudio API
# except ImportError:
#     from diffusers import StableDiffusionPipeline  # Fallback to 2D pipeline
#
# _logger = logging.getLogger(__name__)
# _logger.info("DesignProject model loading...")
#
# class DesignProject(models.Model):
#     _name = 'design.project'
#     _description = 'Design Project'
#     _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
#
#     # Initialize threestudio pipeline (or fallback to Stable Diffusion)
#     try:
#         if 'DreamFusionPipeline' in globals():
#             dreamfusion_pipe = DreamFusionPipeline.from_pretrained(
#                 "threestudio/dreamfusion-sd", torch_dtype=torch.float32
#             )
#             dreamfusion_pipe = dreamfusion_pipe.to("cpu")
#         else:
#             _logger.warning("threestudio DreamFusionPipeline not found, falling back to Stable Diffusion")
#             dreamfusion_pipe = StableDiffusionPipeline.from_pretrained(
#                 "CompVis/stable-diffusion-v1-4", torch_dtype=torch.float32
#             )
#             dreamfusion_pipe = dreamfusion_pipe.to("cpu")
#     except Exception as e:
#         _logger.error("Failed to initialize threestudio/Stable Diffusion: %s", str(e))
#         raise ValidationError(
#             "Failed to initialize generative model. Please ensure the model is installed and your system has enough resources."
#         )
#
#     # Fields
#     name = fields.Char(string='Project Name', required=True)
#     room_name = fields.Char(string='Room Name', required=True)
#     square_feet = fields.Float(string='Square Footage', required=True)
#     length = fields.Float(string='Length (ft)', required=True)
#     breadth = fields.Float(string='Breadth (ft)', required=True)
#     style_preference = fields.Selection([
#         ('modern', 'Modern'),
#         ('traditional', 'Traditional'),
#         ('minimalistic', 'Minimalistic'),
#     ], string='Style Preference', default='modern')
#     design_options_ids = fields.One2many('design.option', 'project_id', string='Design Options')
#     selected_design_id = fields.Many2one('design.option', string='Selected Design')
#     design_document = fields.Binary(string='Design Document', attachment=True, compute='_compute_design_document',
#                                    store=True)
#     document_name = fields.Char(string='Document Name', compute='_compute_design_document', store=True)
#     component_ids = fields.One2many('design.component', 'project_id', string='Components')
#     warranty_period = fields.Integer(string='Warranty Period (Days)', default=90)
#     start_date = fields.Date(string='Start Date', default=fields.Date.today)
#     expiry_date = fields.Date(string='Expiry Date', compute='_compute_expiry_date', store=True)
#     service_request_ids = fields.One2many('design.service.request', 'project_id', string='Service Requests')
#     state = fields.Selection([
#         ('active', 'Active'),
#         ('expired', 'Expired'),
#         ('serviced', 'Serviced'),
#     ], string='Status', compute='_compute_state', store=True)
#     raw_design_image = fields.Binary(string='Raw Design Image', attachment=False)
#     partner_id = fields.Many2one('res.partner', string='Customer')
#
#     @api.depends('selected_design_id')
#     def _compute_design_document(self):
#         for record in self:
#             if record.selected_design_id and record.selected_design_id.design_image:
#                 record.design_document = record.selected_design_id.design_image
#                 record.document_name = f"{record.name}_3d_design_{record.selected_design_id.id}.pdf"
#             else:
#                 record.design_document = False
#                 record.document_name = False
#
#     @api.depends('start_date', 'warranty_period')
#     def _compute_expiry_date(self):
#         for record in self:
#             if record.start_date and record.warranty_period:
#                 record.expiry_date = record.start_date + timedelta(days=record.warranty_period)
#             else:
#                 record.expiry_date = False
#
#     @api.depends('expiry_date')
#     def _compute_state(self):
#         today = fields.Date.today()
#         for record in self:
#             if not record.expiry: record.state = 'active'
#             elif record.expiry_date >= today:
#                 record.state = 'active'
#             else:
#                 record.state = 'expired' if not record.service_request_ids else 'serviced'
#
#     def _compute_access_url(self):
#         for record in self:
#             record.access_url = f'/my/designs/{record.id}'
#
#     @api.model_create_multi
#     def create(self, vals_list):
#         _logger.info("Creating project(s) with vals: %s", vals_list)
#         records = super(DesignProject, self).create(vals_list)
#         return records
#
#     def write(self, vals):
#         _logger.info("Updating project(s) with vals: %s", vals)
#         res = super(DesignProject, self).write(vals)
#         return res
#
#     def generate_design_options(self):
#         _logger.info("Generating 3D design options for project: %s", self.name)
#         # Validate room dimensions
#         if not (self.square_feet and self.length and self.breadth):
#             raise ValidationError("Please provide room dimensions (square footage, length, breadth).")
#         # Check if square footage matches length * breadth
#         if abs(self.length * self.breadth - self.square_feet) > 0.1:
#             raise ValidationError(
#                 f"Square footage ({self.square_feet} sq ft) does not match length ({self.length} ft) x breadth ({self.breadth} ft)."
#             )
#         # Limit dimensions to realistic values
#         if self.length > 100 or self.breadth > 100 or self.square_feet > 10000:
#             raise ValidationError("Room dimensions are too large. Please use realistic values (e.g., length/breadth < 100 ft, square footage < 10,000 sq ft).")
#
#         prompt = (
#             f"A 3D {self.style_preference} {self.room_name} interior design with furniture, "
#             f"dimensions {self.length}ft x {self.breadth}ft, {self.square_feet} sq ft, high-quality, realistic"
#         )
#         self.design_options_ids.unlink()
#         for i in range(3):
#             try:
#                 _logger.info("Generating 3D design option %s with prompt: %s", i + 1, prompt)
#                 if 'DreamFusionPipeline' in globals():
#                     # Generate 3D model using threestudio
#                     model_3d = self.dreamfusion_pipe(
#                         prompt=f"{prompt} (Option {i + 1})",
#                         num_inference_steps=50,  # Adjust for CPU performance
#                         guidance_scale=7.5,
#                         output_type="mesh"  # Hypothetical mesh output
#                     ).meshes[0]
#                     # Convert 3D model to 2D image
#                     scene = trimesh.Scene(model_3d)
#                     image_data = scene.save_image(resolution=(256, 256))  # Lower resolution for CPU
#                     image = Image.open(BytesIO(image_data))
#                 else:
#                     # Fallback to Stable Diffusion
#                     _logger.warning("Using fallback Stable Diffusion for design option %s", i + 1)
#                     image = self.dreamfusion_pipe(f"{prompt} (Option {i + 1})").images[0]
#
#                 # Convert image to bytes (JPEG format)
#                 buffer = BytesIO()
#                 image.save(buffer, format="JPEG")
#                 image_content = buffer.getvalue()
#
#                 # Save raw image for component extraction
#                 self.raw_design_image = base64.b64encode(image_content)
#
#                 # Create PDF
#                 pdf_buffer = BytesIO()
#                 pdf = canvas.Canvas(pdf_buffer, pagesize=letter)
#                 pdf.drawString(100, 750, f"3D Design Option {i + 1} for {self.room_name}")
#                 pdf.drawImage(ImageReader(BytesIO(image_content)), 36, 36, width=540, height=720)
#                 pdf.showPage()
#                 pdf.save()
#                 pdf_data = pdf_buffer.getvalue()
#                 pdf_buffer.close()
#
#                 if not pdf_data.startswith(b'%PDF-'):
#                     _logger.error("Generated PDF is invalid: %s", pdf_data[:100])
#                     raise ValidationError("Failed to generate a valid PDF file.")
#
#                 # Create design option
#                 self.env['design.option'].create({
#                     'project_id': self.id,
#                     'name': f"3D Design Option {i + 1}",
#                     'design_image': base64.b64encode(pdf_data),
#                     'description': f"3D {self.style_preference} design for {self.room_name} ({self.square_feet} sq ft)",
#                 })
#             except Exception as e:
#                 _logger.error("Error generating 3D design option %s: %s", i + 1, str(e))
#                 raise ValidationError(f"Failed to generate 3D design option {i + 1}: {str(e)}")
#
#         return {
#             'type': 'ir.actions.act_window',
#             'res_model': 'design.project',
#             'view_mode': 'form',
#             'res_id': self.id,
#             'target': 'current',
#         }
#
#     def edit_selected_design(self):
#         if not self.selected_design_id:
#             raise ValidationError("Please select a design to edit.")
#
#         prompt = (
#             f"Refined 3D {self.style_preference} {self.room_name} interior design with more furniture, "
#             f"dimensions {self.length}ft x {self.breadth}ft, {self.square_feet} sq ft, high-quality, realistic"
#         )
#         _logger.info("Editing selected 3D design with prompt: %s", prompt)
#         try:
#             if 'DreamFusionPipeline' in globals():
#                 model_3d = self.dreamfusion_pipe(
#                     prompt=prompt,
#                     num_inference_steps=50,
#                     guidance_scale=7.5,
#                     output_type="mesh"
#                 ).meshes[0]
#                 scene = trimesh.Scene(model_3d)
#                 image_data = scene.save_image(resolution=(256, 256))
#                 image = Image.open(BytesIO(image_data))
#             else:
#                 image = self.dreamfusion_pipe(prompt).images[0]
#
#             buffer = BytesIO()
#             image.save(buffer, format="JPEG")
#             image_content = buffer.getvalue()
#
#             self.raw_design_image = base64.b64encode(image_content)
#
#             pdf_buffer = BytesIO()
#             pdf = canvas.Canvas(pdf_buffer, pagesize=letter)
#             pdf.drawString(100, 750, f"Edited 3D Design for {self.room_name}")
#             pdf.drawImage(ImageReader(BytesIO(image_content)), 36, 36, width=540, height=720)
#             pdf.showPage()
#             pdf.save()
#             pdf_data = pdf_buffer.getvalue()
#             pdf_buffer.close()
#
#             if not pdf_data.startswith(b'%PDF-'):
#                 raise ValidationError("Failed to generate a valid PDF file for edited design.")
#
#             self.selected_design_id.write({
#                 'design_image': base64.b64encode(pdf_data),
#                 'description': f"Edited 3D {self.style_preference} design for {self.room_name} ({self.square_feet} sq ft)",
#             })
#
#             return {
#                 'type': 'ir.actions.act_window',
#                 'res_model': 'design.project',
#                 'view_mode': 'form',
#                 'res_id': self.id,
#                 'target': 'current',
#             }
#         except Exception as e:
#             _logger.error("Error editing selected 3D design: %s", str(e))
#             raise ValidationError(f"Failed to edit selected 3D design: {str(e)}")
#
#     def extract_components(self):
#         _logger.info("Extract components called for project: %s (ID: %s)", self.name, self.id)
#         _logger.info("Context: %s", self.env.context)
#         self.ensure_one()
#         if not self.exists():
#             _logger.warning("Cannot extract components: The project record does not exist.")
#             raise ValidationError(
#                 "Cannot extract components: The project record does not exist. Please save the project first.")
#         if not self.raw_design_image:
#             _logger.warning("No raw image available for project: %s", self.name)
#             raise ValidationError("No raw image available for component extraction. Please generate a design first.")
#         credentials_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
#         if not credentials_path or not os.path.exists(credentials_path):
#             _logger.error("GOOGLE_APPLICATION_CREDENTIALS not set or invalid: %s", credentials_path)
#             raise ValidationError("Google Cloud Vision API credentials not configured properly.")
#         try:
#             document_content = base64.b64decode(self.raw_design_image)
#             _logger.info("Raw image decoded, size: %s bytes", len(document_content))
#             client = vision.ImageAnnotatorClient()
#             image = vision.Image(content=document_content)
#             _logger.info("Performing label detection...")
#             response = client.label_detection(image=image)
#             labels = response.label_annotations
#             _logger.info("Labels detected: %s", [label.description for label in labels])
#             if not labels:
#                 _logger.info("No labels detected, trying object localization")
#                 response = client.object_localization(image=image)
#                 objects = response.localized_object_annotations
#                 _logger.info("Objects detected: %s", [obj.name for obj in objects])
#                 labels = [vision.EntityAnnotation(description=obj.name) for obj in objects]
#             if not labels:
#                 _logger.warning("No components detected for project: %s", self.name)
#                 self.env['mail.message'].create({
#                     'body': "No components detected in the image.",
#                     'model': 'design.project',
#                     'res_id': self.id,
#                     'message_type': 'notification',
#                     'subtype_id': self.env.ref('mail.mt_note').id,
#                 })
#                 self.component_ids.unlink()
#                 return {
#                     'type': 'ir.actions.act_window',
#                     'res_model': 'design.project',
#                     'view_mode': 'form',
#                     'res_id': self.id,
#                     'target': 'current',
#                 }
#             self.component_ids.unlink()
#             for label in labels:
#                 component_name = label.description
#                 component_type = 'furniture' if component_name.lower() in ['sofa', 'bed'] else \
#                     'chair' if component_name.lower() == 'chair' else \
#                         'table' if component_name.lower() == 'table' else 'decor'
#                 _logger.info("Creating component: %s (type: %s)", component_name, component_type)
#                 self.env['design.component'].create({
#                     'project_id': self.id,
#                     'name': component_name,
#                     'component_type': component_type,
#                     'quantity': 1,
#                     'dimensions': 'N/A',
#                 })
#             _logger.info("Total components created: %s", len(self.component_ids))
#             return {
#                 'type': 'ir.actions.act_window',
#                 'res_model': 'design.project',
#                 'view_mode': 'form',
#                 'res_id': self.id,
#                 'target': 'current',
#             }
#         except Exception as e:
#             _logger.error("Vision API error for project %s: %s", self.name, str(e))
#             self.env['mail.message'].create({
#                 'body': f"Vision API Error: {str(e)}",
#                 'model': 'design.project',
#                 'res_id': self.id,
#                 'message_type': 'notification',
#                 'subtype_id': self.env.ref('mail.mt_note').id,
#             })
#             raise ValidationError(f"Failed to extract components: {str(e)}")
#
#     def generate_design(self):
#         _logger.info("Generating 3D design for project: %s", self.name)
#         if not self.room_name:
#             raise ValidationError("Please provide a room name.")
#         if not (self.square_feet and self.length and self.breadth):
#             raise ValidationError("Please provide room dimensions (square footage, length, breadth).")
#         if abs(self.length * self.breadth - self.square_feet) > 0.1:
#             raise ValidationError(
#                 f"Square footage ({self.square_feet} sq ft) does not match length ({self.length} ft) x breadth ({self.breadth} ft)."
#             )
#         if self.length > 100 or self.breadth > 100 or self.square_feet > 10000:
#             raise ValidationError("Room dimensions are too large. Please use realistic values.")
#
#         prompt = f"A 3D modern {self.room_name} interior design with furniture, high-quality, realistic"
#         try:
#             if 'DreamFusionPipeline' in globals():
#                 model_3d = self.dreamfusion_pipe(
#                     prompt=prompt,
#                     num_inference_steps=50,
#                     guidance_scale=7.5,
#                     output_type="mesh"
#                 ).meshes[0]
#                 scene = trimesh.Scene(model_3d)
#                 image_data = scene.save_image(resolution=(256, 256))
#                 image = Image.open(BytesIO(image_data))
#             else:
#                 image = self.dreamfusion_pipe(prompt).images[0]
#
#             buffer = BytesIO()
#             image.save(buffer, format="JPEG")
#             image_content = buffer.getvalue()
#
#             self.raw_design_image = base64.b64encode(image_content)
#
#             pdf_buffer = BytesIO()
#             pdf = canvas.Canvas(pdf_buffer, pagesize=letter)
#             pdf.drawString(100, 750, f"3D Design for {self.room_name}")
#             pdf.drawImage(ImageReader(BytesIO(image_content)), 36, 36, width=540, height=720)
#             pdf.showPage()
#             pdf.save()
#             pdf_data = pdf_buffer.getvalue()
#             pdf_buffer.close()
#
#             if not pdf_data.startswith(b'%PDF-'):
#                 raise ValidationError("Failed to generate a valid PDF file.")
#
#             self.design_document = base64.b64encode(pdf_data)
#             self.document_name = f"{self.name}_3d_design.pdf"
#
#             self.extract_components()
#
#             if self.design_document:
#                 attachment = self.env['ir.attachment'].search([
#                     ('res_model', '=', 'design.project'),
#                     ('res_field', '=', 'design_document'),
#                     ('res_id', '=', self.id)
#                 ], limit=1)
#                 if attachment:
#                     attachment.write({
#                         'name': self.document_name,
#                         'mimetype': 'application/pdf',
#                     })
#                 else:
#                     self.env['ir.attachment'].create({
#                         'name': self.document_name,
#                         'type': 'binary',
#                         'datas': self.design_document,
#                         'res_model': 'design.project',
#                         'res_field': 'design_document',
#                         'res_id': self.id,
#                         'mimetype': 'application/pdf',
#                     })
#
#             return {
#                 'type': 'ir.actions.act_window',
#                 'res_model': 'design.project',
#                 'view_mode': 'form',
#                 'res_id': self.id,
#                 'target': 'current',
#             }
#         except Exception as e:
#             _logger.error("Failed to generate 3D design for project %s: %s", self.name, str(e))
#             raise ValidationError(f"Failed to generate 3D design: {str(e)}")
#
#     def download_design_document(self):
#         _logger.info("Downloading design document for project: %s", self.name)
#         if not self.design_document:
#             raise ValidationError("No design document available to download.")
#         return {
#             'type': 'ir.actions.act_url',
#             'url': f'/web/content/design.project/{self.id}/design_document/{self.document_name}?download=true',
#             'target': 'self',
#         }
#
#     def request_service(self):
#         if self.state != 'expired':
#             raise ValidationError("Service can only be requested for expired projects.")
#         return {
#             'type': 'ir.actions.act_window',
#             'res_model': 'design.service.request',
#             'view_mode': 'form',
#             'target': 'new',
#             'context': {'default_project_id': self.id},
#         }