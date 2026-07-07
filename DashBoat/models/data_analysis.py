from odoo import models, fields, api
import requests
import logging
from openai import OpenAI, OpenAIError

_logger = logging.getLogger(__name__)
 
class PredictionAnalysisRegistration(models.Model):
    _name = 'prediction.analysis.registration'
    _description = 'Prediction Analysis Registration'
 
    name = fields.Char(string="Name", required=True)
    email = fields.Char(string="Email", required=True)
    contacts = fields.Char(string="Contacts")
    uuid = fields.Char(string="UUID", readonly=True)
    secret_key = fields.Char(string="Secret Key")
    status = fields.Selection([('active', 'Active'), ('deactivate', 'Deactivated')], string="Status", readonly=True)
    openai_api_key = fields.Char(string="OpenAI API Key")
 
    @api.model
    def default_get(self, fields_list):
        res = super(PredictionAnalysisRegistration, self).default_get(fields_list)
        user = self.env.user
        res.update({
            'name': user.name or '',
            'email': user.email or '',
            'contacts': user.partner_id.phone or '',
        })
        return res
 
    def create(self, vals):
        _logger = logging.getLogger(__name__)
        _logger.info("PredictionAnalysisRegistration CREATE called with: %s", vals)
 
        # Do not allow empty uuid and secret_key from FastAPI
        if not vals.get('uuid') or not vals.get('secret_key'):
            _logger.warning("Skipping creation because uuid or secret_key is missing: %s", vals)
            raise models.ValidationError("Cannot create registration without UUID and Secret Key.")
        return super(PredictionAnalysisRegistration, self).create(vals)
 
    def action_regenerate_uuid(self):
        for rec in self:
            payload = {
                "uuid": rec.uuid,
                "secret_key": rec.secret_key
            }
            try:
                response = requests.post("https://dashboat.sufalamtech.com/regenerate", json=payload)
                if response.status_code == 200:
                    data = response.json()
                    rec.uuid = data.get("new_uuid")
                    if data.get("status"):
                        rec.status = data.get("status")
                else:
                    raise Exception(response.text)
            except Exception as e:
                raise models.ValidationError(f"Failed to regenerate UUID: {e}")
 
    def action_update_status(self, status):
        for rec in self:
            payload = {
                "uuid": rec.uuid,
                "secret_key": rec.secret_key
            }
            try:
                response = requests.post(f"https://dashboat.sufalamtech.com/update_status?status={status}", json=payload)
                if response.status_code == 200:
                    data = response.json()
                    rec.status = data.get("status")
                else:
                    raise Exception(response.text)
            except Exception as e:
                raise models.ValidationError(f"Failed to update status: {e}")
 
    def validate_openai_api_key(self, api_key):
        """Validate OpenAI API key via lightweight API call."""
        _logger = logging.getLogger(__name__)
        if not api_key:
            raise models.ValidationError("Please provide an OpenAI API key.")
       
        try:
            client = OpenAI(api_key=api_key)
            # Simple test call to confirm key is valid
            client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5
            )
            _logger.info(f"[OK] OpenAI API key is valid: {api_key}")
            return True
        except OpenAIError as e:
            _logger.error(f"[ERROR] OpenAI API Key invalid: {str(e)}")
            raise models.ValidationError(f"Invalid OpenAI API key: {str(e)}")
 
    def action_validate_openai_api_key(self):
        for rec in self:
            if not rec.openai_api_key:
                raise models.ValidationError("Please provide an OpenAI API key.")
            
            # Validate the API key
            rec.validate_openai_api_key(rec.openai_api_key)
            
            # Load API key into memory cache for instant access (no database query needed!)
            user_email = rec.email or 'No email'
            try:
                # Store in PredictiveEngine class-level cache
                PredictiveEngine = self.env['predictive.engine']
                PredictiveEngine._api_key_cache[user_email] = rec.openai_api_key
                _logger.info(f"[MEMORY CACHE] Loaded OpenAI API key into memory for user: {user_email}")
            except Exception as e:
                _logger.warning(f"Failed to cache API key in memory: {e}")
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': 'OpenAI API key is valid and loaded into memory cache!',
                    'type': 'success',
                    'sticky': False,
                }
            }
 
 