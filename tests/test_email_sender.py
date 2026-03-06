import base64
import tempfile
import unittest
from email import policy
from email.parser import BytesParser
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app import email_sender


def _decode_raw_message(raw_value: str):
    msg_bytes = base64.urlsafe_b64decode(raw_value.encode())
    return BytesParser(policy=policy.default).parsebytes(msg_bytes)


class EmailSenderTests(unittest.TestCase):
    def setUp(self):
        self.mock_service = MagicMock()
        self.service_patch = patch.object(email_sender, "_get_gmail_service", return_value=self.mock_service)
        self.service_patch.start()
        self.addCleanup(self.service_patch.stop)

        self.settings_patch = patch.object(
            email_sender,
            "settings",
            SimpleNamespace(smtp_email="sender@example.com"),
        )
        self.settings_patch.start()
        self.addCleanup(self.settings_patch.stop)

    def _extract_sent_message(self):
        send_mock = self.mock_service.users.return_value.messages.return_value.send
        self.assertTrue(send_mock.called, "Gmail send() n'a pas ete appele")
        body = send_mock.call_args.kwargs["body"]
        return _decode_raw_message(body["raw"])

    def test_send_email_without_attachment(self):
        email_sender.send_candidature_email(
            to_email="dest@example.com",
            subject="Sujet test",
            lm_texte="Bonjour, ceci est une lettre.",
            cv_path=None,
        )

        sent = self._extract_sent_message()
        self.assertEqual(sent["From"], "sender@example.com")
        self.assertEqual(sent["To"], "dest@example.com")
        self.assertEqual(sent["Subject"], "Sujet test")

        text_parts = [p for p in sent.walk() if p.get_content_type() == "text/plain"]
        self.assertEqual(len(text_parts), 1)
        self.assertIn("Bonjour, ceci est une lettre.", text_parts[0].get_content())

        attachments = list(sent.iter_attachments())
        self.assertEqual(len(attachments), 0)

    def test_send_email_with_attachment_when_file_exists(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(b"%PDF-test-content")
            temp_path = Path(tmp.name)
        self.addCleanup(lambda: temp_path.unlink(missing_ok=True))

        email_sender.send_candidature_email(
            to_email="dest@example.com",
            subject="Sujet avec CV",
            lm_texte="Lettre",
            cv_path=str(temp_path),
        )

        sent = self._extract_sent_message()
        attachments = list(sent.iter_attachments())
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].get_filename(), temp_path.name)

    def test_send_email_uses_default_body_when_empty_lm(self):
        email_sender.send_candidature_email(
            to_email="dest@example.com",
            subject="Sujet vide",
            lm_texte="",
            cv_path=None,
        )

        sent = self._extract_sent_message()
        text_parts = [p for p in sent.walk() if p.get_content_type() == "text/plain"]
        self.assertEqual(len(text_parts), 1)
        self.assertIn("Aucune lettre de motivation", text_parts[0].get_content())


if __name__ == "__main__":
    unittest.main()
