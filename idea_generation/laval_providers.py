"""Provider ports and configurable live/fixture adapters for Idea Laval."""

from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass, field
from html.parser import HTMLParser
import re
from typing import Any, Mapping, Protocol, Sequence

from .config import Settings
from .laval_domain import canonical_domain
from .provider import StructuredProvider


class SearchProvider(Protocol):
    name: str

    def search(self, query: str, *, country: str, language: str, depth: int) -> list[dict[str, Any]]: ...


class WebPageProvider(Protocol):
    name: str

    def fetch(self, url: str) -> dict[str, Any]: ...


class TrendProvider(Protocol):
    name: str

    def research(self, term: str, *, country: str, window: str) -> dict[str, Any]: ...


class YouTubeObservationProvider(Protocol):
    name: str

    def search(self, query: str, *, country: str, language: str, limit: int) -> list[dict[str, Any]]: ...
    def comments(self, video_id: str, *, limit: int) -> list[dict[str, Any]]: ...


class ResearchSink(Protocol):
    name: str

    def record(self, findings: Sequence[Mapping[str, Any]], hypotheses: Sequence[Mapping[str, Any]] = (), mechanisms: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]: ...


PRODUCTS = (
    ("ProofFlow", "proofflow.example"),
    ("GoalForge", "goalforge.example"),
    ("CommitLoop", "commitloop.example"),
    ("PublicPact", "publicpact.example"),
    ("MomentumGrid", "momentumgrid.example"),
    ("ChallengeKit", "challengekit.example"),
)


class FixtureSearchProvider:
    """Deterministic recorded-style provider. Fixture URLs are visibly non-live."""

    name = "fixture"

    def search(self, query: str, *, country: str, language: str, depth: int) -> list[dict[str, Any]]:
        seed = int(hashlib.sha256(f"{query}|{country}|{language}".encode()).hexdigest()[:8], 16)
        offset = seed % len(PRODUCTS)
        products = PRODUCTS[offset:] + PRODUCTS[:offset]
        rows: list[dict[str, Any]] = []
        for position in range(1, depth + 1):
            if position <= 6:
                name, domain = products[(position - 1) % len(products)]
                rows.append({
                    "position": position,
                    "title": f"{name} — evidence fixture for {query}",
                    "url": f"https://{domain}/{country.lower()}/{language}",
                    "domain": domain,
                    "snippet": f"{name} helps users make commitments visible, track proof, and share progress.",
                    "result_type": "direct_product" if position <= 4 else "adjacent_product",
                    "provider_metadata": {"fixture": True, "seed": seed},
                })
            elif position == 7:
                rows.append({"position": position, "title": f"10 best tools for {query}", "url": "https://directory.example/best-tools", "domain": "directory.example", "snippet": "A comparison directory.", "result_type": "directory", "provider_metadata": {"fixture": True}})
            elif position == 8:
                rows.append({"position": position, "title": f"Users discuss {query}", "url": "https://reddit.com/r/fixture/comments/example", "domain": "reddit.com", "snippet": "Users report notification fatigue and weak accountability.", "result_type": "social", "provider_metadata": {"fixture": True}})
            elif position == 9:
                rows.append({"position": position, "title": f"Video review of {query}", "url": "https://youtube.com/watch?v=fixture", "domain": "youtube.com", "snippet": "A product comparison video.", "result_type": "social", "provider_metadata": {"fixture": True}})
            else:
                rows.append({"position": position, "title": f"Guide to {query}", "url": "https://publisher.example/guide", "domain": "publisher.example", "snippet": "An editorial guide.", "result_type": "article", "provider_metadata": {"fixture": True}})
        return rows


class FixtureYouTubeObservationProvider:
    """Deterministic behavior observations; never represented as live evidence."""

    name = "fixture"

    def search(self, query: str, *, country: str, language: str, limit: int) -> list[dict[str, Any]]:
        rows = []
        for index in range(limit):
            channel = f"fixture-channel-{index % 6}"
            video_id = hashlib.sha256(f"{query}|{country}|{language}|{index}".encode()).hexdigest()[:11]
            rows.append({
                "video_id": video_id,
                "channel_id": channel,
                "channel_title": f"Fixture Creator {index % 6 + 1}",
                "title": f"Fixture behavior {index + 1}: {query}",
                "description": "People demonstrate a manual workaround, share proof, and ask how to stay accountable.",
                "published_at": f"2025-0{index % 9 + 1}-01T00:00:00Z",
                "view_count": 1000 + index * 100,
                "like_count": 50 + index,
                "comment_count": 20 + index,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "country": country,
                "language": language,
                "fixture": True,
            })
        return rows

    def comments(self, video_id: str, *, limit: int) -> list[dict[str, Any]]:
        return [
            {
                "text": f"Fixture comment {index + 1}: I use a spreadsheet and a friend to prove progress.",
                "published_at": "2025-01-02T00:00:00Z",
                "like_count": index,
                "fixture": True,
            }
            for index in range(min(limit, 5))
        ]


class OfficialYouTubeObservationProvider:
    """Read-only YouTube Data API adapter. Captions are intentionally absent."""

    name = "youtube_data_api"
    base_url = "https://www.googleapis.com/youtube/v3"

    def __init__(self, api_key: str, *, timeout: float = 30) -> None:
        if not api_key:
            raise RuntimeError("YOUTUBE_API_KEY is required")
        self.api_key = api_key
        self.timeout = timeout

    def _get(self, path: str, params: Mapping[str, Any]) -> dict[str, Any]:
        import httpx
        response = httpx.get(
            f"{self.base_url}/{path}",
            params={**dict(params), "key": self.api_key},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("YouTube returned invalid JSON")
        return payload

    def search(self, query: str, *, country: str, language: str, limit: int) -> list[dict[str, Any]]:
        discovered = self._get("search", {
            "part": "snippet", "type": "video", "q": query,
            "regionCode": country, "relevanceLanguage": language,
            "maxResults": min(50, limit), "safeSearch": "moderate",
        })
        ids = [str(item.get("id", {}).get("videoId") or "") for item in discovered.get("items") or []]
        ids = [value for value in ids if value]
        if not ids:
            return []
        enriched = self._get("videos", {
            "part": "snippet,statistics,contentDetails", "id": ",".join(ids),
            "maxResults": min(50, len(ids)),
        })
        rows = []
        for item in enriched.get("items") or []:
            snippet = item.get("snippet") or {}
            statistics = item.get("statistics") or {}
            video_id = str(item.get("id") or "")
            if not video_id:
                continue
            rows.append({
                "video_id": video_id,
                "channel_id": str(snippet.get("channelId") or ""),
                "channel_title": str(snippet.get("channelTitle") or ""),
                "title": str(snippet.get("title") or ""),
                "description": str(snippet.get("description") or "")[:10_000],
                "published_at": snippet.get("publishedAt"),
                "view_count": int(statistics.get("viewCount") or 0),
                "like_count": int(statistics.get("likeCount") or 0),
                "comment_count": int(statistics.get("commentCount") or 0),
                "duration": str((item.get("contentDetails") or {}).get("duration") or ""),
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "country": country,
                "language": language,
                "fixture": False,
            })
        return rows

    def comments(self, video_id: str, *, limit: int) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        try:
            payload = self._get("commentThreads", {
                "part": "snippet", "videoId": video_id,
                "maxResults": min(100, limit), "order": "relevance", "textFormat": "plainText",
            })
        except Exception:
            # Disabled comments are missing data, not a failed video observation.
            return []
        rows = []
        for item in payload.get("items") or []:
            comment = (((item.get("snippet") or {}).get("topLevelComment") or {}).get("snippet") or {})
            rows.append({
                "text": str(comment.get("textDisplay") or "")[:2000],
                "published_at": comment.get("publishedAt"),
                "like_count": int(comment.get("likeCount") or 0),
                # Author IDs and names are deliberately not persisted.
            })
        return rows


class UnavailableYouTubeObservationProvider:
    """Keeps readiness endpoints available while live V2 remains blocked."""

    name = "unavailable"

    def search(self, query: str, *, country: str, language: str, limit: int) -> list[dict[str, Any]]:
        raise RuntimeError("official YouTube API is not configured and verified")

    def comments(self, video_id: str, *, limit: int) -> list[dict[str, Any]]:
        raise RuntimeError("official YouTube API is not configured and verified")


class DataForSEOSearchProvider:
    name = "dataforseo"
    task_post_endpoint = "https://api.dataforseo.com/v3/serp/google/organic/task_post"
    task_get_endpoint = "https://api.dataforseo.com/v3/serp/google/organic/task_get/advanced"
    normal_cost_per_ten = 0.0006
    locations = {
        "US": "United States",
        "GB": "United Kingdom",
        "DE": "Germany",
        "NO": "Norway",
        "DK": "Denmark",
    }

    def __init__(self, login: str, password: str, *, timeout: float = 90, poll_timeout: float = 3600, poll_interval: float = 5) -> None:
        if not login or not password:
            raise RuntimeError("DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD are required")
        self.auth = (login, password)
        self.timeout = timeout
        self.poll_timeout = poll_timeout
        self.poll_interval = poll_interval

    def estimate_cost(self, depth: int) -> float:
        return self.normal_cost_per_ten * max(1, math.ceil(depth / 10))

    def submit_many(self, requests: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        import httpx
        payload = [{
            "keyword": str(item["query"]),
            "location_name": self.locations.get(str(item["country"]), str(item["country"])),
            "language_code": str(item["language"]),
            "depth": int(item["depth"]),
            "device": "desktop",
            "priority": 1,
            "tag": str(item["key"])[:255],
        } for item in requests]
        response = httpx.post(self.task_post_endpoint, auth=self.auth, json=payload, timeout=self.timeout)
        response.raise_for_status()
        body = response.json()
        if int(body.get("status_code", 0)) != 20000:
            raise RuntimeError(f"DataForSEO rejected queued tasks: {body.get('status_message', 'unknown error')}")
        tasks = body.get("tasks") or []
        if len(tasks) != len(requests):
            raise RuntimeError("DataForSEO returned an unexpected queued task count")
        result = []
        for request, task in zip(requests, tasks):
            if int(task.get("status_code", 0)) != 20100 or not task.get("id"):
                result.append({"key": request["key"], "error": str(task.get("status_message") or "unknown error")})
            else:
                result.append({"key": request["key"], "remote_task_id": str(task["id"]), "cost": float(task.get("cost") or 0)})
        return result

    def fetch_result(self, remote_task_id: str) -> list[dict[str, Any]] | None:
        import httpx
        response = httpx.get(f"{self.task_get_endpoint}/{remote_task_id}", auth=self.auth, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if int(payload.get("status_code", 0)) != 20000:
            raise RuntimeError(f"DataForSEO result request failed: {payload.get('status_message', 'unknown error')}")
        tasks = payload.get("tasks") or []
        task = tasks[0] if tasks else {}
        status = int(task.get("status_code", 0))
        if status in {20100, 40601, 40602} or not task.get("result"):
            return None
        if status != 20000:
            raise RuntimeError(f"DataForSEO queued task failed: {task.get('status_message', 'unknown error')}")
        return self._rows(task, depth=int((task.get("data") or {}).get("depth") or 10))

    def wait_for_results(self, tasks: Mapping[str, str]) -> dict[str, list[dict[str, Any]]]:
        pending = dict(tasks)
        results: dict[str, list[dict[str, Any]]] = {}
        deadline = time.monotonic() + self.poll_timeout
        while pending and time.monotonic() < deadline:
            for key, remote_task_id in list(pending.items()):
                rows = self.fetch_result(remote_task_id)
                if rows is not None:
                    results[key] = rows
                    pending.pop(key)
            if pending:
                time.sleep(self.poll_interval)
        if pending:
            raise TimeoutError(f"DataForSEO queued tasks timed out: {len(pending)} still pending")
        return results

    @staticmethod
    def _rows(task: Mapping[str, Any], *, depth: int) -> list[dict[str, Any]]:
        results = task.get("result") or []
        items = (results[0] if results else {}).get("items") or []
        rows = []
        for item in items:
            if item.get("type") != "organic" or not item.get("url"):
                continue
            published_at = item.get("timestamp") or item.get("published_datetime")
            provider_metadata = {
                "task_id": task.get("id"),
                "cost": float(task.get("cost") or 0),
                "provider_status": task.get("status_code"),
            }
            if isinstance(published_at, str) and published_at.strip():
                provider_metadata["published_at"] = published_at.strip()
            rows.append({
                "position": int(item.get("rank_absolute") or item.get("rank_group") or len(rows) + 1),
                "title": str(item.get("title") or item.get("domain") or item["url"]),
                "url": str(item["url"]),
                "domain": str(item.get("domain") or ""),
                "snippet": str(item.get("description") or ""),
                "result_type": "organic",
                "provider_metadata": provider_metadata,
            })
        return rows[:depth]

    def search(self, query: str, *, country: str, language: str, depth: int) -> list[dict[str, Any]]:
        submitted = self.submit_many([{"key": "single", "query": query, "country": country, "language": language, "depth": depth}])
        return self.wait_for_results({"single": submitted[0]["remote_task_id"]})["single"]


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self.skip:
            self.skip -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip and data.strip():
            self.parts.append(data.strip())


class HttpWebPageProvider:
    name = "http"

    def __init__(self, *, timeout: float = 25, max_bytes: int = 2_000_000) -> None:
        self.timeout = timeout
        self.max_bytes = max_bytes

    def fetch(self, url: str) -> dict[str, Any]:
        import httpx
        with httpx.Client(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": "PTW-Idea-Laval/1.0 (+evidence research)"},
        ) as client:
            response = client.get(url)
        response.raise_for_status()
        raw = response.content[: self.max_bytes]
        content_type = response.headers.get("content-type", "")
        text = raw.decode(response.encoding or "utf-8", errors="replace")
        if "html" in content_type.lower() or "<html" in text[:500].lower():
            parser = _TextExtractor()
            parser.feed(text)
            text = "\n".join(parser.parts)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return {
            "url": str(response.url),
            "status_code": response.status_code,
            "content_type": content_type,
            "text": text[:100_000],
            "truncated": len(response.content) > self.max_bytes or len(text) > 100_000,
        }


class FixtureWebPageProvider:
    name = "fixture"

    def fetch(self, url: str) -> dict[str, Any]:
        domain = canonical_domain(url) or "fixture product"
        return {
            "url": url,
            "status_code": 200,
            "content_type": "text/plain; fixture=true",
            "text": (
                f"{domain} is a fixture product for public commitments and visible progress. "
                "Core features include proof updates, accountability circles, reminders, and shareable challenges. "
                "The product uses subscription pricing and referral invitations. Users report notification fatigue, "
                "shallow social feedback, hard onboarding, and no portable proof history."
            ),
            "truncated": False,
            "fixture": True,
        }


class FixtureTrendProvider:
    name = "fixture"

    def research(self, term: str, *, country: str, window: str) -> dict[str, Any]:
        digest = hashlib.sha256(f"{term}|{country}|{window}".encode()).digest()
        dimensions = {
            "current_interest": round(.25 + digest[0] / 510, 4),
            "growth": round(.15 + digest[1] / 425, 4),
            "acceleration": round(.10 + digest[2] / 364, 4),
            "persistence": round(.30 + digest[3] / 510, 4),
            "geo_spread": round(.25 + digest[4] / 510, 4),
        }
        stem = " ".join(term.split()[:4]).strip() or "behavior"
        discoveries = [
            {"term": f"{stem} proof streak", "type": "rising_query", "growth_label": f"+{100 + digest[5]}%"},
            {"term": f"public {stem} challenge", "type": "related_query", "growth_label": "related"},
        ]
        if digest[6] > 190:
            discoveries.append({"term": f"{stem} accountability circle", "type": "breakout", "growth_label": "Breakout"})
        return {"term": term, "country": country, "window": window, "dimensions": dimensions, "discoveries": discoveries, "raw": {"fixture": True, "digest": digest.hex()[:16]}}


class HttpTrendProvider:
    """Adapter for an owner-provided Google Trends alpha/API bridge contract."""

    name = "google_trends"

    def __init__(self, url: str, token: str = "", *, timeout: float = 90) -> None:
        if not url:
            raise RuntimeError("GOOGLE_TRENDS_BRIDGE_URL is required for TREND_PROVIDER=google_trends")
        self.url, self.token, self.timeout = url, token, timeout

    def research(self, term: str, *, country: str, window: str) -> dict[str, Any]:
        import httpx
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        response = httpx.post(self.url, headers=headers, json={"term": term, "country": country, "window": window}, timeout=self.timeout)
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict) or not isinstance(result.get("dimensions"), dict):
            raise ValueError("Google Trends bridge must return dimensions and optional discoveries")
        return result


class NullResearchSink:
    name = "disabled"

    def record(self, findings: Sequence[Mapping[str, Any]], hypotheses: Sequence[Mapping[str, Any]] = (), mechanisms: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
        return {"sources": {}, "hypotheses": {}, "mechanisms": {}, "disabled": True}


class CommanderResearchSink:
    name = "commander_research_knowledge_service"

    def __init__(self, url: str, token: str, *, timeout: float = 90) -> None:
        if not url or not token:
            raise RuntimeError("research bridge URL and token are required")
        self.url, self.token, self.timeout = url, token, timeout

    def record(self, findings: Sequence[Mapping[str, Any]], hypotheses: Sequence[Mapping[str, Any]] = (), mechanisms: Sequence[Mapping[str, Any]] = ()) -> dict[str, Any]:
        import httpx
        response = httpx.post(
            self.url,
            headers={"X-PTW-Bridge-Token": self.token},
            json={"findings": list(findings), "hypotheses": list(hypotheses), "mechanisms": list(mechanisms)},
            timeout=self.timeout,
        )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("Commander research bridge returned invalid JSON")
        return result


@dataclass(frozen=True, slots=True)
class ProviderBundle:
    llm: StructuredProvider
    search: SearchProvider
    web: WebPageProvider
    trends: TrendProvider
    research: ResearchSink
    youtube: YouTubeObservationProvider = field(default_factory=FixtureYouTubeObservationProvider)
    youtube_results_per_query: int = 10
    youtube_comments_per_video: int = 20


def providers_from_settings(settings: Settings, llm: StructuredProvider) -> ProviderBundle:
    if settings.search_provider == "fixture":
        search: SearchProvider = FixtureSearchProvider()
        web: WebPageProvider = FixtureWebPageProvider()
    elif settings.search_provider == "dataforseo":
        search = DataForSEOSearchProvider(
            settings.dataforseo_login,
            settings.dataforseo_password,
            poll_timeout=settings.dataforseo_poll_timeout,
        )
        web = HttpWebPageProvider()
    else:
        raise RuntimeError("LAVAL_SEARCH_PROVIDER must be fixture or dataforseo")
    if settings.trend_provider in {"fixture", "manual"}:
        trends: TrendProvider = FixtureTrendProvider()
    elif settings.trend_provider == "google_trends":
        trends = HttpTrendProvider(settings.trend_bridge_url, settings.trend_bridge_token)
    else:
        raise RuntimeError("LAVAL_TREND_PROVIDER must be fixture, manual, or google_trends")
    research: ResearchSink = (
        CommanderResearchSink(settings.research_bridge_url, settings.telegram_token)
        if settings.research_bridge_url and settings.telegram_token and settings.search_provider != "fixture"
        else NullResearchSink()
    )
    if settings.search_provider == "fixture":
        youtube: YouTubeObservationProvider = FixtureYouTubeObservationProvider()
    elif settings.youtube_api_key and settings.youtube_verified:
        youtube = OfficialYouTubeObservationProvider(settings.youtube_api_key)
    else:
        youtube = UnavailableYouTubeObservationProvider()
    return ProviderBundle(
        llm=llm, search=search, web=web, trends=trends, research=research, youtube=youtube,
        youtube_results_per_query=settings.youtube_results_per_query,
        youtube_comments_per_video=settings.youtube_comments_per_video,
    )
