"""Optional subscription lifecycle policies supplied by installed apps."""

from django.dispatch import Signal

# Receivers get ``subscription`` and return a blocking message or None.
subscription_activation_check = Signal()
