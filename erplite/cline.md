# ERPLite Frappe App Overview

This document provides context for the `erplite` Frappe application, intended to help future development, bug fixing, and maintenance tasks.

## Application Structure

The `erplite` application is organized into several modules, each containing specific DocTypes to manage different aspects of a small business.

### Core Modules and Their DocTypes:

1.  **Accounts (`erplite/accounts/doctype`)**
    *   `Account`: Manages individual financial accounts.
    *   `Chart Of Accounts Root`: Defines the root for the chart of accounts.
    *   `Payment Entry`: Records payment transactions.
    *   `Purchase Invoice`: Manages invoices received from suppliers.
    *   `Purchase Invoice Item`: Line items for Purchase Invoices.
    *   `Sales Invoice`: Manages invoices issued to customers.
    *   `Sales Invoice Item`: Line items for Sales Invoices.
    *   `Xero Account`: Represents Xero accounts for integration.
    *   `Xero Invoice`: Represents Xero invoices for integration.

2.  **CRM (`erplite/crm/doctype`)**
    *   `Customer`: Manages customer information and interactions.
    *   `Supplier`: Manages supplier information and interactions.

3.  **Projects (`erplite/projects/doctype`)**
    *   `Trip`: Manages details related to trips (likely for business travel or deliveries).
    *   `Zabbix Import`: Manages data import from Zabbix monitoring system.

4.  **Setup (`erplite/setup/doctype`)**
    *   `Company`: Stores company details and configurations.
    *   `Currency`: Manages different currencies used in transactions.
    *   `Finance Book`: Defines financial books for accounting.
    *   `Fiscal Year`: Manages fiscal year periods.
    *   `Holiday`: Defines holidays.
    *   `Holiday List`: Manages lists of holidays.
    *   `Terms and Conditions`: Manages standard terms and conditions for documents.
    *   `Xero Settings`: Configuration for Xero integration.
    *   `Xero Sync Log`: Logs synchronization activities with Xero.

### Key Integrations:

*   **Xero Integration (`erplite/xero/`)**:
    *   The application includes a dedicated `xero` module (`erplite/xero/`) containing logic for authentication (`auth.py`), API interaction (`api.py`, `client.py`), and account management (`accounts.py`).
    *   Related DocTypes like `Xero Account`, `Xero Invoice` (in Accounts), and `Xero Settings`, `Xero Sync Log` (in Setup) support this integration.

### Other Notable Files/Directories:

*   **`hooks.py`**: Contains Frappe hooks for customizing app behavior.
*   **`modules.txt`**: Lists the modules included in the app.
*   **`public/`**: Likely contains static assets.
*   **`templates/`**: Contains Jinja templates for web pages and views.
*   **`www/`**: For public-facing web pages.

## Development Context

When working on `erplite`:
*   Be mindful of the relationships between DocTypes, especially child tables like `Sales Invoice Item` and `Purchase Invoice Item`.
*   Changes to Xero-related DocTypes or logic should be tested thoroughly against the Xero API documentation and integration points.
*   Review relevant `.js` and `.py` files for client-side and server-side customizations associated with each DocType.
*   The `patches.txt` file might contain information about database schema migrations applied to the app.

This `cline.md` file should serve as a starting point for understanding the `erplite` application. It can be expanded with more detailed information as the application evolves.
