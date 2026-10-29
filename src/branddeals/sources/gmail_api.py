"""Source réelle : API Gmail officielle de Google.

Droits demandés : lecture seule + gestion des libellés. Le pipeline ne peut ni envoyer,
ni supprimer, ni archiver : c'est garanti par les droits OAuth eux-mêmes, pas seulement par le code.

Installation : pip install -e ".[gmail]"
"""

from __future__ import annotations

import base64
import random
import time
from collections.abc import Iterator
from datetime import datetime, timezone
from email.utils import getaddresses
from pathlib import Path

from ..models import Message, Thread
from .base import MessageTooLarge, RawAttachment

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.labels",
    "https://www.googleapis.com/auth/gmail.modify",  # uniquement pour poser des libellés
]


def _with_retry(call, attempts: int = 6):
    """Gmail limite le nombre d'appels par minute : on réessaie avec une attente croissante."""
    from googleapiclient.errors import HttpError

    for i in range(attempts):
        try:
            return call.execute()
        except HttpError as err:  # pragma: no cover - dépend du réseau
            if err.resp.status not in (429, 500, 503) or i == attempts - 1:
                raise
            time.sleep(min(60, 2**i) + random.random())
    return None  # pragma: no cover


class GmailSource:
    def __init__(self, credentials_file: str | Path, token_file: str | Path = "token.json",
                 max_message_bytes: int = 6_500_000):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        token_file = Path(token_file)
        creds = Credentials.from_authorized_user_file(token_file, SCOPES) if token_file.exists() else None
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                creds = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES).run_local_server(port=0)
            token_file.write_text(creds.to_json(), encoding="utf-8")
        self.svc = build("gmail", "v1", credentials=creds, cache_discovery=False)
        self.max_message_bytes = max_message_bytes
        self._labels: dict[str, str] | None = None

    # -- lecture -----------------------------------------------------------------------------
    def search(self, query: str) -> Iterator[str]:
        token = None
        while True:
            resp = _with_retry(self.svc.users().threads().list(userId="me", q=query, pageToken=token, maxResults=100))
            for t in resp.get("threads", []):
                yield t["id"]
            token = resp.get("nextPageToken")
            if not token:
                return

    def get_thread(self, thread_id: str) -> Thread:
        resp = _with_retry(self.svc.users().threads().get(userId="me", id=thread_id, format="full"))
        return Thread(id=thread_id, messages=[_parse_message(m) for m in resp.get("messages", [])])

    def get_attachments(self, message_id: str) -> list[RawAttachment]:
        msg = _with_retry(self.svc.users().messages().get(userId="me", id=message_id, format="full"))
        if int(msg.get("sizeEstimate", 0)) > self.max_message_bytes:
            raise MessageTooLarge(message_id)
        out = []
        for part in _walk(msg.get("payload", {})):
            body, name = part.get("body", {}), part.get("filename")
            if not name or not body.get("attachmentId"):
                continue
            att = _with_retry(self.svc.users().messages().attachments().get(
                userId="me", messageId=message_id, id=body["attachmentId"]))
            out.append(RawAttachment(name, part.get("mimeType", ""), base64.urlsafe_b64decode(att["data"])))
        return out

    # -- seule écriture : les libellés --------------------------------------------------------
    def add_label(self, thread_id: str, label: str) -> None:
        label_id = self._label_id(label)
        _with_retry(self.svc.users().threads().modify(userId="me", id=thread_id, body={"addLabelIds": [label_id]}))

    def _label_id(self, name: str) -> str:
        if self._labels is None:
            resp = _with_retry(self.svc.users().labels().list(userId="me"))
            self._labels = {lb["name"]: lb["id"] for lb in resp.get("labels", [])}
        if name not in self._labels:
            created = _with_retry(self.svc.users().labels().create(userId="me", body={"name": name}))
            self._labels[name] = created["id"]
        return self._labels[name]


def _walk(part: dict) -> Iterator[dict]:
    yield part
    for sub in part.get("parts", []) or []:
        yield from _walk(sub)


def _parse_message(m: dict) -> Message:
    headers = {h["name"].lower(): h["value"] for h in m.get("payload", {}).get("headers", [])}
    sender = getaddresses([headers.get("from", "")])[0][1].lower()
    recipients = tuple(a.lower() for _, a in getaddresses([headers.get("to", ""), headers.get("cc", "")]) if a)
    body = ""
    for part in _walk(m.get("payload", {})):
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", "replace")
            break
    sent = datetime.fromtimestamp(int(m.get("internalDate", 0)) / 1000, tz=timezone.utc).date()
    names = tuple(p["filename"] for p in _walk(m.get("payload", {})) if p.get("filename"))
    return Message(id=m["id"], thread_id=m["threadId"], sender=sender, recipients=recipients, sent_at=sent,
                   subject=headers.get("subject", ""), body=body, size_bytes=int(m.get("sizeEstimate", 0)),
                   attachment_names=names)
