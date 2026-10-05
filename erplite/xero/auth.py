# -*- coding: utf-8 -*-
# Copyright (c) 2023, ERPLite and contributors
# For license information, please see license.txt

import frappe
import requests
import json
import base64
from datetime import datetime, timedelta
from frappe.utils import now_datetime, get_datetime
from erplite.xero import XERO_HTTP_TIMEOUT

def get_access_token():
    """Get access token using client credentials flow"""
    settings = frappe.get_single("Xero Settings")
    
    if not settings.client_id:
        frappe.throw("Client ID is required")
    
    # Get the client secret (password field)
    client_id = settings.client_id
    client_secret = settings.get_password('client_secret')
    if not client_secret:
        frappe.throw("Client Secret is required")
    
    # Create base64 encoded client_id:client_secret
    encoded_auth = base64.b64encode(bytes(client_id + ":" + client_secret, 'utf-8')).decode('utf-8')
    
    headers = {
        "Authorization": f"Basic {encoded_auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "client_credentials"
    }
    
    try:
        response = requests.post(
            "https://identity.xero.com/connect/token",
            data=data,
            headers=headers,
            timeout=XERO_HTTP_TIMEOUT,
        )
        
        if response.status_code == 200:
            tokens = response.json()
            
            # Update settings
            settings.access_token = tokens["access_token"]
            # Set token expiry time (subtract 5 minutes for safety margin)
            expiry_seconds = tokens["expires_in"] - 300  # 5 minutes safety margin
            settings.token_expiry = now_datetime() + timedelta(seconds=expiry_seconds)
            settings.authorization_status = "Authorized"
            settings.save()
            
            frappe.db.commit()
            return tokens["access_token"]
        
        # Include response text in the error message for debugging
        error_msg = f"Failed to get access token: Status {response.status_code}"
        try:
            error_details = response.json()
            error_msg += f", Error: {json.dumps(error_details)[:100]}"
        except:
            if response.text:
                error_msg += f", Response: {response.text[:100]}"
        
        frappe.throw(error_msg)
    except Exception as e:
        frappe.throw(f"Error connecting to Xero: {str(e)}")

def get_valid_token():
    """Get a valid access token, refreshing if necessary"""
    settings = frappe.get_single("Xero Settings")
    
    # Check if token exists
    if not settings.access_token:
        return get_access_token()
    
    # Check if token is expired or about to expire
    if not settings.token_expiry:
        return get_access_token()
    
    # Convert token_expiry to datetime if it's a string
    expiry_time = get_datetime(settings.token_expiry) if isinstance(settings.token_expiry, str) else settings.token_expiry
    
    # If token is expired or will expire in the next 5 minutes, refresh it
    if expiry_time <= now_datetime():
        frappe.log_error("Xero token expired, refreshing", "Xero Authentication")
        return get_access_token()
    
    return settings.access_token

def get_tenants():
    """Get Xero tenants (organizations) that the app has access to"""
    token = get_valid_token()
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(
            "https://api.xero.com/connections",
            headers=headers,
            timeout=XERO_HTTP_TIMEOUT,
        )
        
        if response.status_code == 200:
            tenants = response.json()
            
            # Update settings with tenant information if only one tenant
            if len(tenants) == 1:
                settings = frappe.get_single("Xero Settings")
                settings.tenant_id = tenants[0]["tenantId"]
                settings.tenant_name = tenants[0]["tenantName"]
                settings.reload()  # Reload before saving to avoid conflicts
                settings.save()
                frappe.db.commit()
            
            return tenants
        elif response.status_code == 401:
            # Token might be expired, try refreshing and retry
            frappe.log_error("Xero token unauthorized, refreshing and retrying", "Xero Authentication")
            token = get_access_token()  # Force refresh
            
            # Retry with new token
            headers["Authorization"] = f"Bearer {token}"
            response = requests.get(
                "https://api.xero.com/connections",
                headers=headers,
                timeout=XERO_HTTP_TIMEOUT,
            )
            
            if response.status_code == 200:
                tenants = response.json()
                
                # Update settings with tenant information if only one tenant
                if len(tenants) == 1:
                    settings = frappe.get_single("Xero Settings")
                    settings.tenant_id = tenants[0]["tenantId"]
                    settings.tenant_name = tenants[0]["tenantName"]
                    settings.reload()  # Reload before saving to avoid conflicts
                    settings.save()
                    frappe.db.commit()
                
                return tenants
        
        # Include response text in the error message for debugging
        error_msg = f"Failed to get Xero tenants: Status {response.status_code}"
        try:
            error_details = response.json()
            error_msg += f", Error: {json.dumps(error_details)[:100]}"
        except:
            if response.text:
                error_msg += f", Response: {response.text[:100]}"
        
        frappe.throw(error_msg)
    except Exception as e:
        frappe.throw(f"Error getting Xero tenants: {str(e)}")

def handle_api_request(url, method="GET", headers=None, data=None, json_data=None, max_retries=1):
    """
    Handle API requests to Xero with automatic token refresh on 401 errors
    
    Args:
        url (str): The API endpoint URL
        method (str): HTTP method (GET, POST, PUT, DELETE)
        headers (dict): HTTP headers
        data (dict): Form data for the request
        json_data (dict): JSON data for the request
        max_retries (int): Maximum number of retries on 401 errors
    
    Returns:
        Response object
    """
    if headers is None:
        headers = {}
    
    # Get valid token and add to headers
    token = get_valid_token()
    headers["Authorization"] = f"Bearer {token}"
    
    # Get tenant ID
    settings = frappe.get_single("Xero Settings")
    if not settings.tenant_id:
        frappe.throw("Xero tenant ID is required. Please connect to Xero first.")
    
    # Add tenant ID to headers
    headers["Xero-Tenant-Id"] = settings.tenant_id
    
    # Set content type if not provided
    if "Content-Type" not in headers:
        headers["Content-Type"] = "application/json"
    
    # Make the request
    retry_count = 0
    while retry_count <= max_retries:
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, timeout=XERO_HTTP_TIMEOUT)
            elif method.upper() == "POST":
                if json_data:
                    response = requests.post(
                        url, headers=headers, json=json_data, timeout=XERO_HTTP_TIMEOUT
                    )
                else:
                    response = requests.post(
                        url, headers=headers, data=data, timeout=XERO_HTTP_TIMEOUT
                    )
            elif method.upper() == "PUT":
                if json_data:
                    response = requests.put(
                        url, headers=headers, json=json_data, timeout=XERO_HTTP_TIMEOUT
                    )
                else:
                    response = requests.put(
                        url, headers=headers, data=data, timeout=XERO_HTTP_TIMEOUT
                    )
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers, timeout=XERO_HTTP_TIMEOUT)
            else:
                frappe.throw(f"Unsupported HTTP method: {method}")
            
            # If unauthorized and retries left, refresh token and retry
            if response.status_code == 401 and retry_count < max_retries:
                frappe.log_error(f"Xero API request unauthorized, refreshing token and retrying: {url}", "Xero API")
                token = get_access_token()  # Force refresh
                headers["Authorization"] = f"Bearer {token}"
                retry_count += 1
                continue
            
            return response
        
        except Exception as e:
            frappe.log_error(f"Error in Xero API request: {str(e)}", "Xero API")
            raise
    
    # If we get here, all retries failed
    frappe.throw("Failed to authenticate with Xero after multiple attempts")
