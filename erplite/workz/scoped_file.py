"""Protect Workz attachments on Frappe's direct File download path."""
from frappe.core.doctype.file.file import File
from erplite.workz.boundary import file_permission


def check_attachment(doc):
    file_permission(doc, ptype='read')
    # Frappe v15 chooses only the last installed File override. Compose both
    # policies explicitly so reverse installation order cannot erase a veto.
    try:
        from tm_office.access_boundary import record
    except ImportError:
        return
    record(doc, ptype='read')


class ScopedFile(File):
    def is_downloadable(self):
        check_attachment(self)
        return super().is_downloadable()

    def get_content(self):
        check_attachment(self)
        return super().get_content()
