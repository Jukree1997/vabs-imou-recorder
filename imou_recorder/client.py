"""Minimal read-only client for the IMOU OpenAPI verification probe."""

from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid

from .config import ImouConfig
from .signing import calculate_signature


class ImouApiError(RuntimeError):
    """A sanitized IMOU or transport error that never includes credentials."""

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class AccessToken:
    value: str
    expires_in_seconds: int


class ImouClient:
    """Perform signed HTTPS requests without persisting tokens or secrets."""

    def __init__(self, config: ImouConfig) -> None:
        self._config = config

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        timestamp = int(time.time())
        nonce = str(uuid.uuid4())
        payload = {
            "system": {
                "ver": "1.0",
                "appId": self._config.app_id,
                "sign": calculate_signature(
                    timestamp,
                    nonce,
                    self._config.app_secret,
                    self._config.signing_algorithm,
                ),
                "time": timestamp,
                "nonce": nonce,
            },
            "id": str(uuid.uuid4()),
            "params": params,
        }
        request = Request(
            f"https://{self._config.api_host}:443/openapi/{method}",
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "vabs-imou-recorder/0.1",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self._config.timeout_seconds) as response:
                raw_response = response.read()
        except HTTPError as exc:
            raise ImouApiError(f"IMOU returned HTTP {exc.code} for {method}") from exc
        except URLError as exc:
            reason = getattr(exc, "reason", None)
            reason_name = type(reason).__name__ if reason is not None else "network error"
            raise ImouApiError(f"Could not reach IMOU for {method}: {reason_name}") from exc
        except TimeoutError as exc:
            raise ImouApiError(f"IMOU request timed out for {method}") from exc

        try:
            body = json.loads(raw_response.decode("utf-8"))
            result = body["result"]
            code = str(result["code"])
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ImouApiError(f"IMOU returned an invalid response for {method}") from exc

        if code != "0":
            message = str(result.get("msg") or "request failed")
            raise ImouApiError(f"IMOU {method} failed: {message}", code=code)

        data = result.get("data", {})
        if not isinstance(data, dict):
            raise ImouApiError(f"IMOU returned invalid data for {method}")
        return data

    def get_access_token(self) -> AccessToken:
        data = self._request("accessToken", {})
        token = data.get("accessToken")
        if not isinstance(token, str) or not token:
            raise ImouApiError("IMOU accessToken response did not contain a token")
        try:
            expires = int(data.get("expireTime", 0))
        except (TypeError, ValueError) as exc:
            raise ImouApiError("IMOU accessToken response had an invalid expiry") from exc
        return AccessToken(value=token, expires_in_seconds=expires)

    def list_imou_life_devices(self, token: str) -> list[dict[str, Any]]:
        data = self._request(
            "deviceBaseList",
            {
                "token": token,
                "bindId": -1,
                "limit": 128,
                "type": "bindAndShare",
                "needApInfo": False,
            },
        )
        devices = data.get("deviceList", [])
        if not isinstance(devices, list):
            raise ImouApiError("IMOU deviceBaseList returned an invalid device list")
        return [device for device in devices if isinstance(device, dict)]

    def list_imou_life_device_details(
        self,
        token: str,
        devices: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        device_list = []
        for device in devices:
            device_id = device.get("deviceId")
            channels = device.get("channels", [])
            channel_ids = [
                str(channel["channelId"])
                for channel in channels
                if isinstance(channel, dict) and channel.get("channelId") is not None
            ] if isinstance(channels, list) else []
            if isinstance(device_id, str) and device_id and channel_ids:
                device_list.append(
                    {"deviceId": device_id, "channelList": ",".join(channel_ids)}
                )

        if not device_list:
            return []
        data = self._request(
            "deviceBaseDetailList",
            {"token": token, "deviceList": device_list},
        )
        details = data.get("deviceList", [])
        if not isinstance(details, list):
            raise ImouApiError("IMOU deviceBaseDetailList returned invalid data")
        return [detail for detail in details if isinstance(detail, dict)]

    def query_local_records_window(
        self,
        token: str,
        device_id: str,
        channel_id: str,
        begin_time: str,
        end_time: str,
        *,
        page_size: int = 30,
    ) -> list[dict[str, Any]]:
        if not 1 <= page_size <= 30:
            raise ValueError("page_size must be 1-30")
        data = self._request(
            "queryLocalRecords",
            {
                "token": token,
                "deviceId": device_id,
                "channelId": channel_id,
                "beginTime": begin_time,
                "endTime": end_time,
                "type": "All",
                "queryRange": f"1-{page_size}",
            },
        )
        records = data.get("records", [])
        if not isinstance(records, list):
            raise ImouApiError("IMOU queryLocalRecords returned invalid data")
        return [record for record in records if isinstance(record, dict)]

    def query_all_local_records(
        self,
        token: str,
        device_id: str,
        channel_id: str,
        date_text: str,
        *,
        max_pages: int = 100,
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        page_size = 30
        cursor = f"{date_text} 00:00:00"
        day_end = f"{date_text} 23:59:59"
        for _ in range(max_pages):
            page = self.query_local_records_window(
                token,
                device_id,
                channel_id,
                cursor,
                day_end,
                page_size=page_size,
            )
            new_records = []
            for record in page:
                record_id = str(record.get("recordId") or "")
                if record_id and record_id in seen_ids:
                    continue
                if record_id:
                    seen_ids.add(record_id)
                new_records.append(record)
            records.extend(new_records)
            if len(page) < page_size or not new_records:
                return records
            page_end_times = [
                str(record.get("endTime"))
                for record in page
                if record.get("endTime")
            ]
            if not page_end_times:
                raise ImouApiError("Local-record page had no usable end times")
            next_cursor = max(page_end_times)
            if next_cursor <= cursor:
                raise ImouApiError("Local-record pagination did not advance")
            cursor = next_cursor
            if cursor >= day_end:
                return records
        raise ImouApiError("Local-record pagination exceeded the safety limit")
