# -*- coding: utf-8 -*-
# Copyright (c) 2023, ERPLite and contributors
# For license information, please see license.txt

import frappe
import requests
import json
import base64
import os
from datetime import datetime
from frappe.utils import now_datetime, cstr, get_files_path
from erplite.xero.auth import get_valid_token
from erplite.xero import XERO_HTTP_TIMEOUT

def find_invoice_in_xero(invoice_number, invoice_type, contact_name, tenant_id, token):
    """Return the invoice Xero already holds under this InvoiceNumber, or None.

    This is what makes "Send to Xero" repeatable. `xero_invoice_id` is stored
    only after Xero answers, so a POST that reaches Xero whose reply is lost
    leaves three things true at once: the invoice is in Xero, the local
    already-sent guard is still open, and the user is reading a failure. The
    obvious retry then creates a second invoice. Asking Xero first turns that
    retry into a stop.

    It never answers None on doubt. If Xero cannot be reached, or answers
    something this cannot read, it throws: "we could not check" is not "it is
    not there", and the caller must not post on a maybe. Nothing is sent in that
    case, so the user can simply try again.

    A match has to agree on InvoiceNumber, Type and the contact's name, because
    an ACCPAY invoice number belongs to the supplier and two suppliers can both
    use "INV-001". VOIDED and DELETED invoices do not count as a match: Xero
    frees that number again, so sending is the right thing to do.
    """
    if not invoice_number:
        return None

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Xero-Tenant-Id": tenant_id
    }

    try:
        response = requests.get(
            "https://api.xero.com/api.xro/2.0/Invoices",
            headers=headers,
            params={"InvoiceNumbers": cstr(invoice_number)},
            timeout=XERO_HTTP_TIMEOUT
        )
    except Exception as e:
        frappe.throw(
            f"Could not check whether Xero already has invoice {invoice_number}: "
            f"{str(e)}. Nothing was sent. Please try again."
        )

    if response.status_code != 200:
        frappe.throw(
            f"Could not check whether Xero already has invoice {invoice_number}: "
            f"Xero answered {response.status_code}, {response.text[:500]}. "
            "Nothing was sent. Please try again."
        )

    try:
        invoices = response.json().get("Invoices") or []
    except Exception as e:
        frappe.throw(
            f"Could not read Xero's answer when checking invoice {invoice_number}: "
            f"{str(e)}. Nothing was sent. Please try again."
        )

    wanted = cstr(invoice_number).strip().lower()

    # If anything came back under a different number then Xero did not apply the
    # InvoiceNumbers filter, and "nothing here matches" stops being evidence of
    # absence -- the list is capped at 100 and ours could be on a later page.
    others = [
        inv for inv in invoices
        if cstr(inv.get("InvoiceNumber")).strip().lower() != wanted
    ]
    if others:
        frappe.throw(
            f"Could not check whether Xero already has invoice {invoice_number}: "
            f"asked Xero for that number and it returned {len(invoices)} invoice(s), "
            f"{len(others)} of them under other numbers, so the answer cannot be "
            "trusted. Nothing was sent."
        )

    for invoice in invoices:
        if invoice.get("Type") != invoice_type:
            continue
        if cstr(invoice.get("Status")).strip().upper() in ("VOIDED", "DELETED"):
            continue
        if contact_name:
            theirs = cstr((invoice.get("Contact") or {}).get("Name")).strip().lower()
            if theirs != cstr(contact_name).strip().lower():
                continue
        return invoice

    return None


def _already_in_xero_message(invoice_number, existing):
    return (
        f"Xero already has invoice {invoice_number} "
        f"(Xero Invoice ID {existing.get('InvoiceID')}, "
        f"status {existing.get('Status')}), so nothing was sent. "
        "This happens when an earlier send reached Xero but its reply did not "
        "reach us. Check the invoice in Xero before sending anything again."
    )


def create_sales_invoice(sales_invoice):
    """Create a sales invoice in Xero"""
    # Get Xero settings
    settings = frappe.get_single("Xero Settings")
    
    if not settings.tenant_id:
        frappe.throw("Xero tenant ID is required. Please connect to Xero first.")
    
    # Get access token
    token = get_valid_token()
    
    # Prepare invoice data
    line_items = []
    for item in sales_invoice.items:
        line_item = {
            "Description": item.description or item.item_name,
            "Quantity": item.qty,
            "UnitAmount": item.rate,
            # "AccountCode": "200", # Removed as it may not match Xero accounts
            "TaxType": "OUTPUT" if item.tax_rate else "BASEXCLUDED"  # Changed to BASEXCLUDED for tax-exempt
        }
        line_items.append(line_item)
    
    invoice_data = {
        "Type": "ACCREC",
        "Contact": {
            "Name": sales_invoice.customer_name
        },
        "Date": sales_invoice.posting_date.strftime("%Y-%m-%d"),
        "DueDate": sales_invoice.due_date.strftime("%Y-%m-%d"),
        "LineItems": line_items,
        # Always a draft. Invoices are reviewed and approved in Xero, not here.
        # This replaces "AUTHORISED" if <doc>.status == "Submitted" else "DRAFT",
        # which promised a choice the app could not make: Sales Invoice is not
        # submittable and its status is read-only, so it is always "Draft", and
        # on Purchase Invoice the Select is editable, so the same line sent an
        # authorised invoice to the real ledger if someone had set it by hand.
        "Status": "DRAFT",
        "InvoiceNumber": cstr(sales_invoice.name)  # For sales invoices, use our internal reference
    }
    
    # Don't post a second copy of an invoice Xero already has: see
    # find_invoice_in_xero. Deliberately outside the try/except below, so that
    # this stop reaches the user as a stop and not as a failed send.
    existing = find_invoice_in_xero(
        invoice_data["InvoiceNumber"], "ACCREC",
        sales_invoice.customer_name, settings.tenant_id, token
    )
    if existing:
        frappe.throw(_already_in_xero_message(invoice_data["InvoiceNumber"], existing))

    # Send to Xero
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Xero-Tenant-Id": settings.tenant_id
    }
    
    try:
        response = requests.post(
            "https://api.xero.com/api.xro/2.0/Invoices",
            headers=headers,
            data=json.dumps({"Invoices": [invoice_data]}),
            timeout=XERO_HTTP_TIMEOUT,
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("Invoices") and len(result["Invoices"]) > 0:
                invoice = result["Invoices"][0]
                
                # Update sales invoice with Xero details
                frappe.db.set_value("Sales Invoice", sales_invoice.name, {
                    "xero_invoice_id": invoice["InvoiceID"],
                    "xero_invoice_number": invoice.get("InvoiceNumber"),
                    "xero_status": invoice.get("Status"),
                    "xero_sync_date": now_datetime()
                })
                
                return invoice["InvoiceID"]
            
            frappe.throw("Failed to create invoice in Xero: No invoice returned")
        
        error_msg = f"Failed to create invoice in Xero: Status {response.status_code}"
        try:
            error_details = response.json()
            error_msg += f", Error: {json.dumps(error_details)}"
        except:
            if response.text:
                error_msg += f", Response: {response.text}"
        
        frappe.throw(error_msg)
    except Exception as e:
        frappe.throw(f"Error creating invoice in Xero: {str(e)}")

def create_purchase_invoice(purchase_invoice):
    """Create a purchase invoice in Xero"""
    # Get Xero settings
    settings = frappe.get_single("Xero Settings")
    
    if not settings.tenant_id:
        frappe.throw("Xero tenant ID is required. Please connect to Xero first.")
    
    # Get access token
    token = get_valid_token()
    
    # Prepare invoice data
    line_items = []
    for item in purchase_invoice.items:
        combined_description = f"{item.item_name} - {item.description}" if item.description else item.item_name
        line_item = {
            "Description": combined_description,
            "Quantity": item.qty,
            "UnitAmount": item.rate,
            # "AccountCode": "300", # Removed as it doesn't match Xero accounts
            "TaxType": "INPUT" if item.tax_rate else "BASEXCLUDED"  # Changed to BASEXCLUDED for tax-exempt
        }
        line_items.append(line_item)
    
    # For purchase invoices, use the supplier's invoice number if available
    # If not available (like for receipts), use our internal reference
    if purchase_invoice.supplier_invoice_number:
        invoice_number = purchase_invoice.supplier_invoice_number
    else:
        # Use internal document name as fallback for receipts and other documents without formal invoice numbers
        invoice_number = f"REF-{purchase_invoice.name}"
    
    invoice_data = {
        "Type": "ACCPAY",
        "Contact": {
            "Name": purchase_invoice.supplier_name
        },
        "Date": purchase_invoice.posting_date.strftime("%Y-%m-%d"),
        "DueDate": purchase_invoice.due_date.strftime("%Y-%m-%d"),
        "LineItems": line_items,
        # Always a draft. Invoices are reviewed and approved in Xero, not here.
        # This replaces "AUTHORISED" if <doc>.status == "Submitted" else "DRAFT",
        # which promised a choice the app could not make: Sales Invoice is not
        # submittable and its status is read-only, so it is always "Draft", and
        # on Purchase Invoice the Select is editable, so the same line sent an
        # authorised invoice to the real ledger if someone had set it by hand.
        "Status": "DRAFT",
        "InvoiceNumber": invoice_number
    }
    
    # Don't post a second copy of an invoice Xero already has: see
    # find_invoice_in_xero. Deliberately outside the try/except below, so that
    # this stop reaches the user as a stop and not as a failed send.
    existing = find_invoice_in_xero(
        invoice_data["InvoiceNumber"], "ACCPAY",
        purchase_invoice.supplier_name, settings.tenant_id, token
    )
    if existing:
        frappe.throw(_already_in_xero_message(invoice_data["InvoiceNumber"], existing))

    # Log the invoice data for debugging
    frappe.log_error("Xero Integration", f"Xero Invoice Data: {json.dumps(invoice_data)}")
    
    # Send to Xero
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Xero-Tenant-Id": settings.tenant_id
    }
    
    try:
        response = requests.post(
            "https://api.xero.com/api.xro/2.0/Invoices",
            headers=headers,
            data=json.dumps({"Invoices": [invoice_data]}),
            timeout=XERO_HTTP_TIMEOUT,
        )
        
        # Log the response for debugging
        frappe.log_error("Xero Integration", f"Xero Response: Status {response.status_code}, Body: {response.text[:1000]}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("Invoices") and len(result["Invoices"]) > 0:
                invoice = result["Invoices"][0]
                
                # Update purchase invoice with Xero details
                frappe.db.set_value("Purchase Invoice", purchase_invoice.name, {
                    "xero_invoice_id": invoice["InvoiceID"],
                    "xero_invoice_number": invoice.get("InvoiceNumber"),
                    "xero_status": invoice.get("Status"),
                    "xero_sync_date": now_datetime()
                })
                
                # Add comment to purchase invoice history
                frappe.get_doc("Purchase Invoice", purchase_invoice.name).add_comment(
                    "Info", 
                    f"Invoice successfully sent to Xero. Xero Invoice ID: {invoice['InvoiceID']}, "
                    f"Xero Invoice Number: {invoice.get('InvoiceNumber', 'N/A')}, "
                    f"Status: {invoice.get('Status', 'N/A')}"
                )
                
                # Upload attachments to Xero
                upload_attachments_to_xero_invoice(invoice["InvoiceID"], purchase_invoice.name)
                
                return invoice["InvoiceID"]
            
            frappe.throw("Failed to create invoice in Xero: No invoice returned")
        
        error_msg = f"Failed to create invoice in Xero: Status {response.status_code}"
        try:
            error_details = response.json()
            error_msg += f", Error: {json.dumps(error_details)}"
        except:
            if response.text:
                error_msg += f", Response: {response.text}"
        
        frappe.throw(error_msg)
    except Exception as e:
        frappe.throw(f"Error creating invoice in Xero: {str(e)}")

def upload_attachments_to_xero_invoice(invoice_id, purchase_invoice_name):
    """Upload attachments from Purchase Invoice to Xero Invoice"""
    try:
        # Get Xero settings
        settings = frappe.get_single("Xero Settings")
        
        if not settings.tenant_id:
            return
        
        # Get all attachments for this purchase invoice
        attachments = frappe.get_all("File", 
                                   filters={
                                       "attached_to_doctype": "Purchase Invoice",
                                       "attached_to_name": purchase_invoice_name
                                   },
                                   fields=["name", "file_name", "file_url", "is_private"])
        
        if not attachments:
            # Add comment that no attachments were found
            frappe.get_doc("Purchase Invoice", purchase_invoice_name).add_comment(
                "Info", 
                "No attachments found to upload to Xero"
            )
            return
        
        # Get fresh access token for file uploads
        token = get_valid_token()
        
        uploaded_count = 0
        failed_count = 0
        failed_files = []
        
        for attachment in attachments:
            try:
                # Get the file path
                if attachment.file_url:
                    if attachment.file_url.startswith('/files/'):
                        # For public files
                        file_path = frappe.get_site_path('public', 'files', attachment.file_url.split('/files/')[-1])
                    elif attachment.file_url.startswith('/private/files/'):
                        # For private files
                        file_path = frappe.get_site_path('private', 'files', attachment.file_url.split('/private/files/')[-1])
                    else:
                        failed_count += 1
                        failed_files.append(f"{attachment.file_name} (invalid path)")
                        continue
                    
                    # Check if file exists
                    if not os.path.exists(file_path):
                        failed_count += 1
                        failed_files.append(f"{attachment.file_name} (file not found)")
                        frappe.log_error("Xero Attachment", f"File not found: {file_path}")
                        continue
                    
                    # Read file content
                    with open(file_path, 'rb') as f:
                        file_content = f.read()
                    
                    # Prepare headers for file upload (no Content-Type for multipart)
                    headers = {
                        "Authorization": f"Bearer {token}",
                        "Xero-Tenant-Id": settings.tenant_id
                    }
                    
                    # Prepare multipart form data
                    files = {
                        'file': (attachment.file_name, file_content, 'application/octet-stream')
                    }
                    
                    # Upload to Xero
                    response = requests.post(
                        f"https://api.xero.com/api.xro/2.0/Invoices/{invoice_id}/Attachments/{attachment.file_name}",
                        headers=headers,
                        files=files,
                        timeout=XERO_HTTP_TIMEOUT,
                    )
                    
                    if response.status_code == 200:
                        uploaded_count += 1
                        frappe.log_error("Xero Attachment", f"Successfully uploaded: {attachment.file_name}")
                    else:
                        failed_count += 1
                        failed_files.append(attachment.file_name)
                        frappe.log_error("Xero Attachment", f"Failed to upload {attachment.file_name}: Status {response.status_code}, Response: {response.text}")
                    
            except Exception as e:
                failed_count += 1
                failed_files.append(f"{attachment.file_name} (error: {str(e)})")
                frappe.log_error("Xero Attachment", f"Error uploading {attachment.file_name}: {str(e)}")
                continue
        
        # Add comprehensive comment about attachment upload results
        total_attachments = len(attachments)
        if uploaded_count > 0 and failed_count == 0:
            # All successful
            frappe.get_doc("Purchase Invoice", purchase_invoice_name).add_comment(
                "Info", 
                f"Successfully uploaded all {uploaded_count} attachment(s) to Xero invoice {invoice_id}"
            )
        elif uploaded_count > 0 and failed_count > 0:
            # Some successful, some failed
            frappe.get_doc("Purchase Invoice", purchase_invoice_name).add_comment(
                "Info", 
                f"Uploaded {uploaded_count} of {total_attachments} attachment(s) to Xero invoice {invoice_id}. "
                f"Failed: {', '.join(failed_files)}"
            )
        else:
            # All failed
            frappe.get_doc("Purchase Invoice", purchase_invoice_name).add_comment(
                "Info", 
                f"Failed to upload all {total_attachments} attachment(s) to Xero invoice {invoice_id}. "
                f"Failed files: {', '.join(failed_files)}"
            )
        
    except Exception as e:
        frappe.log_error("Xero Attachment", f"Error uploading attachments to Xero: {str(e)}")
        # Add comment about general error
        frappe.get_doc("Purchase Invoice", purchase_invoice_name).add_comment(
            "Info", 
            f"Error occurred while uploading attachments to Xero: {str(e)}"
        )

def create_customer(customer):
    """Create a customer in Xero"""
    # Get Xero settings
    settings = frappe.get_single("Xero Settings")
    
    if not settings.tenant_id:
        frappe.throw("Xero tenant ID is required. Please connect to Xero first.")
    
    # Get access token
    token = get_valid_token()
    
    # Prepare customer data
    customer_data = {
        "Name": customer.customer_name,
        "FirstName": customer.first_name or "",
        "LastName": customer.last_name or "",
        "EmailAddress": customer.email or "",
        "Phones": [
            {
                "PhoneType": "DEFAULT",
                "PhoneNumber": customer.phone or ""
            }
        ],
        "Addresses": [
            {
                "AddressType": "STREET",
                "AddressLine1": customer.address_line1 or "",
                "AddressLine2": customer.address_line2 or "",
                "City": customer.city or "",
                "Region": customer.state or "",
                "PostalCode": customer.postal_code or "",
                "Country": customer.country or ""
            }
        ]
    }
    
    # Send to Xero
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Xero-Tenant-Id": settings.tenant_id
    }
    
    try:
        response = requests.post(
            "https://api.xero.com/api.xro/2.0/Contacts",
            headers=headers,
            data=json.dumps({"Contacts": [customer_data]}),
            timeout=XERO_HTTP_TIMEOUT,
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("Contacts") and len(result["Contacts"]) > 0:
                contact = result["Contacts"][0]
                
                # Update customer
                frappe.db.set_value("Customer", customer.name, {
                    "xero_contact_id": contact["ContactID"],
                    "xero_sync_date": now_datetime()
                })
                
                return contact["ContactID"]
            
            frappe.throw("Failed to create customer in Xero: No contact returned")
        
        error_msg = f"Failed to create customer in Xero: Status {response.status_code}"
        try:
            error_details = response.json()
            error_msg += f", Error: {json.dumps(error_details)}"
        except:
            if response.text:
                error_msg += f", Response: {response.text}"
        
        frappe.throw(error_msg)
    except Exception as e:
        frappe.throw(f"Error creating customer in Xero: {str(e)}")

def create_supplier(supplier):
    """Create a supplier in Xero"""
    # Get Xero settings
    settings = frappe.get_single("Xero Settings")
    
    if not settings.tenant_id:
        frappe.throw("Xero tenant ID is required. Please connect to Xero first.")
    
    # Get access token
    token = get_valid_token()
    
    # Prepare supplier data
    supplier_data = {
        "Name": supplier.supplier_name,
        "FirstName": supplier.first_name or "",
        "LastName": supplier.last_name or "",
        "EmailAddress": supplier.email or "",
        "Phones": [
            {
                "PhoneType": "DEFAULT",
                "PhoneNumber": supplier.phone or ""
            }
        ],
        "Addresses": [
            {
                "AddressType": "STREET",
                "AddressLine1": supplier.address_line1 or "",
                "AddressLine2": supplier.address_line2 or "",
                "City": supplier.city or "",
                "Region": supplier.state or "",
                "PostalCode": supplier.postal_code or "",
                "Country": supplier.country or ""
            }
        ],
        "IsSupplier": True
    }
    
    # Send to Xero
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Xero-Tenant-Id": settings.tenant_id
    }
    
    try:
        response = requests.post(
            "https://api.xero.com/api.xro/2.0/Contacts",
            headers=headers,
            data=json.dumps({"Contacts": [supplier_data]}),
            timeout=XERO_HTTP_TIMEOUT,
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("Contacts") and len(result["Contacts"]) > 0:
                contact = result["Contacts"][0]
                
                # Update supplier
                frappe.db.set_value("Supplier", supplier.name, {
                    "xero_contact_id": contact["ContactID"],
                    "xero_sync_date": now_datetime()
                })
                
                return contact["ContactID"]
            
            frappe.throw("Failed to create supplier in Xero: No contact returned")
        
        error_msg = f"Failed to create supplier in Xero: Status {response.status_code}"
        try:
            error_details = response.json()
            error_msg += f", Error: {json.dumps(error_details)}"
        except:
            if response.text:
                error_msg += f", Response: {response.text}"
        
        frappe.throw(error_msg)
    except Exception as e:
        frappe.throw(f"Error creating supplier in Xero: {str(e)}")

def get_customers_from_xero():
    """Get customers from Xero"""
    # Get Xero settings
    settings = frappe.get_single("Xero Settings")
    
    if not settings.tenant_id:
        frappe.throw("Xero tenant ID is required. Please connect to Xero first.")
    
    # Get access token
    token = get_valid_token()
    
    # Send to Xero
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Xero-Tenant-Id": settings.tenant_id
    }
    
    try:
        response = requests.get(
            "https://api.xero.com/api.xro/2.0/Contacts?where=IsCustomer=true",
            headers=headers,
            timeout=XERO_HTTP_TIMEOUT,
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("Contacts"):
                return result["Contacts"]
            
            return []
        
        error_msg = f"Failed to get customers from Xero: Status {response.status_code}"
        try:
            error_details = response.json()
            error_msg += f", Error: {json.dumps(error_details)}"
        except:
            if response.text:
                error_msg += f", Response: {response.text}"
        
        frappe.throw(error_msg)
    except Exception as e:
        frappe.throw(f"Error getting customers from Xero: {str(e)}")

def get_suppliers_from_xero():
    """Get suppliers from Xero"""
    # Get Xero settings
    settings = frappe.get_single("Xero Settings")
    
    if not settings.tenant_id:
        frappe.throw("Xero tenant ID is required. Please connect to Xero first.")
    
    # Get access token
    token = get_valid_token()
    
    # Send to Xero
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Xero-Tenant-Id": settings.tenant_id
    }
    
    try:
        response = requests.get(
            "https://api.xero.com/api.xro/2.0/Contacts?where=IsSupplier=true",
            headers=headers,
            timeout=XERO_HTTP_TIMEOUT,
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("Contacts"):
                return result["Contacts"]
            
            return []
        
        error_msg = f"Failed to get suppliers from Xero: Status {response.status_code}"
        try:
            error_details = response.json()
            error_msg += f", Error: {json.dumps(error_details)}"
        except:
            if response.text:
                error_msg += f", Response: {response.text}"
        
        frappe.throw(error_msg)
    except Exception as e:
        frappe.throw(f"Error getting suppliers from Xero: {str(e)}")

def import_customer_from_xero(xero_contact_id):
    """Import a customer from Xero"""
    # Get Xero settings
    settings = frappe.get_single("Xero Settings")
    
    if not settings.tenant_id:
        frappe.throw("Xero tenant ID is required. Please connect to Xero first.")
    
    # Get access token
    token = get_valid_token()
    
    # Send to Xero
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Xero-Tenant-Id": settings.tenant_id
    }
    
    try:
        response = requests.get(
            f"https://api.xero.com/api.xro/2.0/Contacts/{xero_contact_id}",
            headers=headers,
            timeout=XERO_HTTP_TIMEOUT,
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("Contacts") and len(result["Contacts"]) > 0:
                contact = result["Contacts"][0]
                
                # Check if customer already exists
                existing = frappe.db.get_value("Customer", {"xero_contact_id": contact["ContactID"]})
                if existing:
                    frappe.throw(f"Customer already exists with Xero Contact ID: {contact['ContactID']}")
                
                # Create customer
                # customer_type is reqd on Customer with no default, so
                # leaving it out made insert() raise MandatoryError for every
                # contact Xero returned -- the import could never create one.
                # "Company" is the owner's rule for imported contacts
                # (review item rev_f9dce41f7f); it is one of the five Select
                # options and can be changed on the record afterwards.
                customer = frappe.get_doc({
                    "doctype": "Customer",
                    "customer_name": contact["Name"],
                    "customer_type": "Company",
                    "first_name": contact.get("FirstName", ""),
                    "last_name": contact.get("LastName", ""),
                    "email": contact.get("EmailAddress", ""),
                    "phone": contact.get("Phones", [{}])[0].get("PhoneNumber", "") if contact.get("Phones") else "",
                    "address_line1": contact.get("Addresses", [{}])[0].get("AddressLine1", "") if contact.get("Addresses") else "",
                    "address_line2": contact.get("Addresses", [{}])[0].get("AddressLine2", "") if contact.get("Addresses") else "",
                    "city": contact.get("Addresses", [{}])[0].get("City", "") if contact.get("Addresses") else "",
                    "state": contact.get("Addresses", [{}])[0].get("Region", "") if contact.get("Addresses") else "",
                    "postal_code": contact.get("Addresses", [{}])[0].get("PostalCode", "") if contact.get("Addresses") else "",
                    "country": contact.get("Addresses", [{}])[0].get("Country", "") if contact.get("Addresses") else "",
                    "xero_contact_id": contact["ContactID"],
                    "xero_sync_date": now_datetime()
                })
                customer.insert()
                
                return customer.name
            
            frappe.throw("Failed to get customer from Xero: No contact returned")
        
        error_msg = f"Failed to get customer from Xero: Status {response.status_code}"
        try:
            error_details = response.json()
            error_msg += f", Error: {json.dumps(error_details)}"
        except:
            if response.text:
                error_msg += f", Response: {response.text}"
        
        frappe.throw(error_msg)
    except Exception as e:
        frappe.throw(f"Error importing customer from Xero: {str(e)}")

def import_supplier_from_xero(xero_contact_id):
    """Import a supplier from Xero"""
    # Get Xero settings
    settings = frappe.get_single("Xero Settings")
    
    if not settings.tenant_id:
        frappe.throw("Xero tenant ID is required. Please connect to Xero first.")
    
    # Get access token
    token = get_valid_token()
    
    # Send to Xero
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Xero-Tenant-Id": settings.tenant_id
    }
    
    try:
        response = requests.get(
            f"https://api.xero.com/api.xro/2.0/Contacts/{xero_contact_id}",
            headers=headers,
            timeout=XERO_HTTP_TIMEOUT,
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("Contacts") and len(result["Contacts"]) > 0:
                contact = result["Contacts"][0]
                
                # Check if supplier already exists
                existing = frappe.db.get_value("Supplier", {"xero_contact_id": contact["ContactID"]})
                if existing:
                    frappe.throw(f"Supplier already exists with Xero Contact ID: {contact['ContactID']}")
                
                # Create supplier
                # supplier_type is reqd on Supplier with no default: same
                # MandatoryError, same rule. See import_customer_from_xero.
                supplier = frappe.get_doc({
                    "doctype": "Supplier",
                    "supplier_name": contact["Name"],
                    "supplier_type": "Company",
                    "first_name": contact.get("FirstName", ""),
                    "last_name": contact.get("LastName", ""),
                    "email": contact.get("EmailAddress", ""),
                    "phone": contact.get("Phones", [{}])[0].get("PhoneNumber", "") if contact.get("Phones") else "",
                    "address_line1": contact.get("Addresses", [{}])[0].get("AddressLine1", "") if contact.get("Addresses") else "",
                    "address_line2": contact.get("Addresses", [{}])[0].get("AddressLine2", "") if contact.get("Addresses") else "",
                    "city": contact.get("Addresses", [{}])[0].get("City", "") if contact.get("Addresses") else "",
                    "state": contact.get("Addresses", [{}])[0].get("Region", "") if contact.get("Addresses") else "",
                    "postal_code": contact.get("Addresses", [{}])[0].get("PostalCode", "") if contact.get("Addresses") else "",
                    "country": contact.get("Addresses", [{}])[0].get("Country", "") if contact.get("Addresses") else "",
                    "xero_contact_id": contact["ContactID"],
                    "xero_sync_date": now_datetime()
                })
                supplier.insert()
                
                return supplier.name
            
            frappe.throw("Failed to get supplier from Xero: No contact returned")
        
        error_msg = f"Failed to get supplier from Xero: Status {response.status_code}"
        try:
            error_details = response.json()
            error_msg += f", Error: {json.dumps(error_details)}"
        except:
            if response.text:
                error_msg += f", Response: {response.text}"
        
        frappe.throw(error_msg)
    except Exception as e:
        frappe.throw(f"Error importing supplier from Xero: {str(e)}")
