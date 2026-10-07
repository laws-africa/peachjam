"""Lifecycle signals for Peachjam account deletion.

These are deliberately separate from Django's model deletion signals: deleting an
account anonymises its User rather than deleting the database row.
"""

from django.dispatch import Signal

user_account_pre_delete = Signal()
user_account_post_delete = Signal()
