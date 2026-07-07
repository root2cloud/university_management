import requests
import logging
 
def register_prediction_analysis(env):
    _logger = logging.getLogger(__name__)
 
    user = env['res.users'].sudo().search([
        ('login', 'not in', ['odoobot', 'admin']),
        ('active', '=', True)
    ], order='id', limit=1)
 
    if not user:
        _logger.warning("No suitable user found for registration during module install.")
        return
 
    payload = {
        "name": user.name or "",
        "email": user.email or "",
        "contacts": user.partner_id.phone or "",
        "status": "active"
    }
 
    _logger.info("Payload sent to FastAPI during module install: %s", payload)
 
    try:
        response = requests.post("https://dashboat.sufalamtech.com/register", json=payload)
        _logger.info("FastAPI response status: %s, body: %s", response.status_code, response.text)
        if response.status_code == 200:
            data = response.json()
            _logger.info("Data received from FastAPI: %s", data)
            existing = env['prediction.analysis.registration'].sudo().search([('email', '=', user.email)], limit=1)
            if not existing:
                env['prediction.analysis.registration'].sudo().create({
                    'name': user.name or "",
                    'email': user.email or "",
                    'contacts': user.partner_id.phone or "",
                    'uuid': data.get("uuid"),
                    'secret_key': data.get("secret_key"),
                    'status': data.get("status", "active"),
                })
    except Exception as e:
        _logger.error("Error connecting to registration server: %s", e)
 
def unregister_prediction_analysis(env):
    registrations = env['prediction.analysis.registration'].sudo().search([])
    for reg in registrations:
        payload = {
            "uuid": reg.uuid,
            "secret_key": reg.secret_key,
        }
        try:
            response = requests.post(
                "https://dashboat.sufalamtech.com/update_status?status=deactivate",
                json=payload,
                timeout=10,
            )
            if response.status_code != 200:
                logging.getLogger(__name__).warning(
                    "Failed to update status for uuid %s: %s", reg.uuid, response.text
                )
        except Exception as e:
            logging.getLogger(__name__).warning(
                "Exception updating status for uuid %s: %s", reg.uuid, e
            )
 
    env.cr.execute("""
        CREATE TABLE IF NOT EXISTS prediction_analysis_registration_backup (
            id SERIAL PRIMARY KEY,
            name VARCHAR,
            email VARCHAR,
            contacts VARCHAR,
            uuid VARCHAR,
            secret_key VARCHAR,
            status VARCHAR
        )
    """)
    env.cr.execute("""
        INSERT INTO prediction_analysis_registration_backup (name, email, contacts, uuid, secret_key, status)
        SELECT name, email, contacts, uuid, secret_key, status FROM prediction_analysis_registration
    """)
 
def reinstall_prediction_analysis(env):
    _logger = logging.getLogger(__name__)
 
    user = env['res.users'].sudo().search([
        ('login', 'not in', ['odoobot', 'admin']),
        ('active', '=', True)
    ], order='id', limit=1)
 
    if not user:
        _logger.warning("No suitable user found for reinstall during module install.")
        return
 
    env.cr.execute("""
        SELECT uuid, secret_key FROM prediction_analysis_registration_backup
        WHERE email=%s ORDER BY id DESC LIMIT 1
    """, (user.email,))
    row = env.cr.fetchone()
    uuid = secret_key = None
    if row:
        uuid, secret_key = row
 
    payload = {
        "name": user.name or "",
        "email": user.email or "",
        "contacts": user.partner_id.phone or "",
    }
    if uuid and secret_key:
        payload["uuid"] = uuid
        payload["secret_key"] = secret_key
 
    try:
        response = requests.post("https://dashboat.sufalamtech.com/reinstall", json=payload)
        _logger.info("FastAPI reinstall response: %s %s", response.status_code, response.text)
        if response.status_code == 200:
            data = response.json()
            existing = env['prediction.analysis.registration'].sudo().search([('email', '=', user.email)], limit=1)
            vals = {
                'name': user.name or "",
                'email': user.email or "",
                'contacts': user.partner_id.phone or "",
                'uuid': data.get("uuid"),
                'secret_key': data.get("secret_key"),
                'status': data.get("status", "active"),
            }
            if existing:
                existing.write(vals)
            else:
                env['prediction.analysis.registration'].sudo().create(vals)
    except Exception as e:
        _logger.error("Error connecting to reinstall server: %s", e)
 
def post_init_prediction_analysis(env):
    user = env['res.users'].sudo().search([
        ('login', 'not in', ['odoobot', 'admin']),
        ('active', '=', True)
    ], order='id', limit=1)
 
    if not user:
        logging.getLogger(__name__).warning("No suitable user found during module install/upgrade.")
        return
 
    env.cr.execute("""
        SELECT uuid, secret_key FROM prediction_analysis_registration_backup
        WHERE email=%s ORDER BY id DESC LIMIT 1
    """, (user.email,))
    row = env.cr.fetchone()
 
    if row and all(row):
        reinstall_prediction_analysis(env)
    else:
        register_prediction_analysis(env)
 