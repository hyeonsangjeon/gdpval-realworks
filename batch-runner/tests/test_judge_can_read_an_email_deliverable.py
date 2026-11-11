"""An email saved as ``.eml`` is read the way a mail client shows it.

Before this, ``_kind_of`` sniffed an ``.eml`` as text and ``read_content``
returned the raw MIME source. For exp036 task 02aa1805 that was 26,449
characters: the 1,927-character message, interleaved with 50 quoted-printable
soft line breaks that split words and well IDs ("Farme=\\nr City",
"WL4=\\n7646") and 53 ``=XX`` escapes, then the HTML alternative, then about
20,000 characters of base64 -- the attached workbook the rubric asks about,
which no op could open.

Now the message is decoded into its headers, its text body and a list of
attachments, and an attachment opens through the same ``member`` scope an
archive member does. Only ``.eml`` files are affected. Nothing here calls a
model.
"""

from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path
import sys

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.tools import has_extractable_text  # noqa: E402
from core.tools.read_deliverable import _kind_of, read_deliverable  # noqa: E402

LONG_LINE = (
    "Seven wells meet all three criteria; I recommend advancing Farmer City "
    "WL47648 and Farmer City WL47646 first, with Weldon WL45047 as the leading "
    "secondary option — pumpage is a prioritisation signal only."
)
CSV_BYTES = b"Water system,Well ID,Depth\nFarmer City,WL47648,188\nWeldon,WL45047,167\n"


@pytest.fixture()
def base_dir(tmp_path: Path) -> Path:
    root = tmp_path / "deliverables"
    root.mkdir()
    return root


def _write_email(base_dir: Path, *, html=True, plain=True, attach=True, name="Email.eml") -> str:
    message = EmailMessage()
    message["From"] = "Senior Project Manager <spm@example.com>"
    message["To"] = "Manager <manager@example.com>"
    message["Subject"] = "Recommendation: Illinois water-well screen"
    if plain:
        message.set_content("Hi,\n\n" + LONG_LINE + "\n\nBest regards,\nSenior Project Manager\n", cte="quoted-printable")
        if html:
            message.add_alternative(
                "<html><head><style>p{color:red}</style></head><body>"
                "<p>Hi,</p><ul><li>Farmer City WL47648</li><li>Weldon WL45047</li></ul>"
                "</body></html>",
                subtype="html",
            )
    else:
        message.set_content(
            "<html><body><p>Hi,</p><p>" + LONG_LINE + "</p>"
            "<ol><li>Farmer City WL47648</li><li>Weldon WL45047</li></ol></body></html>",
            subtype="html",
        )
    if attach:
        message.add_attachment(CSV_BYTES, maintype="text", subtype="csv", filename="wells.csv")
    (base_dir / name).write_bytes(bytes(message))
    return name


def test_read_content_returns_the_decoded_message_not_the_mime_source(base_dir):
    name = _write_email(base_dir)
    raw = (base_dir / name).read_text()
    assert "=\n" in raw or "=E2=80=94" in raw  # the source really is quoted-printable

    result = read_deliverable("read_content", name, base_dir=str(base_dir))

    assert result["ok"] is True
    data = result["data"]
    assert data["kind"] == "email"
    text = data["text"]
    assert "From: Senior Project Manager <spm@example.com>" in text
    assert "Subject: Recommendation: Illinois water-well screen" in text
    assert LONG_LINE in text  # one unbroken line, the em dash decoded
    for mime_noise in ("=\n", "=E2=80=94", "Content-Transfer-Encoding", "boundary="):
        assert mime_noise not in text
    assert "[Attachments: 1]" in text
    assert "wells.csv | csv | %d bytes" % len(CSV_BYTES) in text
    assert 'scope={"member": "<name>"}' in text
    assert "HTML rendering of this body" in text


def test_an_html_only_message_is_read_as_its_visible_text(base_dir):
    name = _write_email(base_dir, plain=False, attach=False)

    text = read_deliverable("read_content", name, base_dir=str(base_dir))["data"]["text"]

    assert LONG_LINE in text
    assert "- Farmer City WL47648" in text
    assert "<p>" not in text and "color:red" not in text
    assert "[Attachments: 0]" in text


def test_an_attachment_opens_like_an_archive_member(base_dir):
    name = _write_email(base_dir)

    result = read_deliverable("read_content", name, base_dir=str(base_dir), scope={"member": "wells.csv"})

    assert result["ok"] is True
    assert result["data"]["kind"] == "csv"
    assert result["data"]["text"] == CSV_BYTES.decode()


def test_an_attachment_that_is_not_in_the_message_is_refused_by_name(base_dir):
    name = _write_email(base_dir)

    result = read_deliverable("read_content", name, base_dir=str(base_dir), scope={"member": "../../etc/passwd"})

    assert result["ok"] is False
    assert result["error_type"] == "bad_scope"
    assert "wells.csv" in result["error"]


def test_an_attachment_name_cannot_point_outside_the_message(base_dir):
    message = EmailMessage()
    message["Subject"] = "names"
    message.set_content("body\n")
    message.add_attachment(CSV_BYTES, maintype="text", subtype="csv", filename="../../evil.csv")
    message.add_attachment(b"x", maintype="application", subtype="octet-stream", filename="..")
    (base_dir / "names.eml").write_bytes(bytes(message))

    data = read_deliverable("inspect_structure", "names.eml", base_dir=str(base_dir))["data"]
    assert [row["name"] for row in data["attachments"]] == ["evil.csv", "attachment"]
    opened = read_deliverable("read_content", "names.eml", base_dir=str(base_dir), scope={"member": "evil.csv"})
    assert opened["ok"] is True
    assert opened["data"]["text"] == CSV_BYTES.decode()


def test_the_member_scope_on_any_other_kind_keeps_its_old_refusal(base_dir):
    (base_dir / "notes.txt").write_text("plain notes\n")

    result = read_deliverable("read_content", "notes.txt", base_dir=str(base_dir), scope={"member": "x"})

    assert result == {
        "ok": False,
        "error": "scope key 'member' is only valid on a zip archive, not on a txt file",
        "error_type": "bad_scope",
    }


def test_structure_lists_the_headers_and_the_attachments(base_dir):
    name = _write_email(base_dir)

    data = read_deliverable("inspect_structure", name, base_dir=str(base_dir))["data"]

    assert data["kind"] == "email"
    assert data["headers"]["To"] == "Manager <manager@example.com>"
    assert data["body_content_type"] == "text/plain"
    assert data["attachments"] == [
        {"name": "wells.csv", "content_type": "text/csv", "kind": "csv", "size": len(CSV_BYTES)}
    ]


def test_an_email_is_named_by_its_extension_and_has_text(base_dir):
    name = _write_email(base_dir)

    assert _kind_of(base_dir / name) == "email"
    assert has_extractable_text(base_dir / name) is True


def test_a_content_scope_key_is_refused_on_an_email(base_dir):
    name = _write_email(base_dir)

    result = read_deliverable("read_content", name, base_dir=str(base_dir), scope={"sheet": "Sheet1"})

    assert result["ok"] is False
    assert result["error_type"] == "bad_scope"
