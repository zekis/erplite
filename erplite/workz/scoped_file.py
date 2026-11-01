"""Protect Workz attachments on Frappe's direct File download path."""
from frappe.core.doctype.file.file import File
from erplite.workz.boundary import file_permission, private_attachment


def check_attachment(doc):
    file_permission(doc, ptype='read')
    # Frappe v15 chooses only the last installed File override. Compose both
    # policies explicitly so reverse installation order cannot erase a veto.
    try:
        from tm_office.access_boundary import record
    except ImportError:
        return
    record(doc, ptype='read')


def check_visibility(doc):
    private_attachment(doc)
    try:
        from tm_office.access_boundary import private_attachment as office_private
    except ImportError:
        return
    office_private(doc)


class ScopedFile(File):
    def before_insert(self):
        check_visibility(self)
        return super().before_insert()

    def validate(self):
        check_visibility(self)
        return super().validate()

    def is_downloadable(self):
        check_attachment(self)
        return super().is_downloadable()

    def get_content(self):
        check_attachment(self)
        return super().get_content()
