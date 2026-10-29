"""Sources de mails : API Gmail (réelle) et boîte fictive (démonstration, tests)."""

from .base import MailSource, MessageTooLarge, RawAttachment

__all__ = ["MailSource", "MessageTooLarge", "RawAttachment"]
