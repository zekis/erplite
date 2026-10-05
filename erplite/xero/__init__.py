# -*- coding: utf-8 -*-
# Copyright (c) 2023, ERPLite and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

# (connect, read) timeout for every Xero HTTP call in this package.
# `requests` has no default timeout, so without this a call can hang for as
# long as the socket stays open. That matters most on the invoice POST: the
# invoice is created in Xero before we learn the outcome, so a reply we never
# wait for is indistinguishable from a send that did not happen.
XERO_HTTP_TIMEOUT = (10, 60)
