# functions/tweet.py
from __future__ import annotations

import logging
from typing import Optional

import requests
from django.conf import settings
from requests_oauthlib import OAuth1

logger = logging.getLogger(__name__)

TW_V2_TWEETS = "https://api.twitter.com/2/tweets"
TW_V11_UPLOAD = "https://upload.twitter.com/1.1/media/upload.json"


class _NoOpTweetClient:
    """
    Safe default client:
    - Never hits the network.
    - Always 'succeeds' and logs the tweet text (and media path if provided).
    """
    enabled = False

    def make_tweet(self, *, text: str, media_path: Optional[str] = None) -> bool:
        logger.info("[Tweet:DISABLED] %s", text)
        if media_path:
            logger.info("[Tweet:DISABLED] media_path=%s", media_path)
        return True


class _TwitterClient:
    """
    Minimal Twitter client:
    - Uses OAuth1 user context.
    - Media upload via v1.1, then tweet create via v2.
    """
    def __init__(self) -> None:
        self.api_key = getattr(settings, "TWITTER_API_KEY", None)
        self.api_secret = getattr(settings, "TWITTER_API_SECRET", None)
        self.access_token = getattr(settings, "TWITTER_ACCESS_TOKEN", None)
        self.access_secret = getattr(settings, "TWITTER_ACCESS_TOKEN_SECRET", None)
        self.enabled = all([self.api_key, self.api_secret, self.access_token, self.access_secret])

        if not self.enabled:
            raise RuntimeError("Twitter client misconfigured: missing credentials")

        self.auth = OAuth1(
            self.api_key,
            self.api_secret,
            self.access_token,
            self.access_secret,
            signature_type="auth_header",
        )

    def _upload_media(self, media_path: str) -> Optional[str]:
        try:
            with open(media_path, "rb") as f:
                files = {"media": f}
                r = requests.post(TW_V11_UPLOAD, auth=self.auth, files=files, timeout=15)
            if r.status_code != 200:
                logger.warning("Twitter media upload failed: %s %s", r.status_code, r.text)
                return None
            media_id = r.json().get("media_id_string")
            return media_id
        except Exception as exc:
            logger.exception("Twitter media upload exception: %s", exc)
            return None

    def make_tweet(self, *, text: str, media_path: Optional[str] = None) -> bool:
        if not self.enabled:
            logger.info("[Tweet:DISABLED via client] %s", text)
            return True

        payload = {"text": text}
        if media_path:
            media_id = self._upload_media(media_path)
            if media_id:
                payload["media"] = {"media_ids": [media_id]}

        try:
            r = requests.post(TW_V2_TWEETS, auth=self.auth, json=payload, timeout=15)
            if r.status_code not in (200, 201):
                logger.warning("Twitter create tweet failed: %s %s", r.status_code, r.text)
                return False
            return True
        except Exception as exc:
            logger.exception("Twitter create tweet exception: %s", exc)
            return False


# ----- Public API --------------------------------------------------------------

_client_singleton = None

def _tweeting_globally_enabled() -> bool:
    """
    Feature flag:
    - Prefer TWITTER_ENABLED if present.
    - Fallback to TWEET_ENABLED for convenience with project flags.
    """
    if hasattr(settings, "TWITTER_ENABLED"):
        return bool(getattr(settings, "TWITTER_ENABLED"))
    return bool(getattr(settings, "TWEET_ENABLED", False))


def get_tweet_client():
    """
    Returns a client exposing .make_tweet(text, media_path=None) -> bool.
    - If globally disabled, returns a no-op client.
    - If enabled but creds are missing, logs warning and still returns no-op.
    """
    global _client_singleton
    if _client_singleton is not None:
        return _client_singleton

    if not _tweeting_globally_enabled():
        _client_singleton = _NoOpTweetClient()
        return _client_singleton

    try:
        _client_singleton = _TwitterClient()
    except Exception as exc:
        logger.warning("Falling back to No-Op tweet client: %s", exc)
        _client_singleton = _NoOpTweetClient()

    return _client_singleton


def post_tweet(text: str, media_path: Optional[str] = None) -> bool:
    """
    Convenience helper used by views:
    post_tweet("New product: ...")
    """
    return get_tweet_client().make_tweet(text=text, media_path=media_path)


__all__ = ["get_tweet_client", "post_tweet"]
