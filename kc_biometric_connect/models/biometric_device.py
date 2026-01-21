# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, date, timedelta, time
from collections import defaultdict
import logging
import base64
from io import BytesIO

_logger = logging.getLogger(__name__)

try:
    import xlsxwriter
    XLSXWRITER_AVAILABLE = True
except ImportError:
    XLSXWRITER_AVAILABLE = False
    _logger.warning("La librería 'xlsxwriter' no está instalada. Para exportar a Excel, instale con: pip install xlsxwriter")

try:
    from zk import ZK
    ZK_AVAILABLE = True
except ImportError:
    ZK_AVAILABLE = False
    _logger.warning("La librería 'zk' no está instalada. Instale con: pip install pyzk")

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    _logger.warning("La librería 'requests' no está instalada. Instale con: pip install requests")


class BiometricDevice(models.Model):
    _name = 'biometric.device'
    _description = 'Dispositivo Biométrico ZKTeco'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Nombre del Dispositivo',
        required=True,
        tracking=True
    )
    
    connection_type = fields.Selection([
        ('direct', 'Conexión Directa al Dispositivo'),
        ('server', 'Conexión al Servidor Biométrico')
    ], string='Tipo de Conexión', default='direct', required=True, tracking=True,
       help='Seleccione si se conecta directamente al dispositivo o a través de un servidor')
    
    ip_address = fields.Char(
        string='Dirección IP / Host',
        required=True,
        tracking=True,
        help='Dirección IP del dispositivo biométrico o servidor'
    )
    
    port = fields.Integer(
        string='Puerto',
        required=True,
        default=4370,
        tracking=True,
        help='Puerto de comunicación (4370 para dispositivo directo, 8082 para servidor)'
    )
    
    password = fields.Char(
        string='Contraseña del Dispositivo',
        required=False,
        tracking=True,
        help='Contraseña del dispositivo (solo para conexión directa)'
    )
    
    # Campos para conexión a servidor
    api_username = fields.Char(
        string='Usuario API',
        required=False,
        tracking=True,
        help='Usuario para autenticación en el servidor (solo para conexión a servidor)'
    )
    
    api_password = fields.Char(
        string='Contraseña API',
        required=False,
        tracking=True,
        help='Contraseña para autenticación en el servidor (solo para conexión a servidor)'
    )
    
    use_https = fields.Boolean(
        string='Usar HTTPS',
        default=False,
        tracking=True,
        help='Usar protocolo HTTPS para conexión al servidor'
    )
    
    auth_type = fields.Selection([
        ('jwt', 'JWT Token (jwt-api-token-auth)'),
        ('token', 'Token Básico (api-token-auth)'),
        ('staff_jwt', 'Staff JWT (staff-jwt-api-token-auth)'),
    ], string='Tipo de Autenticación', default='jwt', required=True,
       help='Tipo de autenticación según la API de BioTime')
    
    api_base_path = fields.Char(
        string='Ruta Base de API',
        default='',
        tracking=True,
        help='Ruta base de la API. Dejar vacío para usar rutas completas. BioTime usa /personnel para empleados y /iclock para dispositivos'
    )
    
    device_id = fields.Integer(
        string='ID del Dispositivo',
        default=1,
        help='ID interno del dispositivo'
    )
    
    is_active = fields.Boolean(
        string='Activo',
        default=True,
        tracking=True,
        help='Indica si el dispositivo está activo y se sincroniza'
    )
    
    last_sync = fields.Datetime(
        string='Última Sincronización',
        readonly=True,
        help='Fecha y hora de la última sincronización exitosa'
    )
    
    sync_status = fields.Selection([
        ('success', 'Exitoso'),
        ('error', 'Error'),
        ('never', 'Nunca sincronizado')
    ], string='Estado de Sincronización', default='never', readonly=True)
    
    sync_error_message = fields.Text(
        string='Mensaje de Error',
        readonly=True,
        help='Último mensaje de error en la sincronización'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        required=True
    )
    
    # Campos para configuración de sincronización
    auto_sync = fields.Boolean(
        string='Sincronización Automática',
        default=True,
        help='Activar sincronización automática mediante cron'
    )
    
    sync_interval = fields.Integer(
        string='Intervalo de Sincronización (minutos)',
        default=30,
        help='Intervalo en minutos para la sincronización automática'
    )
    
    # Relación con empleados
    employee_ids = fields.One2many(
        'hr.employee',
        'biometric_device_id',
        string='Empleados',
        readonly=True
    )
    
    employee_count = fields.Integer(
        string='Cantidad de Empleados',
        compute='_compute_employee_count',
        store=False
    )
    
    @api.depends('employee_ids')
    def _compute_employee_count(self):
        for device in self:
            device.employee_count = len(device.employee_ids)
    
    @api.onchange('connection_type')
    def _onchange_connection_type(self):
        """Ajustar puerto por defecto según el tipo de conexión"""
        if self.connection_type == 'server':
            if self.port == 4370:  # Solo cambiar si está en el valor por defecto
                self.port = 8082
        elif self.connection_type == 'direct':
            if self.port == 8082:  # Solo cambiar si está en el valor por defecto del servidor
                self.port = 4370
    
    def _get_server_base_url(self):
        """Obtener URL base del servidor"""
        self.ensure_one()
        protocol = 'https' if self.use_https else 'http'
        return f"{protocol}://{self.ip_address}:{self.port}"
    
    def _get_auth_endpoint(self):
        """Obtener endpoint de autenticación según el tipo seleccionado"""
        self.ensure_one()
        endpoints = {
            'jwt': '/jwt-api-token-auth/',
            'token': '/api-token-auth/',
            'staff_jwt': '/staff-jwt-api-token-auth/',
        }
        return endpoints.get(self.auth_type, '/jwt-api-token-auth/')
    
    def _server_authenticate(self):
        """
        Autenticar en el servidor BioTime y obtener token JWT
        
        Usa el endpoint /jwt-api-token-auth/ de BioTime API
        """
        self.ensure_one()
        if not REQUESTS_AVAILABLE:
            raise UserError(_('La librería requests no está instalada. Instale con: pip install requests'))
        
        base_url = self._get_server_base_url()
        # Endpoint de autenticación según tipo seleccionado
        auth_endpoint = self._get_auth_endpoint()
        auth_url = f"{base_url}{auth_endpoint}"
        
        try:
            _logger.info("Autenticando en BioTime: %s", auth_url)
            # Timeout más largo para conexiones VPN (30 segundos)
            response = requests.post(
                auth_url,
                json={
                    'username': self.api_username,
                    'password': self.api_password or ''
                },
                headers={'Content-Type': 'application/json'},
                timeout=30,  # Aumentado para conexiones VPN
                verify=False  # En producción, considerar certificados SSL
            )
            response.raise_for_status()
            
            # BioTime JWT retorna el token en formato JSON: {"token": "eyJ0eXAiOiJKV1QiLCJhbGc..."}
            try:
                data = response.json()
                _logger.debug("Respuesta de autenticación: %s", data)
                
                # BioTime JWT siempre retorna {"token": "..."}
                if isinstance(data, dict):
                    token = data.get('token')
                    if not token:
                        # Intentar otros campos comunes por si acaso
                        token = data.get('access_token') or data.get('access') or data.get('jwt_token')
                elif isinstance(data, str):
                    # Si retorna el token directamente como string
                    token = data.strip()
                else:
                    token = None
                    
            except ValueError as e:
                # Si no es JSON válido
                _logger.warning("Respuesta no es JSON válido: %s", response.text)
                # Intentar como texto plano
                token = response.text.strip() if response.text else None
            
            if not token:
                _logger.error("No se recibió token en la respuesta. Status: %s, Response: %s", 
                            response.status_code, response.text[:200])
                raise UserError(_('El servidor no retornó un token de autenticación. Verifique las credenciales y la configuración.'))
            
            _logger.info("Autenticación exitosa, token JWT obtenido (longitud: %d)", len(token))
            return token
        except requests.exceptions.HTTPError as e:
            error_detail = f"HTTP {e.response.status_code}"
            if e.response.text:
                try:
                    error_json = e.response.json()
                    error_detail += f": {error_json}"
                except:
                    error_detail += f": {e.response.text[:200]}"
            
            if e.response.status_code == 400 or e.response.status_code == 401:
                _logger.error("Error de autenticación (HTTP %s): %s - URL: %s", e.response.status_code, error_detail, auth_url)
                raise UserError(_('Error de autenticación:\n\n%s\n\nURL: %s\n\nVerifique:\n- Usuario API: %s\n- Contraseña API: (configurada)\n- Tipo de autenticación: %s\n- Que las credenciales sean correctas') % (error_detail, auth_url, self.api_username or 'No configurado', self.auth_type))
            else:
                _logger.error("Error HTTP al autenticar: %s - URL: %s", error_detail, auth_url)
                raise UserError(_('Error al autenticar en el servidor:\n\n%s\n\nURL: %s\n\nVerifique:\n- Que el endpoint de autenticación sea correcto\n- Que el servidor esté funcionando\n- Que el tipo de autenticación sea el correcto') % (error_detail, auth_url))
        except requests.exceptions.ConnectionError as e:
            # Errores específicos de conexión
            error_msg = str(e)
            if 'No route to host' in error_msg or 'errno 113' in error_msg.lower():
                error_detail = 'No se puede alcanzar el servidor. No hay ruta al host.'
                vpn_tips = f'''
                
⚠️ PROBLEMA DE CONECTIVIDAD VPN/RED:

El error "No route to host" indica que el VPS no puede alcanzar el servidor BioTime a través de la VPN.

🔍 DIAGNÓSTICO (ejecute estos comandos en el VPS):

1. Verificar conectividad básica:
   ping -c 4 {self.ip_address}

2. Verificar si el puerto está abierto:
   telnet {self.ip_address} {self.port}
   # O con nc (netcat):
   nc -zv {self.ip_address} {self.port}

3. Verificar rutas de red:
   ip route | grep {self.ip_address.split('.')[0]}.{self.ip_address.split('.')[1]}
   # O en Linux:
   route -n | grep {self.ip_address.split('.')[0]}.{self.ip_address.split('.')[1]}

4. Verificar interfaces de red VPN:
   ip addr show
   # Busque interfaces como tun0, tap0, ppp0, wg0, etc.

5. Verificar estado de la VPN:
   # Depende del tipo de VPN, ejemplos:
   # OpenVPN: systemctl status openvpn
   # WireGuard: wg show
   # StrongSwan: ipsec status

✅ SOLUCIONES COMUNES:

1. Verificar que la VPN esté conectada y activa
2. Confirmar que la VPN tenga acceso a la red 10.134.x.x (puede estar en otra subred)
3. Verificar reglas de firewall en el VPS:
   - iptables -L -n | grep {self.port}
   - ufw status (si usa UFW)
4. Verificar que el servidor BioTime permita conexiones desde la IP del VPS
5. Contactar al administrador de red para verificar:
   - Que la VPN tenga acceso a la subred 10.134.120.0/24
   - Que no haya ACLs bloqueando el tráfico
   - Que las rutas estén configuradas correctamente

📝 NOTA: Si funciona localmente pero no desde el VPS, el problema es de routing/firewall en el VPS o en la configuración de la VPN.'''
            elif 'Connection refused' in error_msg or 'errno 111' in error_msg.lower():
                error_detail = 'Conexión rechazada. El servidor puede estar apagado o el puerto incorrecto.'
                vpn_tips = f'''
                
⚠️ El servidor responde pero rechaza la conexión:
- Verifique que el puerto {self.port} sea correcto
- Verifique que el servicio BioTime esté corriendo en el servidor
- Verifique firewall en el servidor BioTime (puede estar bloqueando la IP del VPS)'''
            elif 'Name or service not known' in error_msg or 'errno -2' in error_msg.lower():
                error_detail = 'No se puede resolver el nombre del host. Verifique la IP o nombre del servidor.'
                vpn_tips = ''
            elif 'timed out' in error_msg.lower() or 'timeout' in error_msg.lower():
                error_detail = 'Tiempo de espera agotado. El servidor no responde.'
                vpn_tips = f'''
                
⚠️ Si está usando VPN:
- Las conexiones VPN pueden ser más lentas (timeout aumentado a 30 segundos)
- Verifique la latencia: ping -c 10 {self.ip_address}
- Verifique que no haya pérdida de paquetes
- Considere aumentar el timeout si la VPN es muy lenta'''
            else:
                error_detail = f'Error de conexión: {error_msg}'
                vpn_tips = f'''
                
⚠️ Error de conexión general:
- Verifique conectividad: ping {self.ip_address}
- Verifique puerto: telnet {self.ip_address} {self.port}
- Verifique firewall y rutas de red'''
            
            _logger.error("Error de conexión al autenticar en servidor: %s - URL: %s", error_msg, auth_url)
            raise UserError(_('Error de conexión al servidor:\n\n%s\n\nURL: %s\n\nVerifique:\n- Que el servidor esté encendido y accesible\n- Que la IP (%s) y puerto (%s) sean correctos\n- Que no haya firewall bloqueando la conexión\n- Que la red permita conexiones al puerto %s%s') % (error_detail, auth_url, self.ip_address, self.port, self.port, vpn_tips))
        except requests.exceptions.Timeout as e:
            _logger.error("Timeout al autenticar en servidor: %s - URL: %s", str(e), auth_url)
            raise UserError(_('Tiempo de espera agotado al conectar con el servidor:\n\nURL: %s\n\nVerifique:\n- Que el servidor esté respondiendo\n- Que la conexión de red sea estable\n- IP: %s\n- Puerto: %s') % (auth_url, self.ip_address, self.port))
        except requests.exceptions.RequestException as e:
            _logger.error("Error al autenticar en servidor: %s - URL: %s", str(e), auth_url)
            raise UserError(_('Error al autenticar en el servidor:\n\n%s\n\nURL: %s\n\nVerifique:\n- La conexión con el servidor\n- Que el servidor esté encendido\n- Que no haya firewall bloqueando\n- IP: %s\n- Puerto: %s') % (str(e), auth_url, self.ip_address, self.port))
    
    def _server_get_users(self, auth_token=None):
        """
        Obtener lista de empleados del servidor BioTime 8.5
        
        Según documentación BioTime 8.5 API:
        - Endpoint: GET /personnel/api/employees/
        - Parámetros opcionales: emp_code, page, page_size, first_name, last_name, department, app_status
        """
        self.ensure_one()
        base_url = self._get_server_base_url()
        # BioTime 8.5 usa /personnel/api/employees/ según documentación oficial
        users_url = f"{base_url}/personnel/api/employees/"
        
        headers = {'Content-Type': 'application/json'}
        if auth_token:
            # BioTime JWT usa formato "JWT {token}" para JWT, "Token {token}" para token básico
            if self.auth_type == 'jwt' or self.auth_type == 'staff_jwt':
                headers['Authorization'] = f'JWT {auth_token}'
            else:
                headers['Authorization'] = f'Token {auth_token}'
        
        try:
            # BioTime puede retornar resultados paginados, obtener todos
            all_employees = []
            page = 1
            page_size = 100  # Tamaño de página razonable
            
            while True:
                params = {'page': page, 'page_size': page_size}
                _logger.info("Solicitando empleados desde BioTime: %s (página %d)", users_url, page)
                response = requests.get(
                    users_url,
                    headers=headers,
                    params=params,
                    timeout=30,
                    verify=False
                )
                
                # Manejar errores HTTP con más detalle
                if response.status_code == 404:
                    _logger.error("Endpoint no encontrado (404): %s", users_url)
                    raise UserError(_('Endpoint no encontrado: %s\n\nVerifique:\n- Que la URL sea correcta\n- Que el servidor BioTime esté configurado correctamente\n- Endpoint esperado: /personnel/api/employees/') % users_url)
                elif response.status_code == 401:
                    _logger.error("No autorizado (401): Token inválido o expirado")
                    raise UserError(_('No autorizado: Token inválido o expirado. Verifique las credenciales API.'))
                elif response.status_code == 403:
                    _logger.error("Acceso prohibido (403): Sin permisos")
                    raise UserError(_('Acceso prohibido: El usuario API no tiene permisos para acceder a este endpoint.'))
                
                response.raise_for_status()
                data = response.json()
                
                # BioTime puede retornar lista directa o objeto con 'results'
                if isinstance(data, list):
                    all_employees.extend(data)
                    break  # Si es lista, no hay paginación
                elif isinstance(data, dict):
                    results = data.get('results', [])
                    all_employees.extend(results)
                    
                    # Verificar si hay más páginas
                    if not results or len(results) < page_size:
                        break
                    page += 1
                else:
                    all_employees = [data] if data else []
                    break
            
            _logger.info("Obtenidos %d empleados del servidor BioTime (página %d)", len(all_employees), page)
            # Asegurar que siempre retornamos una lista
            if all_employees:
                return all_employees
            elif isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return data.get('results', []) or data.get('data', []) or []
            else:
                _logger.warning("Formato inesperado de respuesta: %s (tipo: %s)", data, type(data))
                return []
        except requests.exceptions.HTTPError as e:
            error_detail = f"HTTP {e.response.status_code}"
            if e.response.text:
                try:
                    error_json = e.response.json()
                    error_detail += f": {error_json}"
                except:
                    error_detail += f": {e.response.text[:200]}"
            _logger.error("Error HTTP al obtener empleados: %s - URL: %s", error_detail, users_url)
            raise UserError(_('Error HTTP al obtener empleados del servidor:\n\n%s\n\nURL: %s\n\nVerifique:\n- Que el endpoint sea correcto\n- Que el servidor esté funcionando\n- Que tenga permisos de acceso') % (error_detail, users_url))
        except requests.exceptions.RequestException as e:
            _logger.error("Error al obtener usuarios del servidor: %s - URL: %s", str(e), users_url)
            raise UserError(_('Error al obtener usuarios del servidor:\n\n%s\n\nURL: %s\n\nVerifique:\n- La conexión con el servidor\n- Que el servidor esté encendido\n- Que no haya firewall bloqueando') % (str(e), users_url))
    
    def _server_get_departments(self, auth_token=None):
        """
        Obtener lista de departamentos del servidor BioTime 8.5
        
        Según documentación BioTime 8.5 API:
        - Endpoint: GET /personnel/api/departments/
        - Parámetros opcionales: dept_code, page, page_size, dept_name, parent_dept
        """
        self.ensure_one()
        base_url = self._get_server_base_url()
        dept_url = f"{base_url}/personnel/api/departments/"
        
        headers = {'Content-Type': 'application/json'}
        if auth_token:
            if self.auth_type == 'jwt' or self.auth_type == 'staff_jwt':
                headers['Authorization'] = f'JWT {auth_token}'
            else:
                headers['Authorization'] = f'Token {auth_token}'
        
        try:
            all_departments = []
            page = 1
            page_size = 100
            
            while True:
                params = {'page': page, 'page_size': page_size}
                response = requests.get(dept_url, headers=headers, params=params, timeout=30, verify=False)
                response.raise_for_status()
                data = response.json()
                
                if isinstance(data, list):
                    all_departments.extend(data)
                    break
                elif isinstance(data, dict):
                    results = data.get('results', [])
                    all_departments.extend(results)
                    if not results or len(results) < page_size:
                        break
                    page += 1
                else:
                    break
            
            return all_departments
        except Exception as e:
            _logger.error("Error al obtener departamentos: %s", str(e))
            raise UserError(_('Error al obtener departamentos: %s') % str(e))
    
    def _server_get_areas(self, auth_token=None):
        """
        Obtener lista de áreas del servidor BioTime 8.5
        
        Según documentación BioTime 8.5 API:
        - Endpoint: GET /personnel/api/areas/
        - Parámetros opcionales: area_code, page, page_size, area_name, parent_area
        """
        self.ensure_one()
        base_url = self._get_server_base_url()
        areas_url = f"{base_url}/personnel/api/areas/"
        
        headers = {'Content-Type': 'application/json'}
        if auth_token:
            if self.auth_type == 'jwt' or self.auth_type == 'staff_jwt':
                headers['Authorization'] = f'JWT {auth_token}'
            else:
                headers['Authorization'] = f'Token {auth_token}'
        
        try:
            all_areas = []
            page = 1
            page_size = 100
            
            while True:
                params = {'page': page, 'page_size': page_size}
                response = requests.get(areas_url, headers=headers, params=params, timeout=30, verify=False)
                response.raise_for_status()
                data = response.json()
                
                if isinstance(data, list):
                    all_areas.extend(data)
                    break
                elif isinstance(data, dict):
                    results = data.get('results', [])
                    all_areas.extend(results)
                    if not results or len(results) < page_size:
                        break
                    page += 1
                else:
                    break
            
            return all_areas
        except Exception as e:
            _logger.error("Error al obtener áreas: %s", str(e))
            raise UserError(_('Error al obtener áreas: %s') % str(e))
    
    def _server_create_employee(self, employee_data, auth_token=None):
        """
        Crear empleado en el servidor BioTime 8.5
        
        Endpoint: POST /personnel/api/employees/
        """
        self.ensure_one()
        base_url = self._get_server_base_url()
        create_url = f"{base_url}/personnel/api/employees/"
        
        headers = {'Content-Type': 'application/json'}
        if auth_token:
            if self.auth_type == 'jwt' or self.auth_type == 'staff_jwt':
                headers['Authorization'] = f'JWT {auth_token}'
            else:
                headers['Authorization'] = f'Token {auth_token}'
        
        try:
            response = requests.post(create_url, headers=headers, json=employee_data, timeout=30, verify=False)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            _logger.error("Error al crear empleado: %s", str(e))
            raise UserError(_('Error al crear empleado: %s') % str(e))
    
    def _server_update_employee(self, employee_id, employee_data, auth_token=None):
        """
        Actualizar empleado en el servidor BioTime 8.5
        
        Endpoint: PATCH /personnel/api/employees/<id>/
        """
        self.ensure_one()
        base_url = self._get_server_base_url()
        update_url = f"{base_url}/personnel/api/employees/{employee_id}/"
        
        headers = {'Content-Type': 'application/json'}
        if auth_token:
            if self.auth_type == 'jwt' or self.auth_type == 'staff_jwt':
                headers['Authorization'] = f'JWT {auth_token}'
            else:
                headers['Authorization'] = f'Token {auth_token}'
        
        try:
            response = requests.patch(update_url, headers=headers, json=employee_data, timeout=30, verify=False)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            _logger.error("Error al actualizar empleado: %s", str(e))
            raise UserError(_('Error al actualizar empleado: %s') % str(e))
    
    def _server_delete_employee(self, employee_id, auth_token=None):
        """
        Eliminar empleado en el servidor BioTime 8.5
        
        Endpoint: DELETE /personnel/api/employees/<id>/
        """
        self.ensure_one()
        base_url = self._get_server_base_url()
        delete_url = f"{base_url}/personnel/api/employees/{employee_id}/"
        
        headers = {'Content-Type': 'application/json'}
        if auth_token:
            if self.auth_type == 'jwt' or self.auth_type == 'staff_jwt':
                headers['Authorization'] = f'JWT {auth_token}'
            else:
                headers['Authorization'] = f'Token {auth_token}'
        
        try:
            response = requests.delete(delete_url, headers=headers, timeout=30, verify=False)
            response.raise_for_status()
            return True
        except Exception as e:
            _logger.error("Error al eliminar empleado: %s", str(e))
            raise UserError(_('Error al eliminar empleado: %s') % str(e))
    
    def _server_get_attendance(self, fecha_desde=None, fecha_hasta=None, auth_token=None):
        """
        Obtener registros de asistencia del servidor BioTime 8.5
        
        Según estructura de BioTime 8.5 API:
        - Endpoint: GET /iclock/api/transactions/
        - Transacciones de asistencia desde dispositivos
        """
        self.ensure_one()
        base_url = self._get_server_base_url()
        # BioTime 8.5 usa /iclock/api/transactions/ para registros de asistencia
        attendance_url = f"{base_url}/iclock/api/transactions/"
        
        headers = {'Content-Type': 'application/json'}
        if auth_token:
            # BioTime JWT usa formato "JWT {token}" para JWT, "Token {token}" para token básico
            if self.auth_type == 'jwt' or self.auth_type == 'staff_jwt':
                headers['Authorization'] = f'JWT {auth_token}'
            else:
                headers['Authorization'] = f'Token {auth_token}'
        
        params = {}
        # Parámetros según documentación de BioTime (ajustar según endpoint real)
        if fecha_desde:
            # Intentar diferentes formatos de parámetros comunes en BioTime
            params['start_date'] = fecha_desde.strftime('%Y-%m-%d')
            params['date_start'] = fecha_desde.strftime('%Y-%m-%d')
            params['startDate'] = fecha_desde.strftime('%Y-%m-%d')
        if fecha_hasta:
            params['end_date'] = fecha_hasta.strftime('%Y-%m-%d')
            params['date_end'] = fecha_hasta.strftime('%Y-%m-%d')
            params['endDate'] = fecha_hasta.strftime('%Y-%m-%d')
        
        try:
            # BioTime puede retornar resultados paginados, obtener todos
            all_transactions = []
            page = 1
            page_size = 100
            
            # Agregar paginación a los parámetros
            params['page'] = page
            params['page_size'] = page_size
            
            while True:
                params['page'] = page
                _logger.info("Solicitando transacciones desde BioTime: %s (página %d, fechas: %s a %s)", 
                            attendance_url, page, fecha_desde, fecha_hasta)
                response = requests.get(
                    attendance_url,
                    headers=headers,
                    params=params,
                    timeout=60,  # Timeout mayor para grandes volúmenes
                    verify=False
                )
                
                # Manejar errores HTTP con más detalle
                if response.status_code == 404:
                    _logger.error("Endpoint no encontrado (404): %s", attendance_url)
                    raise UserError(_('Endpoint no encontrado: %s\n\nVerifique:\n- Que la URL sea correcta\n- Que el servidor BioTime esté configurado correctamente\n- Endpoint esperado: /iclock/api/transactions/') % attendance_url)
                elif response.status_code == 401:
                    _logger.error("No autorizado (401): Token inválido o expirado")
                    raise UserError(_('No autorizado: Token inválido o expirado. Verifique las credenciales API.'))
                elif response.status_code == 403:
                    _logger.error("Acceso prohibido (403): Sin permisos")
                    raise UserError(_('Acceso prohibido: El usuario API no tiene permisos para acceder a este endpoint.'))
                
                response.raise_for_status()
                data = response.json()
                
                # BioTime puede retornar lista directa o objeto con 'results'
                if isinstance(data, list):
                    all_transactions.extend(data)
                    break
                elif isinstance(data, dict):
                    results = data.get('results', []) or data.get('data', []) or data.get('transactions', [])
                    all_transactions.extend(results)
                    
                    # Verificar si hay más páginas
                    if not results or len(results) < page_size:
                        break
                    page += 1
                else:
                    all_transactions = [data] if data else []
                    break
            
            _logger.info("Obtenidos %d transacciones del servidor BioTime (página %d)", len(all_transactions), page)
            return all_transactions if all_transactions else data
        except requests.exceptions.HTTPError as e:
            error_detail = f"HTTP {e.response.status_code}"
            if e.response.text:
                try:
                    error_json = e.response.json()
                    error_detail += f": {error_json}"
                except:
                    error_detail += f": {e.response.text[:200]}"
            _logger.error("Error HTTP al obtener transacciones: %s - URL: %s", error_detail, attendance_url)
            raise UserError(_('Error HTTP al obtener asistencias del servidor:\n\n%s\n\nURL: %s\n\nVerifique:\n- Que el endpoint sea correcto\n- Que el servidor esté funcionando\n- Que tenga permisos de acceso') % (error_detail, attendance_url))
        except requests.exceptions.RequestException as e:
            _logger.error("Error al obtener asistencias del servidor: %s - URL: %s", str(e), attendance_url)
            raise UserError(_('Error al obtener asistencias del servidor:\n\n%s\n\nURL: %s\n\nVerifique:\n- La conexión con el servidor\n- Que el servidor esté encendido\n- Que no haya firewall bloqueando') % (str(e), attendance_url))
    
    def action_view_employees(self):
        """Abrir vista de empleados relacionados con este dispositivo"""
        self.ensure_one()
        return {
            'name': _('Empleados'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee',
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [('biometric_device_id', '=', self.id)],
            'context': {'default_biometric_device_id': self.id},
        }
    
    @api.constrains('ip_address', 'port', 'connection_type')
    def _check_connection_params(self):
        for device in self:
            if device.port < 1 or device.port > 65535:
                raise ValidationError(_('El puerto debe estar entre 1 y 65535'))
            if device.connection_type == 'server' and not device.api_username:
                raise ValidationError(_('Para conexión a servidor, debe especificar un Usuario API'))
    
    def test_connection(self):
        """Probar la conexión con el dispositivo biométrico o servidor"""
        self.ensure_one()
        
        if not self.ip_address:
            raise UserError(_('Debe especificar una dirección IP o host'))
        
        if self.connection_type == 'server':
            return self._test_server_connection()
        else:
            return self._test_direct_connection()
    
    def _test_direct_connection(self):
        """Probar conexión directa al dispositivo"""
        self.ensure_one()
        if not ZK_AVAILABLE:
            raise UserError(_('La librería zk no está instalada. Instale con: pip install pyzk'))
        
        conn = None
        try:
            _logger.info("Intentando conectar a dispositivo biométrico: %s:%s", self.ip_address, self.port)
            
            # Crear instancia ZK con parámetros
            zk_params = {
                'ip': self.ip_address,
                'port': self.port,
                'timeout': 10,
            }
            
            # Agregar contraseña si está configurada
            if self.password:
                zk_params['password'] = self.password
                _logger.info("Usando contraseña para conexión")
            
            zk = ZK(**zk_params)
            _logger.info("Iniciando conexión...")
            conn = zk.connect()
            
            if not conn:
                raise UserError(_('No se pudo establecer la conexión con el dispositivo. Verifique IP, puerto y que el dispositivo esté encendido.'))
            
            _logger.info("Conexión establecida exitosamente")
            
            # Probar obtener información del dispositivo
            _logger.info("Deshabilitando dispositivo para obtener datos...")
            conn.disable_device()
            
            _logger.info("Obteniendo lista de usuarios...")
            users = conn.get_users()
            _logger.info("Se encontraron %d usuarios", len(users))
            
            _logger.info("Habilitando dispositivo...")
            conn.enable_device()
            
            _logger.info("Desconectando...")
            conn.disconnect()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Conexión Exitosa'),
                    'message': _('La conexión con el dispositivo se estableció correctamente. Se encontraron %d usuarios.') % len(users),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            error_msg = str(e)
            _logger.error("Error al conectar con dispositivo biométrico %s:%s - %s", 
                         self.ip_address, self.port, error_msg, exc_info=True)
            
            # Mensaje de error más descriptivo
            if 'timeout' in error_msg.lower() or 'timed out' in error_msg.lower():
                raise UserError(_('Timeout al conectar. Verifique que:\n- El dispositivo esté encendido\n- La IP sea correcta (%s)\n- No haya firewall bloqueando\n- El dispositivo esté en la misma red') % self.ip_address)
            elif 'connection refused' in error_msg.lower() or 'no route to host' in error_msg.lower():
                raise UserError(_('No se puede alcanzar el dispositivo en %s:%s. Verifique la IP y que el dispositivo esté encendido.') % (self.ip_address, self.port))
            else:
                raise UserError(_('Error al conectar con el dispositivo: %s\n\nVerifique:\n- IP: %s\n- Puerto: %s\n- Que el dispositivo esté encendido\n- Que no haya firewall bloqueando') % (error_msg, self.ip_address, self.port))
        finally:
            # Asegurar desconexión en caso de error
            if conn:
                try:
                    conn.disconnect()
                except:
                    pass
    
    def _test_server_connection(self):
        """Probar conexión al servidor biométrico"""
        self.ensure_one()
        if not REQUESTS_AVAILABLE:
            raise UserError(_('La librería requests no está instalada. Instale con: pip install requests'))
        
        try:
            _logger.info("Intentando conectar al servidor biométrico: %s:%s", self.ip_address, self.port)
            
            # Autenticar en el servidor
            auth_token = self._server_authenticate()
            _logger.info("Autenticación exitosa en el servidor")
            
            # Obtener usuarios para verificar conexión
            users_data = self._server_get_users(auth_token)
            users_count = len(users_data) if isinstance(users_data, list) else users_data.get('count', 0)
            _logger.info("Se encontraron %d usuarios en el servidor", users_count)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Conexión Exitosa'),
                    'message': _('La conexión con el servidor se estableció correctamente. Se encontraron %d usuarios.') % users_count,
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            error_msg = str(e)
            _logger.error("Error al conectar con servidor biométrico %s:%s - %s", 
                         self.ip_address, self.port, error_msg, exc_info=True)
            
            if 'timeout' in error_msg.lower() or 'timed out' in error_msg.lower():
                raise UserError(_('Timeout al conectar al servidor. Verifique que:\n- El servidor esté encendido\n- La IP/host sea correcta (%s)\n- El puerto sea correcto (%s)\n- No haya firewall bloqueando') % (self.ip_address, self.port))
            elif 'connection refused' in error_msg.lower() or 'no route to host' in error_msg.lower():
                raise UserError(_('No se puede alcanzar el servidor en %s:%s. Verifique la IP/host y que el servidor esté encendido.') % (self.ip_address, self.port))
            else:
                raise UserError(_('Error al conectar con el servidor: %s\n\nVerifique:\n- IP/Host: %s\n- Puerto: %s\n- Usuario API: %s\n- Que el servidor esté encendido\n- Que no haya firewall bloqueando') % (error_msg, self.ip_address, self.port, self.api_username or 'No configurado'))
    
    def sync_attendance_all(self):
        """Sincronizar todos los registros disponibles del dispositivo (últimos 90 días)"""
        self.ensure_one()
        fecha_desde = date.today() - timedelta(days=90)
        return self.sync_attendance(fecha_desde=fecha_desde, fecha_hasta=date.today())
    
    def action_open_sync_wizard(self):
        """Abrir wizard de sincronización con filtros"""
        self.ensure_one()
        return {
            'name': _('Sincronizar Asistencias'),
            'type': 'ir.actions.act_window',
            'res_model': 'biometric.sync.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_device_id': self.id,
                'default_sync_mode': 'new',
            }
        }
    
    def sync_attendance(self, fecha_desde=None, fecha_hasta=None):
        """
        Sincronizar registros de asistencia desde el dispositivo o servidor
        
        Args:
            fecha_desde: Fecha desde la cual sincronizar (opcional, por defecto última sincronización)
            fecha_hasta: Fecha hasta la cual sincronizar (opcional, por defecto hoy)
        """
        self.ensure_one()
        
        if self.connection_type == 'server':
            return self._sync_attendance_from_server(fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)
        else:
            return self._sync_attendance_from_device(fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)
    
    def _sync_attendance_from_device(self, fecha_desde=None, fecha_hasta=None):
        """
        Sincronizar registros de asistencia desde el dispositivo directamente
        
        Args:
            fecha_desde: Fecha desde la cual sincronizar (opcional, por defecto última sincronización)
            fecha_hasta: Fecha hasta la cual sincronizar (opcional, por defecto hoy)
        """
        self.ensure_one()
        
        if not ZK_AVAILABLE:
            raise UserError(_('La librería zk no está instalada. Instale con: pip install pyzk'))
        
        conn = None
        try:
            _logger.info("Iniciando sincronización para dispositivo %s (%s:%s)", self.name, self.ip_address, self.port)
            
            # Crear instancia ZK con parámetros
            zk_params = {
                'ip': self.ip_address,
                'port': self.port,
                'timeout': 10,
            }
            
            # Agregar contraseña si está configurada
            if self.password:
                zk_params['password'] = self.password
            
            zk = ZK(**zk_params)
            conn = zk.connect()
            
            if not conn:
                raise UserError(_('No se pudo establecer la conexión con el dispositivo'))
            
            _logger.info("Conexión establecida, obteniendo datos...")
            
            # Deshabilitar dispositivo para obtener datos
            conn.disable_device()
            
            # Obtener asistencias y usuarios
            _logger.info("Obteniendo registros de asistencia...")
            attendances = conn.get_attendance()
            _logger.info("Se obtuvieron %d registros de asistencia", len(attendances))
            
            _logger.info("Obteniendo lista de usuarios...")
            users = conn.get_users()
            _logger.info("Se obtuvieron %d usuarios", len(users))
            
            # Habilitar dispositivo nuevamente
            conn.enable_device()
            conn.disconnect()
            conn = None
            
            # Crear mapa de usuarios (user_id -> nombre)
            user_map = {u.user_id: u.name for u in users}
            
            # Determinar rango de fechas
            if not fecha_desde:
                # Si hay última sincronización, usar esa fecha, sino usar hace 30 días
                if self.last_sync:
                    fecha_desde = self.last_sync.date()
                else:
                    fecha_desde = date.today() - timedelta(days=30)
            
            if not fecha_hasta:
                fecha_hasta = date.today()
            
            # Procesar asistencias agrupadas por usuario y fecha
            # Guardar objetos completos de asistencia para obtener status y verify_mode
            por_usuario = defaultdict(lambda: defaultdict(list))
            
            total_attendances = len(attendances)
            filtered_count = 0
            
            for att in attendances:
                fecha_att = att.timestamp.date()
                # Filtrar por rango de fechas
                if fecha_desde <= fecha_att <= fecha_hasta:
                    por_usuario[att.user_id][fecha_att].append(att)
                    filtered_count += 1
            
            _logger.info(
                "Total de registros obtenidos del dispositivo: %d, Registros en rango de fechas (%s a %s): %d",
                total_attendances, fecha_desde, fecha_hasta, filtered_count
            )
            
            if filtered_count == 0:
                _logger.warning(
                    "No hay registros en el rango de fechas seleccionado. Última sincronización: %s, Rango: %s a %s. "
                    "Todos los %d registros del dispositivo están fuera del rango.",
                    self.last_sync, fecha_desde, fecha_hasta, total_attendances
                )
            
            # Crear registros en biometric.attendance y hr.attendance
            biometric_records_created = 0
            attendance_records_created = 0
            employees_not_found = []
            existing_records_skipped = 0
            
            for user_id, fechas in por_usuario.items():
                for fecha, att_list in fechas.items():
                    if not att_list:
                        continue
                    
                    # Ordenar por timestamp
                    att_list_sorted = sorted(att_list, key=lambda x: x.timestamp)
                    entrada_att = att_list_sorted[0]
                    salida_att = att_list_sorted[-1] if len(att_list_sorted) > 1 else None
                    
                    entrada = entrada_att.timestamp
                    # Solo crear salida si hay más de un registro y son diferentes
                    salida = salida_att.timestamp if (salida_att and len(att_list_sorted) > 1 and salida_att != entrada_att) else None
                    
                    # Buscar empleado por ID biométrico
                    employee = self.env['hr.employee'].search([
                        ('biometric_user_id', '=', user_id),
                        ('biometric_sync_active', '=', True)
                    ], limit=1)
                    
                    if not employee:
                        if user_id not in employees_not_found:
                            employees_not_found.append(user_id)
                            _logger.warning("No se encontró empleado con ID biométrico %s (Usuario: %s)", user_id, user_map.get(user_id, 'Desconocido'))
                        continue
                    
                    # Verificar si ya existe un registro biométrico para esta fecha y hora
                    existing_biometric = self.env['biometric.attendance'].search([
                        ('device_id', '=', self.id),
                        ('employee_biometric_id', '=', user_id),
                        ('punch_time', '=', entrada),
                        ('punch_state', '=', 'check_in')
                    ], limit=1)
                    
                    if existing_biometric:
                        existing_records_skipped += 1
                        _logger.debug("Registro ya existe para empleado %s, fecha %s, hora %s", employee.name, fecha, entrada)
                        continue
                    
                    # Obtener status y verify_mode del objeto de asistencia
                    status_entrada = getattr(entrada_att, 'status', 0)
                    verify_mode_entrada = getattr(entrada_att, 'punch', 0)  # punch es el verify_mode en zk
                    
                    # Crear registro de entrada
                    biometric_attendance_in = self.env['biometric.attendance'].create({
                        'device_id': self.id,
                        'employee_biometric_id': user_id,
                        'employee_id': employee.id,
                        'punch_time': entrada,
                        'punch_state': 'check_in',
                        'status': status_entrada,
                        'verify_mode': verify_mode_entrada,
                    })
                    biometric_records_created += 1
                    
                    # Crear registro de asistencia en hr.attendance desde el biométrico
                    attendance = biometric_attendance_in.create_attendance_record()
                    if attendance:
                        attendance_records_created += 1
                        _logger.info(
                            "Registro de asistencia creado para %s - Check_in: %s%s",
                            employee.name,
                            entrada.strftime('%Y-%m-%d %H:%M:%S'),
                            f", Check_out: {salida.strftime('%Y-%m-%d %H:%M:%S')}" if salida else ""
                        )
                    
                    # Si hay salida y es diferente a la entrada, crear registro de salida
                    if salida and salida != entrada:
                        status_salida = getattr(salida_att, 'status', 0)
                        verify_mode_salida = getattr(salida_att, 'punch', 0)
                        
                        biometric_attendance_out = self.env['biometric.attendance'].create({
                            'device_id': self.id,
                            'employee_biometric_id': user_id,
                            'employee_id': employee.id,
                            'punch_time': salida,
                            'punch_state': 'check_out',
                            'status': status_salida,
                            'verify_mode': verify_mode_salida,
                        })
                        biometric_records_created += 1
                        
                        # Actualizar el registro de asistencia con la salida
                        if attendance:
                            attendance.write({
                                'check_out': salida,
                                'biometric_punch_time': salida,
                            })
                            biometric_attendance_out.write({
                                'attendance_id': attendance.id,
                                'is_synced': True,
                                'sync_date': fields.Datetime.now(),
                            })
            
            # Actualizar estado de sincronización
            self.write({
                'last_sync': fields.Datetime.now(),
                'sync_status': 'success',
                'sync_error_message': False
            })
            
            _logger.info(
                "Sincronización completada: %d registros biométricos procesados, %d registros de asistencia creados en hr.attendance. "
                "Total registros del dispositivo: %d, En rango de fechas: %d, Empleados no encontrados: %d, Registros ya existentes: %d",
                biometric_records_created, attendance_records_created, total_attendances, filtered_count,
                len(employees_not_found), existing_records_skipped
            )
            
            # Construir mensaje detallado
            message_parts = [
                _('Sincronización completada:'),
                _('• %d registros biométricos creados') % biometric_records_created,
                _('• %d registros de asistencia creados') % attendance_records_created,
            ]
            
            if total_attendances > 0:
                message_parts.append(_('• %d registros encontrados en el dispositivo') % total_attendances)
            
            if len(employees_not_found) > 0:
                message_parts.append(_('• %d usuarios sin empleado configurado') % len(employees_not_found))
            
            if existing_records_skipped > 0:
                message_parts.append(_('• %d registros ya existían (omitidos)') % existing_records_skipped)
            
            if filtered_count < total_attendances and self.last_sync:
                message_parts.append(_('\n⚠️ Nota: Se sincronizaron solo registros desde la última sincronización (%s). '
                                     '%d registros están fuera del rango y no se procesaron.') % (
                                         self.last_sync.strftime('%Y-%m-%d %H:%M:%S'),
                                         total_attendances - filtered_count
                                     ))
            
            message_parts.append(_('\nLos registros de asistencia están disponibles en: Recursos Humanos > Asistencia'))
            
            message = '\n'.join(message_parts)
            
            # Si no se crearon registros pero hay registros en el dispositivo, mostrar advertencia
            if attendance_records_created == 0 and total_attendances > 0:
                warning_msg = _('No se crearon registros de asistencia. Posibles razones:\n')
                if filtered_count == 0:
                    warning_msg += _('• Todos los registros están fuera del rango de fechas (última sincronización: %s)\n') % (self.last_sync.strftime('%Y-%m-%d %H:%M:%S') if self.last_sync else _('Nunca'))
                if len(employees_not_found) > 0:
                    warning_msg += _('• %d usuarios no tienen empleado configurado con ID biométrico\n') % len(employees_not_found)
                if existing_records_skipped > 0:
                    warning_msg += _('• %d registros ya existen y fueron omitidos\n') % existing_records_skipped
                
                _logger.warning(warning_msg)
                message = warning_msg + '\n' + message
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sincronización Exitosa'),
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            error_msg = str(e)
            _logger.error("Error al sincronizar asistencia para dispositivo %s: %s", 
                         self.name, error_msg, exc_info=True)
            self.write({
                'sync_status': 'error',
                'sync_error_message': error_msg
            })
            
            # Mensaje de error más descriptivo
            if 'timeout' in error_msg.lower():
                raise UserError(_('Timeout al sincronizar. Verifique la conexión con el dispositivo %s:%s') % (self.ip_address, self.port))
            else:
                raise UserError(_('Error al sincronizar asistencia: %s') % error_msg)
        finally:
            # Asegurar desconexión en caso de error
            if conn:
                try:
                    conn.disconnect()
                except:
                    pass
    
    def _sync_attendance_from_server(self, fecha_desde=None, fecha_hasta=None):
        """
        Sincronizar registros de asistencia desde el servidor biométrico
        
        Args:
            fecha_desde: Fecha desde la cual sincronizar (opcional, por defecto última sincronización)
            fecha_hasta: Fecha hasta la cual sincronizar (opcional, por defecto hoy)
        """
        self.ensure_one()
        
        if not REQUESTS_AVAILABLE:
            raise UserError(_('La librería requests no está instalada. Instale con: pip install requests'))
        
        try:
            _logger.info("Iniciando sincronización desde servidor para dispositivo %s (%s:%s)", 
                        self.name, self.ip_address, self.port)
            
            # Autenticar en el servidor
            auth_token = self._server_authenticate()
            _logger.info("Autenticación exitosa en el servidor")
            
            # Obtener usuarios y asistencias del servidor
            _logger.info("Obteniendo lista de usuarios del servidor...")
            users_data = self._server_get_users(auth_token)
            
            # Convertir empleados de BioTime a formato estándar
            # BioTime retorna: {id, emp_code, first_name, last_name, department, ...}
            if isinstance(users_data, list):
                employees_list = users_data
            else:
                # Si viene como objeto con lista (paginación o wrapper)
                employees_list = users_data.get('results', []) or users_data.get('data', []) or users_data.get('employees', [])
                if not employees_list and isinstance(users_data, dict):
                    # Si es un solo empleado o estructura diferente
                    employees_list = [users_data] if users_data.get('id') else []
            
            # Crear mapa: id -> nombre completo
            # BioTime usa 'id' como identificador principal, 'emp_code' como código de empleado
            user_map = {}
            for emp in employees_list:
                emp_id = emp.get('id') or emp.get('emp_code')
                if emp_id:
                    # Construir nombre completo
                    first_name = emp.get('first_name', '')
                    last_name = emp.get('last_name', '')
                    full_name = f"{first_name} {last_name}".strip() or emp.get('emp_code', '')
                    user_map[emp_id] = full_name
            
            _logger.info("Se obtuvieron %d empleados del servidor BioTime", len(user_map))
            
            # Determinar rango de fechas
            if not fecha_desde:
                if self.last_sync:
                    fecha_desde = self.last_sync.date()
                else:
                    fecha_desde = date.today() - timedelta(days=30)
            
            if not fecha_hasta:
                fecha_hasta = date.today()
            
            # Obtener asistencias del servidor
            _logger.info("Obteniendo registros de asistencia del servidor...")
            attendance_data = self._server_get_attendance(
                fecha_desde=fecha_desde,
                fecha_hasta=fecha_hasta,
                auth_token=auth_token
            )
            
            # Convertir asistencias a formato estándar
            if isinstance(attendance_data, list):
                attendances_list = attendance_data
            else:
                attendances_list = attendance_data.get('attendances', []) or attendance_data.get('data', [])
            
            _logger.info("Se obtuvieron %d registros de asistencia del servidor", len(attendances_list))
            
            # Procesar asistencias agrupadas por usuario y fecha
            por_usuario = defaultdict(lambda: defaultdict(list))
            
            total_attendances = len(attendances_list)
            filtered_count = 0
            
            for att_data in attendances_list:
                # BioTime transactions probablemente tiene: employee, punch_time, device, etc.
                # Intentar diferentes campos comunes en BioTime
                user_id = (att_data.get('employee') or att_data.get('employee_id') or 
                          att_data.get('emp_code') or att_data.get('emp_id') or
                          att_data.get('userId') or att_data.get('user_id'))
                
                # Si employee es un objeto, extraer el ID
                if isinstance(user_id, dict):
                    user_id = user_id.get('id') or user_id.get('emp_code')
                
                timestamp_str = (att_data.get('punch_time') or att_data.get('punchTime') or 
                               att_data.get('timestamp') or att_data.get('date_time') or
                               att_data.get('dateTime') or att_data.get('time'))
                
                if not user_id or not timestamp_str:
                    continue
                
                # Convertir timestamp a datetime
                try:
                    if isinstance(timestamp_str, str):
                        # Intentar diferentes formatos de fecha
                        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S.%f']:
                            try:
                                timestamp = datetime.strptime(timestamp_str, fmt)
                                break
                            except ValueError:
                                continue
                        else:
                            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    else:
                        timestamp = timestamp_str
                except Exception as e:
                    _logger.warning("Error al parsear timestamp %s: %s", timestamp_str, str(e))
                    continue
                
                fecha_att = timestamp.date()
                if fecha_desde <= fecha_att <= fecha_hasta:
                    # Crear objeto similar al de pyzk para mantener compatibilidad
                    class AttendanceRecord:
                        def __init__(self, user_id, timestamp, status=0, punch=0):
                            self.user_id = user_id
                            self.timestamp = timestamp
                            self.status = status
                            self.punch = punch
                    
                    att_record = AttendanceRecord(
                        user_id=user_id,
                        timestamp=timestamp,
                        status=att_data.get('status', 0),
                        punch=att_data.get('verifyMode', 0) or att_data.get('punch', 0)
                    )
                    por_usuario[user_id][fecha_att].append(att_record)
                    filtered_count += 1
            
            _logger.info(
                "Total de registros obtenidos del servidor: %d, Registros en rango de fechas (%s a %s): %d",
                total_attendances, fecha_desde, fecha_hasta, filtered_count
            )
            
            if filtered_count == 0:
                _logger.warning(
                    "No hay registros en el rango de fechas seleccionado. Última sincronización: %s, Rango: %s a %s. "
                    "Todos los %d registros del servidor están fuera del rango.",
                    self.last_sync, fecha_desde, fecha_hasta, total_attendances
                )
            
            # Procesar asistencias (código similar al método directo)
            biometric_records_created = 0
            attendance_records_created = 0
            employees_not_found = []
            existing_records_skipped = 0
            
            for user_id, fechas in por_usuario.items():
                for fecha, att_list in fechas.items():
                    if not att_list:
                        continue
                    
                    # Ordenar por timestamp
                    att_list_sorted = sorted(att_list, key=lambda x: x.timestamp)
                    entrada_att = att_list_sorted[0]
                    salida_att = att_list_sorted[-1] if len(att_list_sorted) > 1 else None
                    
                    entrada = entrada_att.timestamp
                    salida = salida_att.timestamp if (salida_att and len(att_list_sorted) > 1 and salida_att != entrada_att) else None
                    
                    # Buscar empleado por ID biométrico
                    employee = self.env['hr.employee'].search([
                        ('biometric_user_id', '=', str(user_id)),
                        ('biometric_sync_active', '=', True)
                    ], limit=1)
                    
                    if not employee:
                        if user_id not in employees_not_found:
                            employees_not_found.append(user_id)
                            _logger.warning("No se encontró empleado con ID biométrico %s (Usuario: %s)", 
                                          user_id, user_map.get(user_id, 'Desconocido'))
                        continue
                    
                    # Verificar si ya existe un registro biométrico
                    existing_biometric = self.env['biometric.attendance'].search([
                        ('device_id', '=', self.id),
                        ('employee_biometric_id', '=', str(user_id)),
                        ('punch_time', '=', entrada),
                        ('punch_state', '=', 'check_in')
                    ], limit=1)
                    
                    if existing_biometric:
                        existing_records_skipped += 1
                        _logger.debug("Registro ya existe para empleado %s, fecha %s, hora %s", 
                                    employee.name, fecha, entrada)
                        continue
                    
                    # Obtener status y verify_mode
                    status_entrada = getattr(entrada_att, 'status', 0)
                    verify_mode_entrada = getattr(entrada_att, 'punch', 0)
                    
                    # Crear registro de entrada
                    biometric_attendance_in = self.env['biometric.attendance'].create({
                        'device_id': self.id,
                        'employee_biometric_id': str(user_id),
                        'employee_id': employee.id,
                        'punch_time': entrada,
                        'punch_state': 'check_in',
                        'status': status_entrada,
                        'verify_mode': verify_mode_entrada,
                    })
                    biometric_records_created += 1
                    
                    # Crear registro de asistencia
                    attendance = biometric_attendance_in.create_attendance_record()
                    if attendance:
                        attendance_records_created += 1
                        _logger.info(
                            "Registro de asistencia creado para %s - Check_in: %s%s",
                            employee.name,
                            entrada.strftime('%Y-%m-%d %H:%M:%S'),
                            f", Check_out: {salida.strftime('%Y-%m-%d %H:%M:%S')}" if salida else ""
                        )
                    
                    # Si hay salida
                    if salida and salida != entrada:
                        status_salida = getattr(salida_att, 'status', 0)
                        verify_mode_salida = getattr(salida_att, 'punch', 0)
                        
                        biometric_attendance_out = self.env['biometric.attendance'].create({
                            'device_id': self.id,
                            'employee_biometric_id': str(user_id),
                            'employee_id': employee.id,
                            'punch_time': salida,
                            'punch_state': 'check_out',
                            'status': status_salida,
                            'verify_mode': verify_mode_salida,
                        })
                        biometric_records_created += 1
                        
                        if attendance:
                            attendance.write({
                                'check_out': salida,
                                'biometric_punch_time': salida,
                            })
                            biometric_attendance_out.write({
                                'attendance_id': attendance.id,
                                'is_synced': True,
                                'sync_date': fields.Datetime.now(),
                            })
            
            # Actualizar estado de sincronización
            self.write({
                'last_sync': fields.Datetime.now(),
                'sync_status': 'success',
                'sync_error_message': False
            })
            
            _logger.info(
                "Sincronización completada: %d registros biométricos procesados, %d registros de asistencia creados. "
                "Total registros del servidor: %d, En rango de fechas: %d, Empleados no encontrados: %d, Registros ya existentes: %d",
                biometric_records_created, attendance_records_created, total_attendances, filtered_count,
                len(employees_not_found), existing_records_skipped
            )
            
            # Construir mensaje
            message_parts = [
                _('Sincronización completada:'),
                _('• %d registros biométricos creados') % biometric_records_created,
                _('• %d registros de asistencia creados') % attendance_records_created,
            ]
            
            if total_attendances > 0:
                message_parts.append(_('• %d registros encontrados en el servidor') % total_attendances)
            
            if len(employees_not_found) > 0:
                message_parts.append(_('• %d usuarios sin empleado configurado') % len(employees_not_found))
            
            if existing_records_skipped > 0:
                message_parts.append(_('• %d registros ya existían (omitidos)') % existing_records_skipped)
            
            message_parts.append(_('\nLos registros de asistencia están disponibles en: Recursos Humanos > Asistencia'))
            
            message = '\n'.join(message_parts)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sincronización Exitosa'),
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            error_msg = str(e)
            _logger.error("Error al sincronizar asistencia desde servidor para dispositivo %s: %s", 
                         self.name, error_msg, exc_info=True)
            self.write({
                'sync_status': 'error',
                'sync_error_message': error_msg
            })
            
            if 'timeout' in error_msg.lower():
                raise UserError(_('Timeout al sincronizar. Verifique la conexión con el servidor %s:%s') % (self.ip_address, self.port))
            else:
                raise UserError(_('Error al sincronizar asistencia desde servidor: %s') % error_msg)
    
    
    def export_attendance(self, fecha_desde=None, fecha_hasta=None):
        """Exportar registros de asistencia a Excel"""
        self.ensure_one()
        
        if not XLSXWRITER_AVAILABLE:
            raise UserError(_('La librería xlsxwriter no está instalada. Instale con: pip install xlsxwriter'))
        
        # Determinar rango de fechas
        if not fecha_desde:
            fecha_desde = date.today() - timedelta(days=30)
        if not fecha_hasta:
            fecha_hasta = date.today()
        
        # Obtener registros de asistencia biométrica relacionados con este dispositivo
        fecha_desde_dt = datetime.combine(fecha_desde, time.min) if isinstance(fecha_desde, date) else fecha_desde
        fecha_hasta_dt = datetime.combine(fecha_hasta, time.max) if isinstance(fecha_hasta, date) else fecha_hasta
        
        domain = [
            ('biometric_device_id', '=', self.id),
            ('check_in', '>=', fecha_desde_dt),
            ('check_in', '<=', fecha_hasta_dt),
        ]
        
        attendances = self.env['hr.attendance'].search(domain, order='check_in desc')
        
        if not attendances:
            raise UserError(_('No se encontraron registros de asistencia para el período seleccionado.'))
        
        # Crear archivo Excel en memoria
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Asistencias')
        
        # Formatos
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#366092',
            'font_color': 'white',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        
        date_format = workbook.add_format({
            'num_format': 'dd/mm/yyyy hh:mm:ss',
            'border': 1
        })
        
        text_format = workbook.add_format({
            'border': 1
        })
        
        center_format = workbook.add_format({
            'align': 'center',
            'border': 1
        })
        
        # Encabezados
        headers = [
            'Empleado',
            'Fecha Entrada',
            'Hora Entrada',
            'Fecha Salida',
            'Hora Salida',
            'Horas Trabajadas',
            'Dispositivo',
            'Registro Biométrico'
        ]
        
        # Escribir encabezados
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)
        
        # Ancho de columnas
        worksheet.set_column(0, 0, 30)  # Empleado
        worksheet.set_column(1, 1, 18)  # Fecha Entrada
        worksheet.set_column(2, 2, 12)  # Hora Entrada
        worksheet.set_column(3, 3, 18)  # Fecha Salida
        worksheet.set_column(4, 4, 12)  # Hora Salida
        worksheet.set_column(5, 5, 18)  # Horas Trabajadas
        worksheet.set_column(6, 6, 25)  # Dispositivo
        worksheet.set_column(7, 7, 20)  # Registro Biométrico
        
        # Escribir datos
        row = 1
        for att in attendances:
            # Empleado
            worksheet.write(row, 0, att.employee_id.name or '', text_format)
            
            # Fecha y hora de entrada
            if att.check_in:
                worksheet.write(row, 1, att.check_in.strftime('%d/%m/%Y'), text_format)
                worksheet.write(row, 2, att.check_in.strftime('%H:%M:%S'), text_format)
            else:
                worksheet.write(row, 1, '', text_format)
                worksheet.write(row, 2, '', text_format)
            
            # Fecha y hora de salida
            if att.check_out:
                worksheet.write(row, 3, att.check_out.strftime('%d/%m/%Y'), text_format)
                worksheet.write(row, 4, att.check_out.strftime('%H:%M:%S'), text_format)
            else:
                worksheet.write(row, 3, '', text_format)
                worksheet.write(row, 4, '', text_format)
            
            # Horas trabajadas
            if att.check_in and att.check_out:
                horas_trabajadas = att.check_out - att.check_in
                horas = horas_trabajadas.total_seconds() / 3600
                worksheet.write(row, 5, f"{horas:.2f}", center_format)
            else:
                worksheet.write(row, 5, '', text_format)
            
            # Dispositivo
            worksheet.write(row, 6, att.biometric_device_id.name if att.biometric_device_id else '', text_format)
            
            # Hora del registro biométrico
            if att.biometric_punch_time:
                worksheet.write(row, 7, att.biometric_punch_time.strftime('%d/%m/%Y %H:%M:%S'), text_format)
            else:
                worksheet.write(row, 7, '', text_format)
            
            row += 1
        
        # Congelar primera fila
        worksheet.freeze_panes(1, 0)
        
        # Cerrar workbook
        workbook.close()
        output.seek(0)
        
        # Nombre del archivo
        filename = f'asistencias_{self.name.replace(" ", "_")}_{fecha_desde.strftime("%Y%m%d")}_{fecha_hasta.strftime("%Y%m%d")}.xlsx'
        filename = filename.replace('/', '_')
        
        # Crear attachment
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(output.read()),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'res_model': self._name,
            'res_id': self.id,
        })
        
        # Retornar acción para descargar
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
    
    @api.model
    def _cron_sync_all_devices(self):
        """Método llamado por el cron para sincronizar todos los dispositivos activos"""
        devices = self.search([
            ('is_active', '=', True),
            ('auto_sync', '=', True)
        ])
        
        for device in devices:
            try:
                device.sync_attendance()
                _logger.info("Dispositivo %s sincronizado exitosamente", device.name)
            except Exception as e:
                _logger.error("Error al sincronizar dispositivo %s: %s", device.name, str(e))
                device.write({
                    'sync_status': 'error',
                    'sync_error_message': str(e)
                })
    
    def action_view_server_employees(self):
        """Abrir vista de empleados del servidor biométrico"""
        self.ensure_one()
        if self.connection_type != 'server':
            raise UserError(_('Esta acción solo está disponible para conexión a servidor'))
        
        # Sincronizar empleados del servidor
        result = self.sync_server_employees()
        
        return {
            'name': _('Empleados del Servidor Biométrico'),
            'type': 'ir.actions.act_window',
            'res_model': 'biometric.server.employee',
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [('device_id', '=', self.id)],
            'context': {
                'default_device_id': self.id,
                'create': False,  # No permitir crear manualmente, solo desde servidor
            },
        }
    
    def action_view_server_departments(self):
        """Abrir vista de departamentos del servidor biométrico"""
        self.ensure_one()
        if self.connection_type != 'server':
            raise UserError(_('Esta acción solo está disponible para conexión a servidor'))
        
        # Sincronizar departamentos del servidor
        self.sync_server_departments()
        
        return {
            'name': _('Departamentos del Servidor Biométrico'),
            'type': 'ir.actions.act_window',
            'res_model': 'biometric.server.department',
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [('device_id', '=', self.id)],
            'context': {'default_device_id': self.id},
        }
    
    def action_view_server_areas(self):
        """Abrir vista de áreas del servidor biométrico"""
        self.ensure_one()
        if self.connection_type != 'server':
            raise UserError(_('Esta acción solo está disponible para conexión a servidor'))
        
        # Sincronizar áreas del servidor
        self.sync_server_areas()
        
        return {
            'name': _('Áreas del Servidor Biométrico'),
            'type': 'ir.actions.act_window',
            'res_model': 'biometric.server.area',
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [('device_id', '=', self.id)],
            'context': {'default_device_id': self.id},
        }
    
    def sync_server_employees(self):
        """Sincronizar empleados del servidor y guardarlos en el modelo temporal"""
        self.ensure_one()
        if self.connection_type != 'server':
            raise UserError(_('Esta acción solo está disponible para conexión a servidor'))
        
        try:
            auth_token = self._server_authenticate()
            employees_data = self._server_get_users(auth_token)
            
            _logger.debug("Datos recibidos del servidor (tipo: %s): %s", type(employees_data), str(employees_data)[:500])
            
            # Asegurar que employees_data sea una lista
            if not isinstance(employees_data, list):
                if isinstance(employees_data, dict):
                    # Si es un diccionario, intentar extraer la lista
                    employees_data = employees_data.get('results', []) or employees_data.get('data', []) or employees_data.get('employees', [])
                    if not employees_data:
                        # Si no hay lista, podría ser un solo empleado
                        if employees_data.get('id'):
                            employees_data = [employees_data]
                        else:
                            _logger.error("No se pudo extraer lista de empleados del diccionario: %s", employees_data)
                            raise UserError(_('El servidor retornó datos en un formato inesperado. No se encontró lista de empleados.'))
                else:
                    _logger.error("Formato inesperado de datos de empleados: %s (tipo: %s)", employees_data, type(employees_data))
                    raise UserError(_('El servidor retornó datos en un formato inesperado (tipo: %s). Verifique la respuesta de la API.') % type(employees_data).__name__)
            
            if not employees_data:
                _logger.warning("No se obtuvieron empleados del servidor")
                raise UserError(_('No se encontraron empleados en el servidor.'))
            
            # Limpiar registros anteriores de este dispositivo
            self.env['biometric.server.employee'].search([('device_id', '=', self.id)]).unlink()
            
            # Crear registros
            created_count = 0
            error_count = 0
            for idx, emp_data in enumerate(employees_data):
                # Validar que emp_data sea un diccionario
                if not isinstance(emp_data, dict):
                    _logger.warning("Empleado #%d no es un diccionario, omitiendo: %s (tipo: %s)", idx + 1, emp_data, type(emp_data))
                    error_count += 1
                    continue
                
                _logger.debug("Procesando empleado #%d: %s", idx + 1, emp_data.get('id', 'Sin ID'))
                # Obtener nombre del departamento si existe
                dept_name = ''
                if emp_data.get('department'):
                    if isinstance(emp_data.get('department'), dict):
                        dept_name = emp_data.get('department', {}).get('dept_name', '')
                    elif isinstance(emp_data.get('department'), int):
                        # Buscar en departamentos ya sincronizados
                        dept = self.env['biometric.server.department'].search([
                            ('device_id', '=', self.id),
                            ('biometric_id', '=', emp_data.get('department'))
                        ], limit=1)
                        dept_name = dept.dept_name if dept else ''
                
                # Obtener áreas
                area_ids = ''
                area_data = emp_data.get('area')
                if area_data:
                    if isinstance(area_data, list):
                        area_list = []
                        for a in area_data:
                            if isinstance(a, int):
                                area_list.append(str(a))
                            elif isinstance(a, dict):
                                area_list.append(str(a.get('id', '')))
                            else:
                                area_list.append(str(a))
                        area_ids = ','.join(area_list)
                    elif isinstance(area_data, dict):
                        area_ids = str(area_data.get('id', ''))
                    else:
                        area_ids = str(area_data)
                
                try:
                    # Obtener ID del empleado
                    emp_id = emp_data.get('id')
                    if not emp_id:
                        _logger.warning("Empleado sin ID, omitiendo: %s", emp_data)
                        continue
                    
                    self.env['biometric.server.employee'].create({
                        'device_id': self.id,
                        'biometric_id': emp_id,
                        'emp_code': emp_data.get('emp_code', ''),
                        'first_name': emp_data.get('first_name', ''),
                        'last_name': emp_data.get('last_name', ''),
                        'department_id': (
                            emp_data.get('department') if isinstance(emp_data.get('department'), int) 
                            else (emp_data.get('department') or {}).get('id', 0) if isinstance(emp_data.get('department'), dict) 
                            else 0
                        ),
                        'department_name': dept_name,
                        'area_ids': area_ids,
                        'hire_date': emp_data.get('hire_date'),
                        'gender': emp_data.get('gender', ''),
                        'birthday': emp_data.get('birthday'),
                        'card_no': emp_data.get('card_no', ''),
                        'device_password': emp_data.get('device_password', ''),
                        'verify_mode': emp_data.get('verify_mode', 0),
                        'app_status': str(emp_data.get('app_status', '')),
                    })
                    created_count += 1
                except Exception as e:
                    _logger.error("Error al crear registro de empleado %s: %s. Datos: %s", 
                                emp_data.get('id', 'Desconocido'), str(e), str(emp_data)[:200])
                    error_count += 1
                    continue
            
            _logger.info("Sincronizados %d empleados del servidor (creados: %d, errores: %d)", 
                        len(employees_data), created_count, error_count)
            message = _('Se sincronizaron %d empleados del servidor (%d creados exitosamente).') % (len(employees_data), created_count)
            if error_count > 0:
                message += _('\n%d empleados tuvieron errores al procesarse. Revise los logs para más detalles.') % error_count
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sincronización Exitosa'),
                    'message': message,
                    'type': 'success' if error_count == 0 else 'warning',
                    'sticky': False,
                }
            }
        except Exception as e:
            _logger.error("Error al sincronizar empleados: %s", str(e))
            raise UserError(_('Error al sincronizar empleados: %s') % str(e))
    
    def sync_server_departments(self):
        """Sincronizar departamentos del servidor"""
        self.ensure_one()
        if self.connection_type != 'server':
            raise UserError(_('Esta acción solo está disponible para conexión a servidor'))
        
        try:
            auth_token = self._server_authenticate()
            depts_data = self._server_get_departments(auth_token)
            
            # Limpiar registros anteriores
            self.env['biometric.server.department'].search([('device_id', '=', self.id)]).unlink()
            
            # Crear registros
            for dept_data in depts_data:
                parent_name = ''
                if dept_data.get('parent_dept'):
                    if isinstance(dept_data.get('parent_dept'), dict):
                        parent_name = dept_data.get('parent_dept', {}).get('dept_name', '')
                
                self.env['biometric.server.department'].create({
                    'device_id': self.id,
                    'biometric_id': dept_data.get('id'),
                    'dept_code': dept_data.get('dept_code', ''),
                    'dept_name': dept_data.get('dept_name', ''),
                    'parent_dept': dept_data.get('parent_dept') if isinstance(dept_data.get('parent_dept'), int) else dept_data.get('parent_dept', {}).get('id', 0),
                    'parent_dept_name': parent_name,
                })
            
            _logger.info("Sincronizados %d departamentos del servidor", len(depts_data))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sincronización Exitosa'),
                    'message': _('Se sincronizaron %d departamentos del servidor.') % len(depts_data),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            _logger.error("Error al sincronizar departamentos: %s", str(e))
            raise UserError(_('Error al sincronizar departamentos: %s') % str(e))
    
    def sync_server_areas(self):
        """Sincronizar áreas del servidor"""
        self.ensure_one()
        if self.connection_type != 'server':
            raise UserError(_('Esta acción solo está disponible para conexión a servidor'))
        
        try:
            auth_token = self._server_authenticate()
            areas_data = self._server_get_areas(auth_token)
            
            # Limpiar registros anteriores
            self.env['biometric.server.area'].search([('device_id', '=', self.id)]).unlink()
            
            # Crear registros
            for area_data in areas_data:
                parent_name = ''
                if area_data.get('parent_area'):
                    if isinstance(area_data.get('parent_area'), dict):
                        parent_name = area_data.get('parent_area', {}).get('area_name', '')
                
                self.env['biometric.server.area'].create({
                    'device_id': self.id,
                    'biometric_id': area_data.get('id'),
                    'area_code': area_data.get('area_code', ''),
                    'area_name': area_data.get('area_name', ''),
                    'parent_area_id': area_data.get('parent_area') if isinstance(area_data.get('parent_area'), int) else area_data.get('parent_area', {}).get('id', 0),
                    'parent_area_name': parent_name,
                })
            
            _logger.info("Sincronizados %d áreas del servidor", len(areas_data))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sincronización Exitosa'),
                    'message': _('Se sincronizaron %d áreas del servidor.') % len(areas_data),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            _logger.error("Error al sincronizar áreas: %s", str(e))
            raise UserError(_('Error al sincronizar áreas: %s') % str(e))

