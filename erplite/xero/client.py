# -*- coding: utf-8 -*-
# Copyright (c) 2023, ERPLite and contributors
# For license information, please see license.txt

import frappe
import requests
import json
from .auth import get_valid_token

class XeroClient:
    """Base client for Xero API interactions"""
    
    API_BASE_URL = "https://api.xero.com/api.xro/2.0"
    
    def __init__(self):
        self.token = get_valid_token()
    
    def get_headers(self):
        """Get request headers with authentication"""
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    def get(self, endpoint, params=None):
        """Make a GET request to Xero API"""
        url = f"{self.API_BASE_URL}/{endpoint}"
        response = requests.get(url, headers=self.get_headers(), params=params)
        
        if response.status_code == 200:
            return response.json()
        
        frappe.throw(f"Xero API Error: {response.text}")
    
    def post(self, endpoint, data):
        """Make a POST request to Xero API"""
        url = f"{self.API_BASE_URL}/{endpoint}"
        response = requests.post(
            url, 
            headers=self.get_headers(), 
            data=json.dumps(data)
        )
        
        if response.status_code in [200, 201]:
            return response.json()
        
        frappe.throw(f"Xero API Error: {response.text}")
    
    def put(self, endpoint, data):
        """Make a PUT request to Xero API"""
        url = f"{self.API_BASE_URL}/{endpoint}"
        response = requests.put(
            url, 
            headers=self.get_headers(), 
            data=json.dumps(data)
        )
        
        if response.status_code in [200, 201]:
            return response.json()
        
        frappe.throw(f"Xero API Error: {response.text}")
