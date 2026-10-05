app_name = "erplite"
app_title = "Erplite"
app_publisher = "TierneyMorris"
app_description = "Simpler ERP for services company"
app_email = "support@tierneymorris.com.au"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
add_to_apps_screen = [
	{
		"name": "erplite",
		"logo": "/assets/erplite/images/toolbox.png",
		"title": "Desk",
		"route": "/app",
		"has_permission": "erplite.check_app_permission"
	}
]



# Website route rules for Vue.js frontend
website_route_rules = [
	{"from_route": "/erplite/<path:app_path>", "to_route": "erplite"},
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# No global app_include_css: the timesheet-calendar stylesheet it used to name was deleted
# along with the rest of that feature in 8126278, and a missing /assets path is served as a 404
# on every desk page (twice -- once for the <link> tag and once for the rel=preload header that
# frappe.utils.jinja_globals.include_style adds). Pages that need a stylesheet link it
# themselves, as erplite/www/todo/index.html does with app_navigation.css.
# app_include_js = "/assets/erplite/js/timesheet-calendar.js"  # Removed global include - now loaded only on timesheet calendar page

# include js, css files in header of web template
# web_include_css = "/assets/erplite/css/erplite.css"
# web_include_js = "/assets/erplite/js/erplite.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "erplite/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "erplite/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "erplite.utils.jinja_methods",
# 	"filters": "erplite.utils.jinja_filters"
# }

# Installation
# ------------

fixtures = [
	"Workspace"
]

# before_install = "erplite.install.before_install"
# after_install = "erplite.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "erplite.uninstall.before_uninstall"
# after_uninstall = "erplite.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "erplite.utils.before_app_install"
# after_app_install = "erplite.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "erplite.utils.before_app_uninstall"
# after_app_uninstall = "erplite.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "erplite.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"erplite.tasks.all"
# 	],
# 	"daily": [
# 		"erplite.tasks.daily"
# 	],
# 	"hourly": [
# 		"erplite.tasks.hourly"
# 	],
# 	"weekly": [
# 		"erplite.tasks.weekly"
# 	],
# 	"monthly": [
# 		"erplite.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "erplite.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "erplite.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "erplite.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["erplite.utils.before_request"]
# after_request = ["erplite.utils.after_request"]

# Job Events
# ----------
# before_job = ["erplite.utils.before_job"]
# after_job = ["erplite.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"erplite.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }
