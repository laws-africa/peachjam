"""Lifecycle signals for Peachjam accounts.

These are deliberately separate from Django's model deletion signals: deleting an
account anonymises its User rather than deleting the database row.
"""

from django.dispatch import Signal

user_account_pre_delete = Signal()
user_account_post_delete = Signal()

# Sent before signup analytics, including accounts created through email codes.
account_created = Signal()
