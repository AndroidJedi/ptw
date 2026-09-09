"""Project-scoped, PAUSED-only Meta Ads staging for approved Studio versions."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
import os
import re
import stat
import threading
from typing import Any, Iterator, Mapping
from urllib.parse import quote
from uuid import NAMESPACE_URL, UUID, uuid5

import httpx

from commander.ids import new_uuid7

from .local_brief_store import LocalBriefStore, utc_now


GRAPH_VERSION = "v26.0"
DEPLOYMENT_STATES = frozenset({
    "queued", "creating_campaign", "creating_ad_set", "uploading_image",
    "creating_creative", "creating_ad", "staged", "failed",
})
SPECIAL_AD_CATEGORIES = frozenset({
    "NONE", "CREDIT", "EMPLOYMENT", "HOUSING", "ISSUES_ELECTIONS_POLITICS",
    "FINANCIAL_PRODUCTS_SERVICES", "ONLINE_GAMBLING_AND_GAMING",
})
_COUNTRY = re.compile(r"[A-Z]{2}")
_CITY_KEY = re.compile(r"[0-9]+")
_SECRET_KEYS = frozenset({
    "META_SYSTEM_USER_ACCESS_TOKEN", "META_AD_ACCOUNT_ID", "META_PAGE_ID",
    "META_INSTAGRAM_ACTOR_ID", "META_GRAPH_API_VERSION", "META_ADS_NAME_PREFIX",
})


def _secret_file_values() -> dict[str, str]:
    """Read an optional literal dotenv file without shell evaluation."""
    path = os.environ.get("META_ADS_SECRETS_PATH", "").strip()
    if not path or not os.path.exists(path):
        return {}
    metadata = os.lstat(path)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise RuntimeError("Meta Ads secrets path must be a regular file")
    mode = stat.S_IMODE(metadata.st_mode)
    if mode not in {0o400, 0o440, 0o600, 0o640}:
        raise RuntimeError("Meta Ads secrets file must use mode 400, 440, 600, or 640")
    values: dict[str, str] = {}
    with open(path, encoding="utf-8") as secrets:
        for line_number, raw_line in enumerate(secrets, start=1):
            line = raw_line.rstrip("\r\n")
            if not line or line.lstrip().startswith("#"):
                continue
            key, separator, value = line.partition("=")
            if not separator or key not in _SECRET_KEYS or key in values:
                raise RuntimeError(f"Meta Ads secrets file has an invalid entry on line {line_number}")
            values[key] = value.strip()
    return values


def _uuid(value: Any, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValueError(f"Meta Ads {field} must be a UUID") from error


def _text(value: Any, field: str, minimum: int, maximum: int) -> str:
    normalized = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if any(ord(character) < 32 and character not in "\n\t" for character in normalized):
        raise ValueError(f"Meta Ads {field} contains unsupported control characters")
    if not minimum <= len(normalized) <= maximum:
        raise ValueError(f"Meta Ads {field} must contain {minimum}-{maximum} characters")
    return normalized


def _single_line(value: Any, field: str, minimum: int, maximum: int) -> str:
    return _text(" ".join(str(value or "").split()), field, minimum, maximum)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _categories(value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError("Meta Ads special_ad_categories must be a non-empty list")
    normalized = [str(item).strip().upper() for item in value]
    if len(normalized) != len(set(normalized)) or any(item not in SPECIAL_AD_CATEGORIES for item in normalized):
        raise ValueError("Meta Ads special_ad_categories are invalid")
    if "NONE" in normalized and len(normalized) != 1:
        raise ValueError("Meta Ads NONE cannot be combined with another special category")
    return sorted(normalized)


def normalize_preset(value: Mapping[str, Any]) -> dict[str, Any]:
    base_fields = {"name", "countries", "age_min", "age_max", "gender", "daily_budget_minor"}
    supplied_fields = set(value)
    if supplied_fields != base_fields and supplied_fields != {*base_fields, "cities"}:
        raise ValueError("Meta Ads preset fields are invalid")
    countries = value["countries"]
    if not isinstance(countries, list) or len(countries) > 10:
        raise ValueError("Meta Ads preset requires at most 10 country codes")
    normalized_countries = sorted({str(item).strip().upper() for item in countries})
    if len(normalized_countries) != len(countries) or any(not _COUNTRY.fullmatch(item) for item in normalized_countries):
        raise ValueError("Meta Ads country codes must be unique ISO alpha-2 values")
    raw_cities = value.get("cities", [])
    if not isinstance(raw_cities, list) or len(raw_cities) > 5:
        raise ValueError("Meta Ads preset requires at most 5 cities")
    normalized_cities: list[dict[str, Any]] = []
    for raw_city in raw_cities:
        if not isinstance(raw_city, Mapping) or set(raw_city) != {"key", "name", "country_code", "radius_km"}:
            raise ValueError("Meta Ads city fields are invalid")
        key = str(raw_city["key"]).strip()
        country_code = str(raw_city["country_code"]).strip().upper()
        radius = raw_city["radius_km"]
        if not _CITY_KEY.fullmatch(key):
            raise ValueError("Meta Ads city key is invalid")
        if not _COUNTRY.fullmatch(country_code):
            raise ValueError("Meta Ads city country code is invalid")
        if isinstance(radius, bool) or not isinstance(radius, int) or not 17 <= radius <= 80:
            raise ValueError("Meta Ads city radius must be between 17 and 80 kilometers")
        normalized_cities.append({
            "key": key,
            "name": _single_line(raw_city["name"], "city name", 1, 100),
            "country_code": country_code,
            "radius_km": radius,
        })
    normalized_cities.sort(key=lambda item: (item["country_code"], item["name"].casefold(), item["key"]))
    if len({item["key"] for item in normalized_cities}) != len(normalized_cities):
        raise ValueError("Meta Ads city keys must be unique")
    if bool(normalized_countries) == bool(normalized_cities):
        raise ValueError("Meta Ads preset requires either countries or cities, but not both")
    age_min, age_max = value["age_min"], value["age_max"]
    budget = value["daily_budget_minor"]
    if any(isinstance(item, bool) or not isinstance(item, int) for item in (age_min, age_max, budget)):
        raise ValueError("Meta Ads ages and daily budget must be integers")
    if not 18 <= age_min <= age_max <= 65:
        raise ValueError("Meta Ads ages must be between 18 and 65")
    if not 1 <= budget <= 100_000_000:
        raise ValueError("Meta Ads daily budget is outside the supported bound")
    gender = str(value["gender"])
    if gender not in {"all", "men", "women"}:
        raise ValueError("Meta Ads gender must be all, men, or women")
    return {
        "schema": "ptw.meta-ads.preset.v2" if normalized_cities else "ptw.meta-ads.preset.v1",
        "name": _single_line(value["name"], "preset name", 1, 80),
        "countries": normalized_countries,
        **({"cities": normalized_cities} if normalized_cities else {}),
        "age_min": age_min, "age_max": age_max, "gender": gender,
        "daily_budget_minor": budget,
        "publisher_platforms": ["instagram"], "instagram_positions": ["stream"],
        "location_types": ["home"],
    }


@dataclass(frozen=True, slots=True)
class MetaAdsConfiguration:
    access_token: str = field(default="", repr=False)
    ad_account_id: str = ""
    page_id: str = ""
    instagram_actor_id: str = ""
    graph_version: str = GRAPH_VERSION
    name_prefix: str = "[PTW LOCAL]"
    instagram_media_origin: str = ""

    @property
    def configured(self) -> bool:
        return all((self.access_token, self.ad_account_id, self.page_id, self.instagram_actor_id))

    @classmethod
    def from_environment(cls) -> "MetaAdsConfiguration":
        file_values = _secret_file_values()

        def value(name: str, default: str = "") -> str:
            return os.environ.get(name, "").strip() or file_values.get(name, default).strip()

        version = value("META_GRAPH_API_VERSION", GRAPH_VERSION)
        if not re.fullmatch(r"v\d+\.\d+", version):
            raise RuntimeError("META_GRAPH_API_VERSION is invalid")
        prefix = _single_line(value("META_ADS_NAME_PREFIX", "[PTW LOCAL]"), "name prefix", 1, 40)
        return cls(
            access_token=value("META_SYSTEM_USER_ACCESS_TOKEN"),
            ad_account_id=value("META_AD_ACCOUNT_ID").removeprefix("act_"),
            page_id=value("META_PAGE_ID"),
            instagram_actor_id=value("META_INSTAGRAM_ACTOR_ID"),
            graph_version=version,
            name_prefix=prefix,
            instagram_media_origin=value("META_INSTAGRAM_MEDIA_ORIGIN"),
        )


class MetaAdsProviderError(RuntimeError):
    """Sanitized Meta failure safe for persistence and owner display."""

    def __init__(
        self, outcome: str, *, status_code: int | None = None,
        error_code: str | None = None, error_subcode: str | None = None,
        transient: bool = False,
    ) -> None:
        self.outcome = outcome
        self.status_code = status_code
        self.error_code = error_code
        self.error_subcode = error_subcode
        self.transient = transient
        context = ", ".join(
            f"{key}={value}" for key, value in (
                ("http", status_code), ("code", error_code), ("subcode", error_subcode),
            ) if value is not None
        )
        super().__init__(f"{outcome}. Check the Meta connection and retry from Ads.{f' ({context})' if context else ''}")

    def record(self) -> dict[str, Any]:
        return {
            "error_type": type(self).__name__, "error_message": str(self)[:1000],
            "provider_context": {
                "http_status": self.status_code, "code": self.error_code,
                "subcode": self.error_subcode, "transient": self.transient,
            },
        }


class MetaAdsAdapter:
    """Minimal Graph client with server-owned PAUSED/Instagram-only payloads."""

    def __init__(
        self, configuration: MetaAdsConfiguration, *, client: httpx.Client | None = None,
    ) -> None:
        if not configuration.access_token:
            raise RuntimeError("Meta credentials are not configured")
        self.configuration = configuration
        self._client = client
        self._base = f"https://graph.facebook.com/{configuration.graph_version}"

    @property
    def account_node(self) -> str:
        return f"act_{self.configuration.ad_account_id}"

    def _call(
        self, method: str, path: str, *, data: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None, files: Mapping[str, Any] | None = None,
        outcome: str,
    ) -> dict[str, Any]:
        request = {
            "headers": {"Authorization": f"Bearer {self.configuration.access_token}"},
            "data": None if data is None else dict(data),
            "params": None if params is None else dict(params),
            "files": files,
        }
        try:
            if self._client is None:
                with httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
                    response = client.request(method, f"{self._base}/{path.lstrip('/')}", **request)
            else:
                response = self._client.request(method, f"{self._base}/{path.lstrip('/')}", **request)
        except httpx.HTTPError as error:
            raise MetaAdsProviderError(outcome) from error
        try:
            payload = response.json()
        except ValueError as error:
            raise MetaAdsProviderError(outcome, status_code=response.status_code) from error
        if response.status_code >= 400 or not isinstance(payload, Mapping) or payload.get("error"):
            provider = payload.get("error") if isinstance(payload, Mapping) else {}
            provider = provider if isinstance(provider, Mapping) else {}
            raise MetaAdsProviderError(
                outcome, status_code=response.status_code,
                error_code=None if provider.get("code") is None else str(provider.get("code")),
                error_subcode=None if provider.get("error_subcode") is None else str(provider.get("error_subcode")),
                transient=bool(provider.get("is_transient")),
            )
        return dict(payload)

    @staticmethod
    def _data(**values: Any) -> dict[str, Any]:
        return {
            key: _canonical(value) if isinstance(value, (dict, list)) else value
            for key, value in values.items() if value is not None
        }

    def connection(self) -> dict[str, Any]:
        permission_result = self._call("GET", "me/permissions", outcome="Meta advertising permissions could not be verified")
        granted = {item.get("permission") for item in permission_result.get("data", []) if item.get("status") == "granted"}
        if not {"ads_read", "ads_management"} <= granted:
            raise MetaAdsProviderError("Meta advertising permissions are missing")
        accounts_value = self._call(
            "GET", "me/adaccounts",
            params={"fields": "id,name,currency,timezone_name,account_status", "limit": 100},
            outcome="Meta ad account discovery failed",
        )
        account = self._call(
            "GET", self.account_node,
            params={"fields": "id,name,currency,timezone_name,account_status,disable_reason,promote_pages"},
            outcome="Meta ad account verification failed",
        )
        instagram = self._call(
            "GET", f"{self.account_node}/instagram_accounts",
            params={"fields": "id,username", "limit": 100},
            outcome="Meta Instagram asset verification failed",
        )
        pages_value = account.get("promote_pages") or {}
        pages = pages_value.get("data", []) if isinstance(pages_value, Mapping) else pages_value
        pages = pages if isinstance(pages, list) else []
        instagram_items = instagram.get("data") if isinstance(instagram.get("data"), list) else []
        accounts = accounts_value.get("data") if isinstance(accounts_value.get("data"), list) else []
        if not any(str(item.get("id", "")).removeprefix("act_") == self.configuration.ad_account_id for item in accounts if isinstance(item, Mapping)):
            raise MetaAdsProviderError("Configured ad account is not assigned to this system user")
        if not any(str(item.get("id")) == self.configuration.page_id for item in pages if isinstance(item, Mapping)):
            raise MetaAdsProviderError("Configured Facebook Page is not assigned to this ad account")
        selected_ig = next((
            item for item in instagram_items if isinstance(item, Mapping)
            and str(item.get("id")) == self.configuration.instagram_actor_id
        ), None)
        if selected_ig is None:
            raise MetaAdsProviderError("Configured Instagram account is not assigned to this ad account")
        selected_page = next((item for item in pages if str(item.get("id")) == self.configuration.page_id), {})
        return {
            "configured": True, "verified": True, "graph_version": self.configuration.graph_version,
            "account": {key: account.get(key) for key in ("id", "name", "currency", "timezone_name", "account_status")},
            "page": {"id": self.configuration.page_id, "name": selected_page.get("name")},
            "instagram": {"id": self.configuration.instagram_actor_id, "username": selected_ig.get("username")},
            "available": {
                "ad_accounts": [
                    {key: item.get(key) for key in ("id", "name", "currency", "timezone_name", "account_status")}
                    for item in accounts if isinstance(item, Mapping)
                ],
                "pages": [dict(item) for item in pages if isinstance(item, Mapping)],
                "instagram_accounts": [dict(item) for item in instagram_items if isinstance(item, Mapping)],
            },
        }

    def search_cities(self, query: str, country_code: str) -> list[dict[str, str]]:
        result = self._call(
            "GET", "search",
            params={
                "type": "adgeolocation", "location_types": _canonical(["city"]),
                "q": query, "country_code": country_code, "limit": 20,
            },
            outcome="Meta city search failed",
        )
        items: list[dict[str, str]] = []
        for raw_item in result.get("data", []):
            if not isinstance(raw_item, Mapping):
                continue
            key = str(raw_item.get("key") or "").strip()
            name = " ".join(str(raw_item.get("name") or "").split())
            item_country = str(raw_item.get("country_code") or "").strip().upper()
            item_type = str(raw_item.get("type") or "").strip().lower()
            if not _CITY_KEY.fullmatch(key) or not name or item_country != country_code or item_type != "city":
                continue
            items.append({
                "key": key, "name": name[:100], "type": "city", "country_code": item_country,
                "country_name": " ".join(str(raw_item.get("country_name") or "").split())[:100],
                "region": " ".join(str(raw_item.get("region") or "").split())[:100],
            })
        return items

    def _find(self, edge: str, name: str, *, fields: str) -> dict[str, Any] | None:
        result = self._call(
            "GET", f"{self.account_node}/{edge}",
            params={
                "fields": fields, "limit": 100,
                "filtering": _canonical([{"field": "name", "operator": "EQUAL", "value": name}]),
            }, outcome=f"Meta {edge} reconciliation failed",
        )
        matches = [
            dict(item) for item in result.get("data", [])
            if isinstance(item, Mapping) and item.get("name") == name
        ]
        if len(matches) > 1:
            raise MetaAdsProviderError(f"Meta {edge} reconciliation found duplicate PTW names")
        return matches[0] if matches else None

    def ensure_campaign(self, name: str, categories: list[str], objective: str = "OUTCOME_ENGAGEMENT") -> dict[str, Any]:
        existing = self._find("campaigns", name, fields="id,name,status,effective_status,objective,special_ad_categories")
        if existing is not None:
            if (existing.get("status") not in {"PAUSED", "ACTIVE"}
                    or existing.get("objective") != objective
                    or sorted(existing.get("special_ad_categories") or []) != ([] if categories == ["NONE"] else categories)):
                raise MetaAdsProviderError("Existing PTW campaign does not match its objective and categories")
            return existing
        payload = self._call(
            "POST", f"{self.account_node}/campaigns",
            data=self._data(
                name=name, objective=objective, buying_type="AUCTION", status="PAUSED",
                special_ad_categories=[] if categories == ["NONE"] else categories,
            ), outcome="Meta campaign creation failed",
        )
        return {"id": str(payload["id"]), "name": name, "status": "PAUSED"}

    def ensure_ad_set(
        self, name: str, *, campaign_id: str, preset: Mapping[str, Any], destination: str = "INSTAGRAM_DIRECT",
    ) -> dict[str, Any]:
        existing = self._find("adsets", name, fields="id,name,status,effective_status,campaign_id,destination_type,optimization_goal,billing_event,daily_budget,targeting")
        if existing is not None:
            if str(existing.get("campaign_id")) != str(campaign_id) or existing.get("status") not in {"PAUSED", "ACTIVE"}:
                raise MetaAdsProviderError("Existing PTW ad set does not match its campaign")
            self._verify_ad_set(existing, campaign_id, preset, destination)
            return existing
        genders = None if preset["gender"] == "all" else [1 if preset["gender"] == "men" else 2]
        cities = preset.get("cities") or []
        geo_locations = {"location_types": ["home"]}
        if cities:
            geo_locations["cities"] = [
                {
                    "key": city["key"], "radius": city["radius_km"],
                    "distance_unit": "kilometer",
                }
                for city in cities
            ]
        else:
            geo_locations["countries"] = preset["countries"]
        targeting = {
            "geo_locations": geo_locations,
            "age_min": preset["age_min"], "age_max": preset["age_max"],
            "publisher_platforms": ["instagram"], "instagram_positions": ["stream"],
        }
        if genders is not None:
            targeting["genders"] = genders
        payload = self._call(
            "POST", f"{self.account_node}/adsets",
            data=self._data(
                name=name, campaign_id=campaign_id, status="PAUSED",
                optimization_goal="LINK_CLICKS" if destination == "WEBSITE" else "CONVERSATIONS", billing_event="IMPRESSIONS",
                bid_strategy="LOWEST_COST_WITHOUT_CAP", destination_type=destination,
                daily_budget=preset["daily_budget_minor"], targeting=targeting,
                promoted_object={
                    "page_id": self.configuration.page_id,
                    "instagram_user_id": self.configuration.instagram_actor_id,
                } if destination != "WEBSITE" else None,
            ), outcome="Meta ad set creation failed",
        )
        return {"id": str(payload["id"]), "name": name, "status": "PAUSED", "campaign_id": campaign_id}

    def upload_image(self, png: bytes, expected_sha256: str) -> str:
        if hashlib.sha256(png).hexdigest() != expected_sha256:
            raise ValueError("Approved Studio render digest mismatch before Meta upload")
        payload = self._call(
            "POST", f"{self.account_node}/adimages",
            files={"filename": (f"ptw-{expected_sha256[:12]}.png", png, "image/png")},
            outcome="Meta image upload failed",
        )
        images = payload.get("images")
        if not isinstance(images, Mapping) or len(images) != 1:
            raise MetaAdsProviderError("Meta image upload returned no image hash")
        result = next(iter(images.values()))
        if not isinstance(result, Mapping) or not result.get("hash"):
            raise MetaAdsProviderError("Meta image upload returned no image hash")
        return str(result["hash"])

    def ensure_creative(self, name: str, *, image_hash: str, specification: Mapping[str, Any]) -> dict[str, Any]:
        existing = self._find("adcreatives", name, fields="id,name,object_story_spec")
        story = {
            "page_id": self.configuration.page_id,
            "instagram_user_id": self.configuration.instagram_actor_id,
            "link_data": {
                "image_hash": image_hash, "message": specification["primary_text"],
                "name": specification["headline"],
                "call_to_action": {
                    "type": "SEND_MESSAGE", "value": {"app_destination": "INSTAGRAM_DIRECT"},
                },
            },
        }
        website = specification.get("destination_type") == "WEBSITE"
        if website:
            story["link_data"]["link"] = specification["landing"]["canonical_url"]
            story["link_data"]["call_to_action"] = {
                "type": "LEARN_MORE", "value": {"link": specification["landing"]["canonical_url"]},
            }
        if existing is not None:
            actual = existing.get("object_story_spec") or {}
            link = actual.get("link_data") or {}
            expected_link = story["link_data"]
            if (str(actual.get("page_id")) != self.configuration.page_id
                    or str(actual.get("instagram_user_id")) != self.configuration.instagram_actor_id
                    or any(link.get(key) != val for key, val in expected_link.items())):
                raise MetaAdsProviderError("Existing creative does not match the approved image and destination")
            return existing
        payload = self._call(
            "POST", f"{self.account_node}/adcreatives",
            data=self._data(
                name=name, object_story_spec=story,
                page_welcome_message=None if website else specification["welcome_message"],
                degrees_of_freedom_spec={
                    "creative_features_spec": {
                        "standard_enhancements": {"enroll_status": "OPT_OUT"},
                    },
                },
            ), outcome="Meta ad creative creation failed",
        )
        return {"id": str(payload["id"]), "name": name}

    def ensure_ad(self, name: str, *, ad_set_id: str, creative_id: str) -> dict[str, Any]:
        existing = self._find("ads", name, fields="id,name,status,effective_status,adset_id,creative")
        if existing is not None:
            if str(existing.get("adset_id")) != str(ad_set_id) or str((existing.get("creative") or {}).get("id")) != creative_id or existing.get("status") != "PAUSED":
                raise MetaAdsProviderError("Existing PTW ad does not match its PAUSED ad set")
            return existing
        payload = self._call(
            "POST", f"{self.account_node}/ads",
            data=self._data(name=name, adset_id=ad_set_id, creative={"creative_id": creative_id}, status="PAUSED"),
            outcome="Meta ad creation failed",
        )
        return {"id": str(payload["id"]), "name": name, "status": "PAUSED", "adset_id": ad_set_id}

    def verify_parents(self, campaign_id: str, ad_set_id: str | None, specification: Mapping[str, Any]) -> None:
        campaign = self._call("GET", campaign_id,
            params={"fields": "id,account_id,objective,special_ad_categories,status"}, outcome="Meta campaign verification failed")
        categories = specification["special_ad_categories"]
        if (str(campaign.get("account_id")) != self.configuration.ad_account_id
                or campaign.get("objective") != specification["objective"]
                or sorted(campaign.get("special_ad_categories") or []) != ([] if categories == ["NONE"] else categories)
                or campaign.get("status") not in {"PAUSED", "ACTIVE"}):
            raise MetaAdsProviderError("Existing campaign no longer matches the reviewed ad")
        if ad_set_id:
            ad_set = self._call("GET", ad_set_id,
                params={"fields": "id,campaign_id,destination_type,optimization_goal,billing_event,daily_budget,targeting,status"},
                outcome="Meta ad set verification failed")
            self._verify_ad_set(ad_set, campaign_id, specification["preset"], specification["destination_type"])

    @staticmethod
    def _verify_ad_set(value: Mapping[str, Any], campaign_id: str, preset: Mapping[str, Any], destination: str) -> None:
        targeting = value.get("targeting") or {}
        geo = targeting.get("geo_locations") or {}
        expected_cities = preset.get("cities") or []
        actual_cities = geo.get("cities") or []
        cities_match = sorted((str(item.get("key")), item.get("radius"), item.get("distance_unit")) for item in actual_cities) == sorted((item["key"], item["radius_km"], "kilometer") for item in expected_cities)
        if (str(value.get("campaign_id")) != campaign_id or value.get("status") not in {"PAUSED", "ACTIVE"}
                or value.get("destination_type") != destination
                or value.get("optimization_goal") != ("LINK_CLICKS" if destination == "WEBSITE" else "CONVERSATIONS")
                or value.get("billing_event") != "IMPRESSIONS"
                or str(value.get("daily_budget")) != str(preset["daily_budget_minor"])
                or targeting.get("publisher_platforms") != ["instagram"] or targeting.get("instagram_positions") != ["stream"]
                or targeting.get("age_min") != preset["age_min"] or targeting.get("age_max") != preset["age_max"]
                or (targeting.get("genders") or []) != ([] if preset["gender"] == "all" else [1 if preset["gender"] == "men" else 2])
                or sorted(geo.get("countries") or []) != sorted(preset["countries"])
                or not cities_match):
            raise MetaAdsProviderError("Existing ad set no longer matches the reviewed audience and destination")

    def status(self, object_id: str, kind: str) -> dict[str, Any]:
        fields = "id,name,status,effective_status,issues_info"
        value = self._call("GET", object_id, params={"fields": fields}, outcome=f"Meta {kind} status sync failed")
        return {key: value.get(key) for key in ("id", "name", "status", "effective_status", "issues_info")}

    def ads_manager_url(self, campaign_id: str | None = None) -> str:
        base = f"https://adsmanager.facebook.com/adsmanager/manage/campaigns?act={quote(self.configuration.ad_account_id)}"
        return base if not campaign_id else f"{base}&selected_campaign_ids={quote(str(campaign_id))}"


class LocalMetaAdsAuthority:
    """Append-only local authority backed by the canonical local record store."""

    def __init__(self, store: LocalBriefStore) -> None:
        self.store = store
        self._lock = threading.RLock()

    @contextmanager
    def execution_lock(self, project_id: str) -> Iterator[None]:
        import fcntl
        directory = self.store.root / "meta-ads-locks"
        directory.mkdir(exist_ok=True)
        with (directory / _uuid(project_id, "project_id")).open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def list_presets(self) -> list[dict[str, Any]]:
        return sorted(self.store.list("meta_ads_presets"), key=lambda item: int(item["version"]), reverse=True)

    def create_preset(self, spec: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            previous = self.list_presets()
            value = {
                "preset_id": new_uuid7(), "version": int(previous[0]["version"]) + 1 if previous else 1,
                "specification": deepcopy(dict(spec)), "specification_sha256": _sha(spec),
                "created_at": utc_now(),
            }
            self.store.append("meta_ads_presets", value["preset_id"], value)
            return value

    def get_preset(self, preset_id: str) -> dict[str, Any]:
        return self.store.get("meta_ads_presets", _uuid(preset_id, "preset_id"))

    def project(self, project_id: str) -> dict[str, Any]:
        return self.store.get("projects", _uuid(project_id, "project_id"))

    def get_experiment(self, project_id: str, experiment_id: str | None = None) -> dict[str, Any] | None:
        project_id = _uuid(project_id, "project_id")
        return next((item for item in self.store.list("meta_ads_experiments") if item["project_id"] == project_id and (experiment_id is None or item["experiment_id"] == experiment_id)), None)

    def ensure_experiment(self, project_id: str, name: str, categories: list[str], objective: str = "OUTCOME_ENGAGEMENT") -> dict[str, Any]:
        with self._lock:
            existing = next((item for item in self.store.list("meta_ads_experiments") if
                item["project_id"] == project_id and item.get("objective", "OUTCOME_ENGAGEMENT") == objective
                and item["special_ad_categories"] == categories), None)
            if existing is not None:
                return existing
            experiment_id = new_uuid7()
            value = {
                "experiment_id": experiment_id, "project_id": _uuid(project_id, "project_id"),
                "campaign_name": name, "special_ad_categories": categories, "objective": objective,
                "meta_campaign_id": None, "status": "reserved", "error": None,
                "created_at": utc_now(), "updated_at": utc_now(),
            }
            self.store.append("meta_ads_experiments", experiment_id, value)
            self.store.edge(source_id=project_id, relation="contains", target_id=experiment_id, evidence={"member": "meta_ads_experiment"})
            return value

    def update_experiment(self, experiment_id: str, **patch: Any) -> dict[str, Any]:
        current = self.store.get("meta_ads_experiments", _uuid(experiment_id, "experiment_id"))
        value = {**current, **deepcopy(patch), "updated_at": utc_now()}
        self.store.append("meta_ads_experiments", experiment_id, value)
        return value

    def ensure_audience(self, experiment_id: str, preset: Mapping[str, Any], name: str) -> dict[str, Any]:
        existing = next((item for item in self.store.list("meta_ads_audiences") if (
            item["experiment_id"] == experiment_id and item["preset_sha256"] == preset["specification_sha256"]
        )), None)
        if existing is not None:
            return existing
        audience_id = new_uuid7()
        value = {
            "audience_id": audience_id, "experiment_id": experiment_id,
            "preset_id": preset["preset_id"], "preset_sha256": preset["specification_sha256"],
            "specification": deepcopy(preset["specification"]), "ad_set_name": name,
            "meta_ad_set_id": None, "status": "reserved", "error": None,
            "created_at": utc_now(), "updated_at": utc_now(),
        }
        self.store.append("meta_ads_audiences", audience_id, value)
        self.store.edge(source_id=experiment_id, relation="contains", target_id=audience_id, evidence={"member": "meta_ads_audience"})
        return value

    def update_audience(self, audience_id: str, **patch: Any) -> dict[str, Any]:
        current = self.store.get("meta_ads_audiences", _uuid(audience_id, "audience_id"))
        value = {**current, **deepcopy(patch), "updated_at": utc_now()}
        self.store.append("meta_ads_audiences", audience_id, value)
        return value

    def get_audience(self, audience_id: str) -> dict[str, Any]:
        return self.store.get("meta_ads_audiences", _uuid(audience_id, "audience_id"))

    def request_deployment(self, request_id: str) -> dict[str, Any] | None:
        return next((item for item in self.store.list("meta_ads_deployments") if item["request_id"] == request_id), None)

    def reserve_deployment(self, value: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        fingerprint = {"request_sha256": value["request_sha256"]}
        target, created = self.store.reserve_request(
            scope="meta_ads_deployments", request_id=str(value["request_id"]), fingerprint=fingerprint,
            create_target=lambda: str(value["deployment_id"]),
        )
        if not created:
            return self.get_deployment(target), False
        record = deepcopy(dict(value))
        self.store.append("meta_ads_deployments", target, record)
        source_version_id = record.get("source_version_id")
        if not source_version_id:
            source_version_id = str(uuid5(
                NAMESPACE_URL,
                f"ptw-studio-version:{record['source_creative_id']}:{record['source_version']}:{record['source_version_sha256']}",
            ))
            if not self.store.history("studio_versions", source_version_id):
                self.store.append("studio_versions", source_version_id, {
                    "version_id": source_version_id, "creative_id": record["source_creative_id"],
                    "version": record["source_version"], "version_sha256": record["source_version_sha256"],
                    "render_sha256": record["render_sha256"], "created_at": utc_now(),
                })
        self.store.edge(source_id=record["experiment_id"], relation="contains", target_id=target, evidence={"member": "meta_ads_deployment"})
        self.store.edge(source_id=target, relation="derived_from", target_id=source_version_id, evidence={"input": "approved_studio_version"})
        landing = record["specification"].get("landing")
        if landing:
            self.store.edge(source_id=target, relation="derived_from", target_id=landing["event_id"], evidence={"input": "published_landing"})
        return record, True

    def get_deployment(self, deployment_id: str) -> dict[str, Any]:
        return self.store.get("meta_ads_deployments", _uuid(deployment_id, "deployment_id"))

    def update_deployment(self, deployment_id: str, **patch: Any) -> dict[str, Any]:
        current = self.get_deployment(deployment_id)
        value = {**current, **deepcopy(patch), "updated_at": utc_now()}
        if value["status"] not in DEPLOYMENT_STATES:
            raise ValueError("Meta Ads deployment status is invalid")
        self.store.append("meta_ads_deployments", deployment_id, value)
        return value

    def list_deployments(self, project_id: str) -> list[dict[str, Any]]:
        project_id = _uuid(project_id, "project_id")
        return [item for item in self.store.list("meta_ads_deployments") if item["project_id"] == project_id]

    def record_run(self, deployment_id: str, stage: str, status: str, error: Mapping[str, Any] | None = None) -> dict[str, Any]:
        previous = [item for item in self.store.list("meta_ads_runs") if item["deployment_id"] == deployment_id]
        run_id = new_uuid7()
        value = {
            "run_id": run_id, "deployment_id": deployment_id, "attempt": len(previous) + 1,
            "stage": stage, "status": status, "error": deepcopy(error), "created_at": utc_now(),
        }
        self.store.append("meta_ads_runs", run_id, value)
        self.store.edge(source_id=deployment_id, relation="contains", target_id=run_id, evidence={"member": "meta_ads_stage_run", "stage": stage})
        deployment = self.get_deployment(deployment_id)
        self.store.edge(source_id=deployment["experiment_id"], relation="contains", target_id=run_id, evidence={"member": "meta_ads_stage_run", "stage": stage})
        return value

    def record_snapshot(self, deployment_id: str, value: Mapping[str, Any]) -> dict[str, Any]:
        snapshot_id = new_uuid7()
        record = {"snapshot_id": snapshot_id, "deployment_id": deployment_id, "objects": deepcopy(dict(value)), "created_at": utc_now()}
        self.store.append("meta_ads_snapshots", snapshot_id, record)
        self.store.edge(source_id=deployment_id, relation="contains", target_id=snapshot_id, evidence={"member": "meta_ads_status_snapshot"})
        return record

    def recover_interrupted(self) -> list[str]:
        return [item["deployment_id"] for item in self.store.list("meta_ads_deployments") if item["status"] not in {"staged", "failed"}]


class DatabaseMetaAdsAuthority:
    """PostgreSQL authority for Meta Ads orchestration and graph lineage."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    @contextmanager
    def connection(self) -> Iterator[Any]:
        import psycopg
        with psycopg.connect(self.database_url) as connection:
            with connection.transaction():
                yield connection

    @contextmanager
    def execution_lock(self, project_id: str) -> Iterator[None]:
        import psycopg
        key = "meta-ads-execute:" + _uuid(project_id, "project_id")
        with psycopg.connect(self.database_url, autocommit=True) as connection:
            connection.execute("SELECT pg_advisory_lock(hashtextextended(%s,0))", (key,))
            try:
                yield
            finally:
                connection.execute("SELECT pg_advisory_unlock(hashtextextended(%s,0))", (key,))

    @staticmethod
    def _edge(connection: Any, source_id: str, relation: str, target_id: str, attributes: Mapping[str, Any]) -> None:
        from psycopg.types.json import Jsonb
        connection.execute(
            """INSERT INTO commander_relationships(id,source_id,relation,target_id,attributes)
                 VALUES(%s,%s,%s,%s,%s) ON CONFLICT(source_id,relation,target_id) DO NOTHING""",
            (UUID(new_uuid7()), UUID(source_id), relation, UUID(target_id), Jsonb(dict(attributes))),
        )

    @staticmethod
    def _preset(row: Any) -> dict[str, Any]:
        return {"preset_id": str(row[0]), "version": int(row[1]), "specification": dict(row[2]), "specification_sha256": row[3], "created_at": row[4].isoformat()}

    def list_presets(self) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute("SELECT entity_id,version,specification,specification_sha256,created_at FROM meta_ads_preset_versions ORDER BY version DESC").fetchall()
        return [self._preset(row) for row in rows]

    def create_preset(self, spec: Mapping[str, Any]) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        preset_id = UUID(new_uuid7())
        with self.connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtextextended('meta-ads-presets',0))")
            version = int(connection.execute("SELECT COALESCE(max(version),0)+1 FROM meta_ads_preset_versions").fetchone()[0])
            connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'meta_ads_preset_version',%s)", (preset_id, Jsonb({"schema_version": 1, "version": version})))
            connection.execute("INSERT INTO meta_ads_preset_versions(entity_id,version,specification,specification_sha256) VALUES(%s,%s,%s,%s)", (preset_id, version, Jsonb(dict(spec)), _sha(spec)))
        return self.get_preset(str(preset_id))

    def get_preset(self, preset_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute("SELECT entity_id,version,specification,specification_sha256,created_at FROM meta_ads_preset_versions WHERE entity_id=%s", (UUID(preset_id),)).fetchone()
        if row is None:
            raise KeyError("Meta Ads preset was not found")
        return self._preset(row)

    def project(self, project_id: str) -> dict[str, Any]:
        from .repository import ValidationRepository
        return ValidationRepository(self.database_url).get_project(_uuid(project_id, "project_id"))

    @staticmethod
    def _experiment(row: Any) -> dict[str, Any]:
        return {
            "experiment_id": str(row[0]), "project_id": str(row[1]), "campaign_name": row[2],
            "special_ad_categories": list(row[3]), "meta_campaign_id": row[4], "status": row[5],
            "error": None if row[6] is None else dict(row[6]), "created_at": row[7].isoformat(), "updated_at": row[8].isoformat(), "objective": row[9],
        }

    def get_experiment(self, project_id: str, experiment_id: str | None = None) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute("SELECT entity_id,project_id,campaign_name,special_ad_categories,meta_campaign_id,status,error,created_at,updated_at,objective FROM meta_ads_workspaces WHERE project_id=%s AND (%s::uuid IS NULL OR entity_id=%s::uuid) ORDER BY created_at LIMIT 1", (UUID(project_id), experiment_id, experiment_id)).fetchone()
        return None if row is None else self._experiment(row)

    def ensure_experiment(self, project_id: str, name: str, categories: list[str], objective: str = "OUTCOME_ENGAGEMENT") -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        project_id = _uuid(project_id, "project_id")
        with self.connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"meta-ads-project:{project_id}",))
            row = connection.execute("SELECT entity_id,project_id,campaign_name,special_ad_categories,meta_campaign_id,status,error,created_at,updated_at,objective FROM meta_ads_workspaces WHERE project_id=%s AND objective=%s AND special_ad_categories=%s", (UUID(project_id), objective, Jsonb(categories))).fetchone()
            if row is not None:
                value = self._experiment(row)
                return value
            experiment_id = UUID(new_uuid7())
            connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'meta_ads_experiment',%s)", (experiment_id, Jsonb({"schema_version": 1, "project_id": project_id})))
            connection.execute("INSERT INTO meta_ads_workspaces(entity_id,project_id,campaign_name,special_ad_categories,objective,status) VALUES(%s,%s,%s,%s,%s,'reserved')", (experiment_id, UUID(project_id), name, Jsonb(categories), objective))
            self._edge(connection, project_id, "contains", str(experiment_id), {"member": "meta_ads_experiment"})
        return self.get_experiment(project_id, str(experiment_id)) or {}

    def update_experiment(self, experiment_id: str, **patch: Any) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        allowed = {"meta_campaign_id", "status", "error"}
        if set(patch) - allowed:
            raise ValueError("Meta Ads experiment patch is invalid")
        assignments, values = [], []
        for key, value in patch.items():
            assignments.append(f"{key}=%s")
            values.append(Jsonb(value) if key == "error" and value is not None else value)
        with self.connection() as connection:
            connection.execute(f"UPDATE meta_ads_workspaces SET {','.join(assignments)},updated_at=clock_timestamp() WHERE entity_id=%s", (*values, UUID(experiment_id)))
            project_id = str(connection.execute("SELECT project_id FROM meta_ads_workspaces WHERE entity_id=%s", (UUID(experiment_id),)).fetchone()[0])
        return self.get_experiment(project_id, str(experiment_id)) or {}

    @staticmethod
    def _audience(row: Any) -> dict[str, Any]:
        return {
            "audience_id": str(row[0]), "experiment_id": str(row[1]), "preset_id": str(row[2]),
            "preset_sha256": row[3], "specification": dict(row[4]), "ad_set_name": row[5],
            "meta_ad_set_id": row[6], "status": row[7], "error": None if row[8] is None else dict(row[8]),
            "created_at": row[9].isoformat(), "updated_at": row[10].isoformat(),
        }

    def ensure_audience(self, experiment_id: str, preset: Mapping[str, Any], name: str) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        with self.connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"meta-ads-audience:{experiment_id}:{preset['specification_sha256']}",))
            row = connection.execute("SELECT entity_id,workspace_id,preset_id,preset_sha256,specification,ad_set_name,meta_ad_set_id,status,error,created_at,updated_at FROM meta_ads_audience_versions WHERE workspace_id=%s AND preset_sha256=%s", (UUID(experiment_id), preset["specification_sha256"])).fetchone()
            if row is not None:
                return self._audience(row)
            audience_id = UUID(new_uuid7())
            connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'meta_ads_audience_version',%s)", (audience_id, Jsonb({"schema_version": 1, "preset_sha256": preset["specification_sha256"]})))
            connection.execute("INSERT INTO meta_ads_audience_versions(entity_id,workspace_id,preset_id,preset_sha256,specification,ad_set_name,status) VALUES(%s,%s,%s,%s,%s,%s,'reserved')", (audience_id, UUID(experiment_id), UUID(str(preset["preset_id"])), preset["specification_sha256"], Jsonb(dict(preset["specification"])), name))
            self._edge(connection, experiment_id, "contains", str(audience_id), {"member": "meta_ads_audience"})
        return self.get_audience(str(audience_id))

    def _audience_row(self, audience_id: str) -> Any:
        with self.connection() as connection:
            row = connection.execute("SELECT entity_id,workspace_id,preset_id,preset_sha256,specification,ad_set_name,meta_ad_set_id,status,error,created_at,updated_at FROM meta_ads_audience_versions WHERE entity_id=%s", (UUID(audience_id),)).fetchone()
        if row is None:
            raise KeyError("Meta Ads audience was not found")
        return row

    def get_audience(self, audience_id: str) -> dict[str, Any]:
        return self._audience(self._audience_row(audience_id))

    def update_audience(self, audience_id: str, **patch: Any) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        allowed = {"meta_ad_set_id", "status", "error"}
        if set(patch) - allowed:
            raise ValueError("Meta Ads audience patch is invalid")
        assignments, values = [], []
        for key, value in patch.items():
            assignments.append(f"{key}=%s")
            values.append(Jsonb(value) if key == "error" and value is not None else value)
        with self.connection() as connection:
            connection.execute(f"UPDATE meta_ads_audience_versions SET {','.join(assignments)},updated_at=clock_timestamp() WHERE entity_id=%s", (*values, UUID(audience_id)))
        return self.get_audience(audience_id)

    @staticmethod
    def _deployment(row: Any) -> dict[str, Any]:
        return {
            "deployment_id": str(row[0]), "request_id": str(row[1]), "request_sha256": row[2],
            "project_id": str(row[3]), "experiment_id": str(row[4]), "audience_id": str(row[5]),
            "source_creative_id": str(row[6]), "source_version_id": str(row[7]), "source_version": int(row[8]),
            "source_version_sha256": row[9], "render_sha256": row[10], "specification": dict(row[11]),
            "specification_sha256": row[12], "campaign_name": row[13], "ad_set_name": row[14],
            "creative_name": row[15], "ad_name": row[16], "meta_image_hash": row[17],
            "meta_creative_id": row[18], "meta_ad_id": row[19], "status": row[20],
            "error": None if row[21] is None else dict(row[21]), "status_snapshot": dict(row[22] or {}),
            "created_at": row[23].isoformat(), "updated_at": row[24].isoformat(),
        }

    @staticmethod
    def _deployment_select() -> str:
        return """SELECT entity_id,request_id,request_sha256,project_id,workspace_id,audience_id,
            source_creative_id,source_version_id,source_version,source_version_sha256,render_sha256,
            specification,specification_sha256,campaign_name,ad_set_name,creative_name,ad_name,
            meta_image_hash,meta_creative_id,meta_ad_id,status,error,status_snapshot,created_at,updated_at
            FROM meta_ads_deployments"""

    def get_deployment(self, deployment_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(self._deployment_select() + " WHERE entity_id=%s", (UUID(deployment_id),)).fetchone()
        if row is None:
            raise KeyError("Meta Ads deployment was not found")
        return self._deployment(row)

    def request_deployment(self, request_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(self._deployment_select() + " WHERE request_id=%s", (UUID(request_id),)).fetchone()
        return None if row is None else self._deployment(row)

    def reserve_deployment(self, value: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        from psycopg.types.json import Jsonb
        request_id = UUID(str(value["request_id"]))
        with self.connection() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"meta-ads-request:{request_id}",))
            row = connection.execute(self._deployment_select() + " WHERE request_id=%s", (request_id,)).fetchone()
            if row is not None:
                existing = self._deployment(row)
                if existing["request_sha256"] != value["request_sha256"]:
                    raise ValueError("idempotency request ID was reused with different input")
                return existing, False
            deployment_id = UUID(str(value["deployment_id"]))
            connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'meta_ads_deployment',%s)", (deployment_id, Jsonb({"schema_version": 1, "project_id": value["project_id"]})))
            connection.execute(
                """INSERT INTO meta_ads_deployments(
                    entity_id,request_id,request_sha256,project_id,workspace_id,audience_id,
                    source_creative_id,source_version_id,source_version,source_version_sha256,render_sha256,
                    specification,specification_sha256,campaign_name,ad_set_name,creative_name,ad_name,status
                ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'queued')""",
                (
                    deployment_id, request_id, value["request_sha256"], UUID(str(value["project_id"])),
                    UUID(str(value["experiment_id"])), UUID(str(value["audience_id"])),
                    UUID(str(value["source_creative_id"])), UUID(str(value["source_version_id"])), value["source_version"],
                    value["source_version_sha256"], value["render_sha256"], Jsonb(dict(value["specification"])),
                    value["specification_sha256"], value["campaign_name"], value["ad_set_name"], value["creative_name"], value["ad_name"],
                ),
            )
            self._edge(connection, str(value["experiment_id"]), "contains", str(deployment_id), {"member": "meta_ads_deployment"})
            self._edge(connection, str(deployment_id), "derived_from", str(value["source_version_id"]), {"input": "approved_studio_version"})
            landing = value["specification"].get("landing")
            if landing:
                self._edge(connection, str(deployment_id), "derived_from", landing["event_id"], {"input": "published_landing"})
        return self.get_deployment(str(deployment_id)), True

    def update_deployment(self, deployment_id: str, **patch: Any) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        allowed = {"meta_image_hash", "meta_creative_id", "meta_ad_id", "status", "error", "status_snapshot"}
        if set(patch) - allowed:
            raise ValueError("Meta Ads deployment patch is invalid")
        assignments, values = [], []
        for key, value in patch.items():
            assignments.append(f"{key}=%s")
            values.append(Jsonb(value) if key in {"error", "status_snapshot"} and value is not None else value)
        with self.connection() as connection:
            connection.execute(f"UPDATE meta_ads_deployments SET {','.join(assignments)},updated_at=clock_timestamp() WHERE entity_id=%s", (*values, UUID(deployment_id)))
        return self.get_deployment(deployment_id)

    def list_deployments(self, project_id: str) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(self._deployment_select() + " WHERE project_id=%s ORDER BY created_at DESC", (UUID(project_id),)).fetchall()
        return [self._deployment(row) for row in rows]

    def record_run(self, deployment_id: str, stage: str, status: str, error: Mapping[str, Any] | None = None) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        run_id = UUID(new_uuid7())
        with self.connection() as connection:
            attempt = int(connection.execute("SELECT COALESCE(max(attempt),0)+1 FROM meta_ads_stage_runs WHERE deployment_id=%s", (UUID(deployment_id),)).fetchone()[0])
            connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'meta_ads_stage_run',%s)", (run_id, Jsonb({"schema_version": 1, "stage": stage, "status": status})))
            connection.execute("INSERT INTO meta_ads_stage_runs(entity_id,deployment_id,attempt,stage,status,error) VALUES(%s,%s,%s,%s,%s,%s)", (run_id, UUID(deployment_id), attempt, stage, status, None if error is None else Jsonb(dict(error))))
            self._edge(connection, deployment_id, "contains", str(run_id), {"member": "meta_ads_stage_run", "stage": stage})
            workspace_id = str(connection.execute("SELECT workspace_id FROM meta_ads_deployments WHERE entity_id=%s", (UUID(deployment_id),)).fetchone()[0])
            self._edge(connection, workspace_id, "contains", str(run_id), {"member": "meta_ads_stage_run", "stage": stage})
        return {"run_id": str(run_id), "deployment_id": deployment_id, "attempt": attempt, "stage": stage, "status": status, "error": error}

    def record_snapshot(self, deployment_id: str, value: Mapping[str, Any]) -> dict[str, Any]:
        from psycopg.types.json import Jsonb
        snapshot_id = UUID(new_uuid7())
        with self.connection() as connection:
            connection.execute("INSERT INTO commander_entities(id,kind,attributes) VALUES(%s,'meta_ads_status_snapshot',%s)", (snapshot_id, Jsonb({"schema_version": 1})))
            connection.execute("INSERT INTO meta_ads_status_snapshots(entity_id,deployment_id,objects) VALUES(%s,%s,%s)", (snapshot_id, UUID(deployment_id), Jsonb(dict(value))))
            self._edge(connection, deployment_id, "contains", str(snapshot_id), {"member": "meta_ads_status_snapshot"})
        return {"snapshot_id": str(snapshot_id), "deployment_id": deployment_id, "objects": dict(value)}

    def recover_interrupted(self) -> list[str]:
        with self.connection() as connection:
            rows = connection.execute("SELECT entity_id FROM meta_ads_deployments WHERE status NOT IN ('staged','failed')").fetchall()
        return [str(row[0]) for row in rows]


class MetaAdsService:
    """Orchestrate immutable approved Studio renders into PAUSED Meta ads."""

    def __init__(self, authority: Any, studio: Any, configuration: MetaAdsConfiguration, adapter: MetaAdsAdapter | None = None, landing_publications: Any = None) -> None:
        self.authority = authority
        self.studio = studio
        self.configuration = configuration
        self.adapter = adapter
        self.landing_publications = landing_publications
        self._lock = threading.RLock()

    def landing(self, project_id: str) -> dict[str, Any] | None:
        publication = self.landing_publications.get(project_id) if self.landing_publications else None
        if not publication or publication["status"] != "published":
            return None
        event = next((item for item in publication["events"] if item["event_id"] == publication["current_event_id"]), None)
        if not event:
            return None
        return {"publication_id": publication["publication_id"], "event_id": event["event_id"],
                "landing_version_id": event.get("landing_version_id"),
                "landing_version": event["landing_version"], "landing_version_sha256": event["landing_version_sha256"],
                "canonical_url": publication["canonical_url"]}

    def connection(self, *, verify: bool = True) -> dict[str, Any]:
        if not self.configuration.configured or self.adapter is None:
            return {
                "configured": False, "verified": False, "graph_version": self.configuration.graph_version,
                "explanation": "Add the Meta system-user token and assigned asset IDs to the local secrets file.",
                "required_permissions": ["ads_management", "ads_read"],
            }
        if not verify:
            return {"configured": True, "verified": False, "graph_version": self.configuration.graph_version, "required_permissions": ["ads_management", "ads_read"]}
        try:
            return self.adapter.connection()
        except MetaAdsProviderError as error:
            return {
                "configured": True, "verified": False, "graph_version": self.configuration.graph_version,
                "explanation": str(error), "required_permissions": ["ads_management", "ads_read"],
            }

    def presets(self) -> dict[str, Any]:
        return {"items": self.authority.list_presets()}

    def locations(self, query: str, country_code: str) -> dict[str, Any]:
        query = _single_line(query, "location query", 2, 80)
        country_code = str(country_code).strip().upper()
        if not _COUNTRY.fullmatch(country_code):
            raise ValueError("Meta Ads location country code must be ISO alpha-2")
        if not self.configuration.configured or self.adapter is None:
            raise RuntimeError("Meta Ads city search is disabled until credentials and asset IDs are configured")
        connection = self.connection()
        if not connection.get("verified"):
            raise RuntimeError(str(connection.get("explanation") or "Meta Ads assets could not be verified"))
        return {"items": self.adapter.search_cities(query, country_code)}

    def create_preset(self, request: Mapping[str, Any]) -> dict[str, Any]:
        return {"preset": self.authority.create_preset(normalize_preset(request))}

    def _artifact(self, project_id: str, creative_id: str, version: int) -> dict[str, Any]:
        detail = self.studio.detail(project_id, creative_id)
        record = self.studio._workspace(creative_id).version_detail(version)
        rendered = self.studio._workspace(creative_id).version_render(version)
        if record.get("render_sha256") != rendered.get("sha256"):
            raise ValueError("Approved Studio render digest mismatch")
        brief = self.studio.authority.brief(detail["source_brief_id"])
        language = str((brief.get("document") or {}).get("language") or brief.get("language") or "uk")
        return {"detail": detail, "record": record, "rendered": rendered, "language": language}

    @staticmethod
    def _defaults(record: Mapping[str, Any], language: str) -> dict[str, str]:
        content = dict(record.get("content") or {})
        configuration = dict(record.get("configuration") or {})
        offer = str(content.get("offer") or "").strip()
        if isinstance(configuration.get("offer"), Mapping) and not configuration["offer"].get("enabled", True):
            offer = ""
        parts = [str(content.get("supporting_text") or "").strip(), offer]
        return {
            "headline": str(content.get("hero_title") or "").strip(),
            "primary_text": "\n\n".join(item for item in parts if item),
            "welcome_message": "Hi! I'd like to learn more." if language == "en" else "Вітаю! Хочу дізнатися більше.",
        }

    def _sources(self, project_id: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for creative in self.studio.list_creatives(project_id)["items"]:
            if int(creative.get("approved_version_count", 0)) < 1:
                continue
            detail = self.studio.detail(project_id, creative["creative_id"])
            brief = self.studio.authority.brief(detail["source_brief_id"])
            language = str((brief.get("document") or {}).get("language") or brief.get("language") or "uk")
            for summary in detail.get("versions", []):
                record = self.studio._workspace(creative["creative_id"]).version_detail(int(summary["version"]))
                items.append({
                    "creative_id": creative["creative_id"], "creative_ordinal": creative["ordinal"],
                    "template_id": creative["template_id"], "version": int(record["version"]),
                    "version_id": record.get("version_id"), "version_sha256": record["version_sha256"],
                    "render_sha256": record["render_sha256"], "change_note": record["change_note"],
                    "defaults": self._defaults(record, language),
                })
        return sorted(items, key=lambda item: (item["creative_ordinal"], item["version"]), reverse=True)

    def workspace(self, project_id: str) -> dict[str, Any]:
        project = self.authority.project(_uuid(project_id, "project_id"))
        experiment = self.authority.get_experiment(project_id)
        deployments = [
            {
                **item,
                "meta_ad_set_id": self.authority.get_audience(item["audience_id"]).get("meta_ad_set_id"),
                "meta_campaign_id": (self.authority.get_experiment(project_id, item["experiment_id"]) or {}).get("meta_campaign_id"),
                "ads_manager_url": self.adapter.ads_manager_url((self.authority.get_experiment(project_id, item["experiment_id"]) or {}).get("meta_campaign_id")) if self.adapter else None,
            }
            for item in self.authority.list_deployments(project_id)
        ]
        if self.adapter is not None:
            manager_url = self.adapter.ads_manager_url(None if experiment is None else experiment.get("meta_campaign_id"))
        else:
            manager_url = None
        return {
            "schema": "ptw.meta-ads.workspace.v1", "project_id": project_id,
            "project_name": project["name"], "connection": self.connection(verify=False),
            "presets": self.authority.list_presets(), "sources": self._sources(project_id),
            "experiment": experiment, "deployments": deployments, "ads_manager_url": manager_url,
            "landing": self.landing(project_id),
        }

    def reserve(self, project_id: str, request: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        with self._lock:
            return self._reserve(project_id, request)

    def _reserve(self, project_id: str, request: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        expected = {
            "request_id", "creative_id", "version", "preset_id", "primary_text",
            "headline", "welcome_message", "special_ad_categories",
        }
        website = request.get("destination_type") == "WEBSITE"
        if "destination_type" in request:
            expected.add("destination_type")
            if request["destination_type"] not in {"WEBSITE", "INSTAGRAM_DIRECT"}:
                raise ValueError("Meta Ads destination is invalid")
        if website:
            expected.remove("welcome_message")
            expected.add("landing_event_id")
        if set(request) != expected:
            raise ValueError("Meta Ads deployment fields are invalid")
        previous = self.authority.request_deployment(_uuid(request["request_id"], "request_id"))
        if previous:
            spec = previous["specification"]
            matches = (previous["project_id"] == _uuid(project_id, "project_id")
                and previous["source_creative_id"] == _uuid(request["creative_id"], "creative_id")
                and previous["source_version"] == request["version"] and not isinstance(request["version"], bool)
                and self.authority.get_audience(previous["audience_id"])["preset_id"] == request["preset_id"]
                and spec["headline"] == _single_line(request["headline"], "headline", 1, 255)
                and spec["primary_text"] == _text(request["primary_text"], "primary text", 1, 2200)
                and spec["special_ad_categories"] == _categories(request["special_ad_categories"])
                and spec["destination_type"] == ("WEBSITE" if website else "INSTAGRAM_DIRECT")
                and (spec["landing"]["event_id"] == request["landing_event_id"] if website else
                     spec["welcome_message"] == _text(request["welcome_message"], "welcome message", 1, 1000)))
            if not matches:
                raise ValueError("idempotency request ID was reused with different input")
            return previous, False
        if not self.configuration.configured or self.adapter is None:
            raise RuntimeError("Meta Ads staging is disabled until the local credentials and asset IDs are configured")
        connection = self.connection()
        if not connection.get("verified"):
            raise RuntimeError(str(connection.get("explanation") or "Meta Ads assets could not be verified"))
        project_id = _uuid(project_id, "project_id")
        self.authority.project(project_id)
        request_id = _uuid(request["request_id"], "request_id")
        creative_id = _uuid(request["creative_id"], "creative_id")
        version = request["version"]
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            raise ValueError("Meta Ads source version must be a positive integer")
        artifact = self._artifact(project_id, creative_id, version)
        record, rendered = artifact["record"], artifact["rendered"]
        preset = self.authority.get_preset(_uuid(request["preset_id"], "preset_id"))
        categories = _categories(request["special_ad_categories"])
        specification = {
            "schema": "ptw.meta-ads.deployment-spec.v1",
            "identity": {"ad_account_id": self.configuration.ad_account_id, "page_id": self.configuration.page_id,
                         "instagram_actor_id": self.configuration.instagram_actor_id},
            "primary_text": _text(request["primary_text"], "primary text", 1, 2200),
            "headline": _single_line(request["headline"], "headline", 1, 255),
            **({} if website else {"welcome_message": _text(request["welcome_message"], "welcome message", 1, 1000)}),
            "special_ad_categories": categories,
            "objective": "OUTCOME_ENGAGEMENT", "optimization_goal": "CONVERSATIONS",
            "destination_type": "INSTAGRAM_DIRECT", "billing_event": "IMPRESSIONS",
            "bid_strategy": "LOWEST_COST_WITHOUT_CAP", "call_to_action": "SEND_MESSAGE",
            "publisher_platforms": ["instagram"], "instagram_positions": ["stream"],
            "creative_enhancements": "OPT_OUT", "preset": deepcopy(preset["specification"]),
        }
        if website:
            landing = self.landing(project_id)
            if not landing or landing["event_id"] != request["landing_event_id"]:
                raise RuntimeError("Published Landing changed or is unavailable. Refresh and review the destination.")
            specification.update(schema="ptw.meta-ads.deployment-spec.v2", objective="OUTCOME_TRAFFIC",
                                 optimization_goal="LINK_CLICKS", destination_type="WEBSITE",
                                 call_to_action="LEARN_MORE", landing=landing)
        specification_sha = _sha(specification)
        project = self.authority.project(project_id)
        campaign_key = _sha({"objective": specification["objective"], "categories": categories})[:16]
        campaign_name = f"{self.configuration.name_prefix} [project:{project_id}] [{campaign_key}] {project['name']}"[:255]
        experiment = self.authority.ensure_experiment(project_id, campaign_name, categories, specification["objective"])
        campaign_name = experiment["campaign_name"]
        ad_set_name = f"{self.configuration.name_prefix} [campaign:{experiment['experiment_id']}] [preset:{preset['specification_sha256']}]"[:255]
        audience = self.authority.ensure_audience(experiment["experiment_id"], preset, ad_set_name)
        deployment_id = new_uuid7()
        fingerprint = {
            "project_id": project_id, "creative_id": creative_id, "version": version,
            "version_sha256": record["version_sha256"], "render_sha256": record["render_sha256"],
            "preset_id": preset["preset_id"], "specification": specification,
        }
        value = {
            "deployment_id": deployment_id, "request_id": request_id, "request_sha256": _sha(fingerprint),
            "project_id": project_id, "experiment_id": experiment["experiment_id"], "audience_id": audience["audience_id"],
            "source_creative_id": creative_id, "source_version_id": record.get("version_id"),
            "source_version": version, "source_version_sha256": record["version_sha256"],
            "render_sha256": record["render_sha256"], "specification": specification,
            "specification_sha256": specification_sha, "campaign_name": campaign_name,
            "ad_set_name": ad_set_name,
            "creative_name": f"{self.configuration.name_prefix} [deployment:{deployment_id}] Creative v{version}"[:255],
            "ad_name": f"{self.configuration.name_prefix} [deployment:{deployment_id}] Ad v{version}"[:255],
            "meta_image_hash": None, "meta_creative_id": None, "meta_ad_id": None,
            "status": "queued", "error": None, "status_snapshot": {},
            "created_at": utc_now(), "updated_at": utc_now(), "_render_bytes": rendered["bytes"],
        }
        stored = {key: item for key, item in value.items() if key != "_render_bytes"}
        deployment, created = self.authority.reserve_deployment(stored)
        return deployment, created

    @staticmethod
    def _error(error: Exception) -> dict[str, Any]:
        if isinstance(error, MetaAdsProviderError):
            return error.record()
        return {
            "error_type": type(error).__name__,
            "error_message": f"Meta Ads staging failed. Review the saved configuration and retry. ({type(error).__name__})",
            "provider_context": {},
        }

    def execute(self, deployment_id: str) -> dict[str, Any]:
        deployment_id = _uuid(deployment_id, "deployment_id")
        if self.adapter is None or not self.configuration.configured:
            error = RuntimeError("Meta Ads credentials are not configured")
            record = self._error(error)
            self.authority.record_run(deployment_id, "connection", "failed", record)
            return self.authority.update_deployment(deployment_id, status="failed", error=record)
        project_id = self.authority.get_deployment(deployment_id)["project_id"]
        with self._lock, self.authority.execution_lock(project_id):
            deployment = self.authority.get_deployment(deployment_id)
            if deployment["status"] == "staged":
                return deployment
            experiment = self.authority.get_experiment(deployment["project_id"], deployment["experiment_id"])
            if experiment is None:
                raise RuntimeError("Meta Ads experiment was not found")
            audience = self.authority.get_audience(deployment["audience_id"])
            try:
                spec = deployment["specification"]
                identity = spec.get("identity")
                if identity and identity != {"ad_account_id": self.configuration.ad_account_id,
                        "page_id": self.configuration.page_id, "instagram_actor_id": self.configuration.instagram_actor_id}:
                    raise RuntimeError("Configured Meta assets changed after review; create a new reviewed ad")
                self.adapter.connection()
                if spec.get("destination_type") == "WEBSITE":
                    landing = self.landing(deployment["project_id"])
                    if not landing or landing["event_id"] != spec["landing"]["event_id"]:
                        raise RuntimeError("Published Landing changed or is unavailable; create a new reviewed ad.")
                if experiment.get("meta_campaign_id") and isinstance(self.adapter, MetaAdsAdapter):
                    self.adapter.verify_parents(experiment["meta_campaign_id"], audience.get("meta_ad_set_id"), spec)
                if not experiment.get("meta_campaign_id"):
                    self.authority.update_deployment(deployment_id, status="creating_campaign", error=None)
                    campaign = self.adapter.ensure_campaign(deployment["campaign_name"], experiment["special_ad_categories"], **({"objective": "OUTCOME_TRAFFIC"} if spec.get("destination_type") == "WEBSITE" else {}))
                    experiment = self.authority.update_experiment(experiment["experiment_id"], meta_campaign_id=campaign["id"], status="staged", error=None)
                    self.authority.record_run(deployment_id, "campaign", "completed")
                if not audience.get("meta_ad_set_id"):
                    self.authority.update_deployment(deployment_id, status="creating_ad_set", error=None)
                    ad_set = self.adapter.ensure_ad_set(
                        deployment["ad_set_name"], campaign_id=experiment["meta_campaign_id"],
                        preset=deployment["specification"]["preset"],
                        **({"destination": "WEBSITE"} if spec.get("destination_type") == "WEBSITE" else {}),
                    )
                    audience = self.authority.update_audience(audience["audience_id"], meta_ad_set_id=ad_set["id"], status="staged", error=None)
                    self.authority.record_run(deployment_id, "ad_set", "completed")
                deployment = self.authority.get_deployment(deployment_id)
                if not deployment.get("meta_image_hash"):
                    self.authority.update_deployment(deployment_id, status="uploading_image", error=None)
                    artifact = self._artifact(deployment["project_id"], deployment["source_creative_id"], deployment["source_version"])
                    image_hash = self.adapter.upload_image(artifact["rendered"]["bytes"], deployment["render_sha256"])
                    deployment = self.authority.update_deployment(deployment_id, meta_image_hash=image_hash)
                    self.authority.record_run(deployment_id, "image", "completed")
                if not deployment.get("meta_creative_id"):
                    self.authority.update_deployment(deployment_id, status="creating_creative", error=None)
                    creative = self.adapter.ensure_creative(
                        deployment["creative_name"], image_hash=deployment["meta_image_hash"],
                        specification=deployment["specification"],
                    )
                    deployment = self.authority.update_deployment(deployment_id, meta_creative_id=creative["id"])
                    self.authority.record_run(deployment_id, "creative", "completed")
                if not deployment.get("meta_ad_id"):
                    self.authority.update_deployment(deployment_id, status="creating_ad", error=None)
                    ad = self.adapter.ensure_ad(
                        deployment["ad_name"], ad_set_id=audience["meta_ad_set_id"],
                        creative_id=deployment["meta_creative_id"],
                    )
                    deployment = self.authority.update_deployment(deployment_id, meta_ad_id=ad["id"])
                    self.authority.record_run(deployment_id, "ad", "completed")
                return self.authority.update_deployment(deployment_id, status="staged", error=None)
            except Exception as error:
                record = self._error(error)
                current = self.authority.get_deployment(deployment_id)
                failed_stage = "connection" if current["status"] == "queued" else current["status"]
                self.authority.record_run(deployment_id, failed_stage, "failed", record)
                if current["status"] == "creating_campaign":
                    self.authority.update_experiment(experiment["experiment_id"], status="failed", error=record)
                if current["status"] == "creating_ad_set":
                    self.authority.update_audience(audience["audience_id"], status="failed", error=record)
                return self.authority.update_deployment(deployment_id, status="failed", error=record)

    def retry(self, project_id: str, deployment_id: str) -> dict[str, Any]:
        deployment = self.authority.get_deployment(_uuid(deployment_id, "deployment_id"))
        if deployment["project_id"] != _uuid(project_id, "project_id"):
            raise KeyError("Meta Ads deployment was not found in this Project")
        if deployment["status"] != "failed":
            raise ValueError("Only a failed Meta Ads deployment can be retried")
        return self.authority.update_deployment(deployment_id, status="queued", error=None)

    def sync(self, project_id: str, deployment_id: str) -> dict[str, Any]:
        if self.adapter is None:
            raise RuntimeError("Meta Ads credentials are not configured")
        deployment = self.authority.get_deployment(_uuid(deployment_id, "deployment_id"))
        if deployment["project_id"] != _uuid(project_id, "project_id"):
            raise KeyError("Meta Ads deployment was not found in this Project")
        experiment = self.authority.get_experiment(project_id, deployment["experiment_id"])
        audience = self.authority.get_audience(deployment["audience_id"])
        objects: dict[str, Any] = {}
        for kind, identifier in (
            ("campaign", None if experiment is None else experiment.get("meta_campaign_id")),
            ("ad_set", audience.get("meta_ad_set_id")), ("ad", deployment.get("meta_ad_id")),
        ):
            if identifier:
                objects[kind] = self.adapter.status(str(identifier), kind)
        snapshot = self.authority.record_snapshot(deployment_id, objects)
        return self.authority.update_deployment(deployment_id, status_snapshot=snapshot["objects"])

    def recover_interrupted(self) -> list[str]:
        return self.authority.recover_interrupted()
