"""Contrat commun à toutes les sources de mails.

Le pipeline ne connaît que cette interface : on peut le brancher sur l'API Gmail,
sur une boîte fictive pour la démonstration, ou demain sur une autre messagerie.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol

from ..models import Thread


@dataclass(frozen=True)
class RawAttachment:
    filename: str
    mime_type: str
    content: bytes


class MessageTooLarge(Exception):
    """Le message dépasse la taille téléchargeable : il sera listé pour récupération manuelle."""


class MailSource(Protocol):
    def search(self, query: str) -> Iterator[str]:
        """Renvoie les identifiants de conversations qui répondent à une recherche, page après page."""

    def get_thread(self, thread_id: str) -> Thread:
        """Renvoie une conversation complète (métadonnées et texte, sans pièces jointes)."""

    def get_attachments(self, message_id: str) -> list[RawAttachment]:
        """Télécharge les pièces jointes d'un message. Lève MessageTooLarge si nécessaire."""

    def add_label(self, thread_id: str, label: str) -> None:
        """Pose un libellé sur une conversation (seule écriture autorisée dans la boîte)."""
