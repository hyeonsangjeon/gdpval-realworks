"""Plan-first intake of one explicit, private GitHub draft-release asset.

This is not a release publisher, credential discovery tool or model launcher.
The workflow must validate its reviewed source/cell before calling input-check.
Draft visibility is observed at metadata read time, not guaranteed permanently.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from enum import Enum
import http.client
import logging
import os
from pathlib import Path
import re
import sys
import tarfile
import time
from typing import Any, Iterator
import urllib.error
import urllib.parse
import urllib.request

import yaml

import codex_ci_input_bundle as bundle

REPOSITORY = "hyeonsangjeon/gdpval-realworks"
API_ROOT = "https://api.github.com/repos/" + REPOSITORY + "/releases/"
BUNDLE_SIZE = 2519040
BUNDLE_SHA256 = "757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3"
MAX_METADATA_BYTES = 256 * 1024
MAX_ASSETS = 100
REQUEST_TIMEOUT_SECONDS = 30
TRANSFER_TIMEOUT_SECONDS = 120
ASSET_TYPES = {"application/octet-stream", "application/x-tar"}
LOG = logging.getLogger(__name__)


class GitHubStage(Enum):
    RELEASE_METADATA = "release_metadata"
    ASSET_DOWNLOAD = "asset_download"
    ASSET_REDIRECT = "asset_redirect"


class InputIntakeRefused(ValueError):
    """Closed reason/context; never contains a URL, response body or path."""

    def __init__(self, reason: str, *, stage: GitHubStage | None = None,
                 http_status: int | None = None) -> None:
        super().__init__(reason)
        self.stage = GitHubStage(stage) if stage is not None else None
        self.http_status = http_status if type(http_status) is int else None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: urllib.request.Request, fp: Any, code: int,
                         msg: str, headers: Any, newurl: str) -> None:
        return None


def _positive_id(value: str | None) -> int:
    if (type(value) is not str or re.fullmatch(r"[1-9][0-9]{0,18}", value) is None
            or int(value) > 2**63 - 1):
        raise InputIntakeRefused("positive_explicit_release_and_asset_ids_required")
    return int(value)


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise InputIntakeRefused("github_transfer_time_limit_exceeded")
    return min(REQUEST_TIMEOUT_SECONDS, remaining)


@contextmanager
def _response(opener: Any, url: str, *, token: str | None, accept: str, deadline: float,
              stage: GitHubStage) -> Iterator[Any]:
    # Callers construct only the exact API paths or validate the sole CDN hop.
    # No ambient proxy, auth handler, cookie jar or redirect-following opener.
    headers = {"Accept": accept, "Accept-Encoding": "identity", "User-Agent": "gdpval-private-input-intake"}
    if token is not None:
        headers.update({"Authorization": "Bearer " + token, "X-GitHub-Api-Version": "2022-11-28"})
    request = urllib.request.Request(url, headers=headers, method="GET")
    status = None
    try:
        try:
            response = opener.open(request, timeout=_remaining(deadline))
        except urllib.error.HTTPError as error:
            # HTTPError is also a closable response. Do not read/log its error body.
            response = error
        with response:
            status = response.status
            yield response
    except (OSError, ValueError, TypeError, KeyError, AttributeError, StopIteration, RecursionError,
            http.client.HTTPException) as error:
        reason = str(error) if isinstance(error, InputIntakeRefused) else "private_input_verification_or_transport_failed"
        # Only the fixed call-site stage and a received numeric status survive.
        # An open failure has no response, even after an earlier successful hop.
        raise InputIntakeRefused(reason, stage=stage, http_status=status) from None


def _header(response: Any, name: str) -> str | None:
    values = response.headers.get_all(name, [])
    if len(values) > 1:
        raise InputIntakeRefused("github_duplicate_response_header")
    return values[0] if values else None


def _body(response: Any, *, limit: int, types: set[str], deadline: float, exact: bool = False) -> bytes:
    if _header(response, "Content-Encoding") not in (None, "identity"):
        raise InputIntakeRefused("github_encoded_response_refused")
    content_type = (_header(response, "Content-Type") or "").split(";", 1)[0].lower().strip()
    if content_type not in types:
        raise InputIntakeRefused("github_response_content_type_refused")
    length = _header(response, "Content-Length")
    if (length is not None and (re.fullmatch(r"[0-9]{1,10}", length) is None or int(length) > limit)
            or exact and (length is None or int(length) != limit)):
        raise InputIntakeRefused("github_response_size_refused")
    payload = bytearray()
    while True:
        _remaining(deadline)
        # read1 makes at most one underlying read, unlike a fill-until-n read.
        # The workflow additionally enforces an owned CLI wall-time ceiling.
        block = response.read1(min(65536, limit + 1 - len(payload)))
        _remaining(deadline)
        if not block:
            break
        payload.extend(block)
        if len(payload) > limit:
            raise InputIntakeRefused("github_response_size_refused")
    if ((length is not None and len(payload) != int(length)) or (exact and len(payload) != limit)):
        raise InputIntakeRefused("github_response_size_refused")
    return bytes(payload)


def _require_success(response: Any) -> None:
    if response.status in (401, 403, 404):
        # This does not diagnose permission, token validity or resource absence.
        raise InputIntakeRefused("github_draft_or_asset_inaccessible")
    if response.status != 200:
        raise InputIntakeRefused("github_response_status_refused")


def _asset_metadata(opener: Any, release_id: int, asset_id: int, token: str, deadline: float) -> str:
    release_url, asset_url = API_ROOT + str(release_id), API_ROOT + "assets/" + str(asset_id)
    with _response(opener, release_url, token=token, accept="application/vnd.github+json", deadline=deadline,
                   stage=GitHubStage.RELEASE_METADATA) as response:
        if response.geturl() != release_url or 300 <= response.status < 400:
            raise InputIntakeRefused("github_release_metadata_redirect_refused")
        _require_success(response)
        release = bundle._json_object(_body(response, limit=MAX_METADATA_BYTES, types={"application/json"}, deadline=deadline))
    if (release.get("url") != release_url or type(release.get("id")) is not int
            or release["id"] != release_id):
        raise InputIntakeRefused("github_release_ownership_or_identity_refused")
    if release.get("draft") is not True:
        raise InputIntakeRefused("github_release_must_remain_private_draft")
    assets = release.get("assets")
    if (type(assets) is not list or len(assets) > MAX_ASSETS
            or any(type(asset) is not dict or type(asset.get("id")) is not int for asset in assets)):
        raise InputIntakeRefused("github_release_assets_shape_or_limit_refused")
    matches = [asset for asset in assets if asset["id"] == asset_id]
    if len(matches) != 1:
        raise InputIntakeRefused("github_selected_asset_membership_refused")
    asset = matches[0]
    if asset.get("url") != asset_url or asset.get("state") != "uploaded":
        raise InputIntakeRefused("github_asset_ownership_or_state_refused")
    if (type(asset.get("size")) is not int or asset["size"] != BUNDLE_SIZE
            or asset.get("content_type") not in ASSET_TYPES
            or type(asset.get("name")) is not str
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", asset["name"]) is None):
        raise InputIntakeRefused("github_asset_file_type_or_size_refused")
    # Neither browser_download_url nor a metadata digest is a trust anchor.
    return asset_url


def _asset_redirect(location: str | None) -> str:
    if (type(location) is not str or len(location) > 8192
            or any(ord(char) < 33 or ord(char) > 126 for char in location)):
        raise InputIntakeRefused("github_asset_redirect_target_refused")
    parsed = urllib.parse.urlsplit(location)
    if (parsed.scheme != "https" or parsed.netloc != "release-assets.githubusercontent.com"
            or parsed.fragment or not parsed.query
            or re.fullmatch(r"/github-production-release-asset/[1-9][0-9]*/[0-9a-f-]{36}", parsed.path) is None):
        raise InputIntakeRefused("github_asset_redirect_target_refused")
    return location


def _download(opener: Any, asset_url: str, token: str, deadline: float) -> bytes:
    with _response(opener, asset_url, token=token, accept="application/octet-stream", deadline=deadline,
                   stage=GitHubStage.ASSET_DOWNLOAD) as response:
        if response.geturl() != asset_url:
            raise InputIntakeRefused("github_automatic_redirect_refused")
        if response.status not in (302, 307):
            _require_success(response)
            return _body(response, limit=BUNDLE_SIZE, types=ASSET_TYPES, deadline=deadline, exact=True)
        target = _asset_redirect(_header(response, "Location"))
    # Exactly one allowlisted hop. Fresh headers contain no Authorization,
    # cookies, Referer, GitHub API headers or credential-bearing input values.
    with _response(opener, target, token=None, accept="application/octet-stream", deadline=deadline,
                   stage=GitHubStage.ASSET_REDIRECT) as response:
        if response.geturl() != target or 300 <= response.status < 400:
            raise InputIntakeRefused("github_additional_asset_redirect_refused")
        _require_success(response)
        return _body(response, limit=BUNDLE_SIZE, types=ASSET_TYPES, deadline=deadline, exact=True)


def intake(*, release_id: str | None, asset_id: str | None, expected_sha256: str | None,
           bundle_out: Path, output: Path, transport: bundle.LocalTransport,
           _test_github: Any = None) -> dict:
    """Verify one selected private draft asset, then use the genuine importer.

    No network retry, published fallback, original regeneration or overwrite is
    available. A failed reservation/partial import is retained and not adopted.
    """
    release, asset = _positive_id(release_id), _positive_id(asset_id)
    if (type(expected_sha256) is not str or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None
            or expected_sha256 != BUNDLE_SHA256):
        raise InputIntakeRefused("registered_external_bundle_sha256_required")
    if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY:
        raise InputIntakeRefused("same_repository_input_intake_required")
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token or len(token) > 4096 or any(ord(char) < 33 or ord(char) > 126 for char in token):
        raise InputIntakeRefused("existing_github_read_token_required")
    bundle_out, reservation = bundle._destination(bundle_out, (output,))
    output, output_reservation = bundle._destination(output, (bundle_out,))
    with (bundle._held_parents(bundle_out.parent, (bundle_out.name, reservation.name)) as check,
          bundle._held_parents(output.parent, (output.name, output_reservation.name)) as check_output):
        bundle._destination(bundle_out, (output,))
        bundle._destination(output, (bundle_out,))
        bundle._write_no_clobber(reservation, bundle._canonical_json({
            "operation": "private_draft_intake", "repository": REPOSITORY,
            "release_id": release, "asset_id": asset,
            "bundle": {"size": BUNDLE_SIZE, "sha256": expected_sha256},
        }).encode())
        opener = _test_github if _test_github is not None else urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect())
        deadline = time.monotonic() + TRANSFER_TIMEOUT_SECONDS
        asset_url = _asset_metadata(opener, release, asset, token, deadline)
        archive = _download(opener, asset_url, token, deadline)
        if bundle._identity(archive) != {"size": BUNDLE_SIZE, "sha256": expected_sha256}:
            raise InputIntakeRefused("external_bundle_digest_mismatch")
        check()
        check_output()
        bundle._destination(output, (bundle_out,))
        # No payload file exists until the bounded response and external SHA pass.
        bundle._write_no_clobber(bundle_out, archive)
        check()
        report = bundle.import_bundle(bundle=bundle_out, expected_sha256=expected_sha256,
                                      output=output, transport=transport)
        check()
        check_output()
    return {"mode": "input_check", "repository": REPOSITORY, "release_id": release, "asset_id": asset,
            "bundle": report["bundle"], "original_inputs_verified": True,
            "draft_observed_at_metadata_read": True, "publication_authorized": False,
            "oidc_requested": False, "model_requested": False}


def main(argv: list[str] | None = None, *, _test_github: Any = None,
         _test_transport: bundle.LocalTransport | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-check", action="store_true", help="Explicit private intake only; no OIDC or model")
    parser.add_argument("--release-id")
    parser.add_argument("--asset-id")
    parser.add_argument("--expected-sha256")
    parser.add_argument("--bundle-out", type=Path, help="New absent private staging file outside source")
    parser.add_argument("--out", type=Path, help="New absent private root for the exact original roles")
    args = parser.parse_args(argv)
    try:
        if not args.input_check:
            report = {"mode": "plan_only", "transfer_attempted": False, "draft_access": "not_observed",
                      "oidc_requested": False, "model_requested": False}
        else:
            if args.bundle_out is None or args.out is None:
                raise InputIntakeRefused("explicit_private_staging_and_input_destinations_required")
            report = intake(release_id=args.release_id, asset_id=args.asset_id, expected_sha256=args.expected_sha256,
                            bundle_out=args.bundle_out, output=args.out,
                            transport=_test_transport or bundle.LocalTransport(), _test_github=_test_github)
        sys.stdout.write(bundle._canonical_json(report) + "\n")
        return 0
    except KeyboardInterrupt:
        LOG.error("Private input intake refused: interrupted_reservation_retained")
        return 130
    except (OSError, ValueError, TypeError, KeyError, AttributeError, StopIteration, RecursionError,
            http.client.HTTPException, tarfile.TarError, yaml.YAMLError) as error:
        reason = str(error) if isinstance(error, InputIntakeRefused) else "private_input_verification_or_transport_failed"
        if isinstance(error, InputIntakeRefused) and error.stage is not None:
            LOG.error("Private input intake refused: %s (stage=%s, http_status=%s)",
                      reason, error.stage.value, error.http_status if error.http_status is not None else "null")
        else:
            LOG.error("Private input intake refused: %s", reason)
        return 2


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
