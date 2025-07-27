import frappe
import requests
from frappe import _
from urllib.parse import urlencode
import json

@frappe.whitelist()
def search_everything(query, **kwargs):
    """
    Proxy search requests to Everything HTTP server
    """
    try:
        # Get Everything server settings from site config or defaults
        settings = get_everything_settings()
        
        # Build the Everything HTTP API URL
        base_url = f"{settings.get('server_url', 'http://localhost')}:{settings.get('server_port', 80)}"
        
        # Prepare query parameters
        params = {
            'search': query,
            'json': '1',
            'path_column': '1',
            'size_column': '1',
            'date_modified_column': '1'
        }
        
        # Add optional parameters
        for key, value in kwargs.items():
            if value is not None and value != '':
                params[key] = str(value)
        
        # Make request to Everything server with authentication
        url = f"{base_url}/?{urlencode(params)}"
        
        # Prepare authentication if credentials are provided
        auth = None
        username = settings.get('username')
        password = settings.get('password')
        if username and password:
            auth = (username, password)
        
        response = requests.get(url, auth=auth, timeout=10)
        response.raise_for_status()
        
        # Parse JSON response
        data = response.json()
        
        # Process results to ensure consistent format
        results = []
        if 'results' in data:
            for result in data['results']:
                processed_result = {
                    'name': result.get('name', ''),
                    'path': result.get('path', ''),
                    'type': 'folder' if result.get('type') == 'folder' else 'file',
                    'size': result.get('size'),
                    'date_modified': result.get('date_modified')
                }
                results.append(processed_result)
        
        return {
            'success': True,
            'results': results,
            'totalResults': data.get('totalResults', len(results)),
            'query': query,
            'server_url': base_url
        }
        
    except requests.exceptions.ConnectionError:
        frappe.log_error("Everything server connection failed", "Everything Search")
        return {
            'success': False,
            'error': 'Unable to connect to Everything server. Please check if Everything is running with HTTP server enabled.',
            'error_type': 'connection_error'
        }
        
    except requests.exceptions.Timeout:
        frappe.log_error("Everything server timeout", "Everything Search")
        return {
            'success': False,
            'error': 'Everything server request timed out.',
            'error_type': 'timeout_error'
        }
        
    except requests.exceptions.HTTPError as e:
        frappe.log_error(f"Everything server HTTP error: {e}", "Everything Search")
        return {
            'success': False,
            'error': f'Everything server returned HTTP {e.response.status_code}: {e.response.reason}',
            'error_type': 'http_error'
        }
        
    except json.JSONDecodeError:
        frappe.log_error("Everything server returned invalid JSON", "Everything Search")
        return {
            'success': False,
            'error': 'Everything server returned invalid response format.',
            'error_type': 'json_error'
        }
        
    except Exception as e:
        frappe.log_error(f"Everything search error: {str(e)}", "Everything Search")
        return {
            'success': False,
            'error': f'An unexpected error occurred: {str(e)}',
            'error_type': 'unknown_error'
        }

@frappe.whitelist()
def test_connection(**kwargs):
    """
    Test connection to Everything HTTP server
    """
    try:
        # Get server settings (use hardcoded settings if no parameters provided)
        settings = get_everything_settings()
        server_url = kwargs.get('server_url', settings.get('server_url'))
        server_port = kwargs.get('server_port', settings.get('server_port'))
        
        # Build test URL
        base_url = f"{server_url}:{server_port}"
        test_url = f"{base_url}/?json=1&count=1"
        
        # Prepare authentication if credentials are provided
        auth = None
        username = settings.get('username')
        password = settings.get('password')
        if username and password:
            auth = (username, password)
        
        # Make test request with authentication
        response = requests.get(test_url, auth=auth, timeout=5)
        response.raise_for_status()
        
        # Try to parse JSON to ensure it's a valid Everything response
        data = response.json()
        
        return {
            'success': True,
            'message': 'Successfully connected to Everything server',
            'server_url': base_url,
            'response_time': response.elapsed.total_seconds() * 1000  # Convert to milliseconds
        }
        
    except requests.exceptions.ConnectionError:
        return {
            'success': False,
            'error': 'Unable to connect to Everything server. Please check if Everything is running with HTTP server enabled.',
            'error_type': 'connection_error'
        }
        
    except requests.exceptions.Timeout:
        return {
            'success': False,
            'error': 'Connection to Everything server timed out.',
            'error_type': 'timeout_error'
        }
        
    except requests.exceptions.HTTPError as e:
        return {
            'success': False,
            'error': f'Everything server returned HTTP {e.response.status_code}: {e.response.reason}',
            'error_type': 'http_error'
        }
        
    except json.JSONDecodeError:
        return {
            'success': False,
            'error': 'Everything server returned invalid response format.',
            'error_type': 'json_error'
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': f'An unexpected error occurred: {str(e)}',
            'error_type': 'unknown_error'
        }

@frappe.whitelist()
def get_settings():
    """
    Get Everything search settings
    """
    settings = get_everything_settings()
    return {
        'success': True,
        'settings': settings
    }

@frappe.whitelist()
def save_settings(**kwargs):
    """
    Save Everything search settings
    """
    try:
        # Validate settings
        server_url = kwargs.get('server_url', 'http://localhost').strip()
        server_port = int(kwargs.get('server_port', 80))
        
        if not server_url:
            server_url = 'http://localhost'
            
        if server_port < 1 or server_port > 65535:
            server_port = 80
        
        # Save to site config or user preferences
        settings = {
            'server_url': server_url,
            'server_port': server_port,
            'results_per_page': int(kwargs.get('results_per_page', 50)),
            'auto_search': bool(kwargs.get('auto_search', True))
        }
        
        # Save settings (you might want to store this in a custom DocType or site config)
        frappe.cache().set_value(f"everything_settings_{frappe.session.user}", settings)
        
        return {
            'success': True,
            'message': 'Settings saved successfully',
            'settings': settings
        }
        
    except ValueError as e:
        return {
            'success': False,
            'error': f'Invalid setting value: {str(e)}',
            'error_type': 'validation_error'
        }
        
    except Exception as e:
        frappe.log_error(f"Error saving Everything settings: {str(e)}", "Everything Search")
        return {
            'success': False,
            'error': f'Failed to save settings: {str(e)}',
            'error_type': 'save_error'
        }

def get_everything_settings():
    """
    Get Everything settings from cache or defaults
    """
    # Try to get user-specific settings from cache
    settings = frappe.cache().get_value(f"everything_settings_{frappe.session.user}")
    
    if not settings:
        # Default settings with hardcoded authentication
        settings = {
            'server_url': 'http://119.42.53.73',
            'server_port': 8080,
            'results_per_page': 50,
            'auto_search': True,
            'username': 'eDvki23PEXTWHxxgtYoZUWAdi9J',  # Add your Everything HTTP username here
            'password': 'A43KP497rq9HoFZtE5Vz2vvUVuT'   # Add your Everything HTTP password here
        }
    
    return settings

@frappe.whitelist()
def download_file(file_path=None):
    """
    Download a file through Everything HTTP server
    """
    try:
        import mimetypes
        from urllib.parse import quote
        
        # Get file_path from form data if not provided as argument
        if not file_path:
            file_path = frappe.form_dict.get('file_path')
        
        if not file_path:
            frappe.throw(_("File path is required"))
        
        # Get Everything server settings
        settings = get_everything_settings()
        base_url = f"{settings.get('server_url', 'http://localhost')}:{settings.get('server_port', 80)}"
        
        # Prepare authentication
        auth = None
        username = settings.get('username')
        password = settings.get('password')
        if username and password:
            auth = (username, password)
        
        # Build download URL - Everything HTTP server serves files directly by path
        # URL encode the file path
        encoded_path = quote(file_path.replace('\\', '/'))
        download_url = f"{base_url}/{encoded_path}"
        
        # Make request to Everything server to get the file
        response = requests.get(download_url, auth=auth, timeout=30, stream=True)
        response.raise_for_status()
        
        # Get file info for proper headers
        filename = file_path.split('\\')[-1] if '\\' in file_path else file_path.split('/')[-1]
        mime_type, _ = mimetypes.guess_type(filename)
        if not mime_type:
            mime_type = 'application/octet-stream'
        
        # Create Frappe response with file content
        frappe.local.response.filename = filename
        frappe.local.response.filecontent = response.content
        frappe.local.response.type = "download"
        frappe.local.response.headers = {
            'Content-Type': mime_type,
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Length': str(len(response.content))
        }
        
        # Don't return JSON for file downloads - Frappe handles the file response
        return
        
    except requests.exceptions.ConnectionError:
        frappe.log_error("Everything server connection failed during download", "Everything Search")
        return {
            'success': False,
            'error': 'Unable to connect to Everything server for download.',
            'error_type': 'connection_error'
        }
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return {
                'success': False,
                'error': 'File not found on Everything server.',
                'error_type': 'file_not_found'
            }
        else:
            frappe.log_error(f"Everything server HTTP error during download: {e}", "Everything Search")
            return {
                'success': False,
                'error': f'Everything server returned HTTP {e.response.status_code}: {e.response.reason}',
                'error_type': 'http_error'
            }
        
    except Exception as e:
        frappe.log_error(f"File download error: {str(e)}", "Everything Search")
        return {
            'success': False,
            'error': f'Download failed: {str(e)}',
            'error_type': 'download_error'
        }

@frappe.whitelist()
def get_file_info(file_path):
    """
    Get additional file information (if needed for future features)
    """
    try:
        import os
        import mimetypes
        from datetime import datetime
        
        if not os.path.exists(file_path):
            return {
                'success': False,
                'error': 'File not found'
            }
        
        stat = os.stat(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)
        
        return {
            'success': True,
            'info': {
                'path': file_path,
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
                'mime_type': mime_type,
                'is_directory': os.path.isdir(file_path)
            }
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
