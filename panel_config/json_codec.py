"""Canonical UTF-8 encoding shared by HA drafts and the host runtime tools."""

import json


def encode_document(document):
    """Arrays define order; this is not an RFC 8785/numeric migration codec."""
    try:
        return json.dumps(document, ensure_ascii=False, allow_nan=False, sort_keys=True,
                          separators=(",", ":")).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        raise ValueError("Configuration must contain finite, valid UTF-8 JSON values") from error
