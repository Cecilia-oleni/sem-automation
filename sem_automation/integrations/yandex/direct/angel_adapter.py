# 模块：sem_automation/integrations/yandex/direct/angel_adapter.py；内部模块由统一入口调用。
# VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化 - 副本'
# 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' --help
from __future__ import annotations

import calendar

import csv

import io

import json

import os

import re

import time

import uuid

from collections import defaultdict

from dataclasses import dataclass

from datetime import date, datetime, timezone

from pathlib import Path

from typing import Any, Iterable

import requests

from dotenv import load_dotenv

REPORTS_URL = "https://api.direct.yandex.com/json/v501/reports"

DICTIONARIES_URL = "https://api.direct.yandex.com/json/v501/dictionaries"

class DirectReportsClient:
    """Small production wrapper around the Yandex Direct Reports service."""

    def __init__(
        self,
        token: str,
        client_login: str,
        *,
        timeout: int = 60,
        session: requests.Session | None = None,
    ) -> None:
        if not token:
            raise ValueError("缺少 YANDEX_OAUTH_TOKEN，请检查项目 .env")
        self.client_login = client_login
        self.timeout = timeout
        self.session = session or requests.Session()
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Client-Login": client_login,
            "Accept-Language": "en",
            "Content-Type": "application/json; charset=utf-8",
            "processingMode": "auto",
            "returnMoneyInMicros": "false",
            "skipReportHeader": "true",
            "skipReportSummary": "true",
        }

    def get_report(
        self,
        *,
        report_key: str,
        report_type: str,
        field_names: list[str],
        date_from: str,
        date_to: str,
        goals: list[str],
        attribution_model: str,
        include_vat: str,
        include_discount: str,
        max_attempts: int = 20,
    ) -> list[dict[str, str]]:
        report_name = (
            f"Angel_{report_key}_{date_from}_{date_to}_{uuid.uuid4().hex[:8]}"
        )[:100]
        payload = {
            "params": {
                "SelectionCriteria": {"DateFrom": date_from, "DateTo": date_to},
                "Goals": goals,
                "AttributionModels": [attribution_model],
                "FieldNames": field_names,
                "ReportName": report_name,
                "ReportType": report_type,
                "DateRangeType": "CUSTOM_DATE",
                "Format": "TSV",
                "IncludeVAT": include_vat,
                "IncludeDiscount": include_discount,
            }
        }

        server_errors = 0
        for attempt in range(1, max_attempts + 1):
            response = self.session.post(
                REPORTS_URL,
                headers=self.headers,
                json=payload,
                timeout=self.timeout,
            )
            response.encoding = "utf-8"
            if response.status_code == 200:
                reader = csv.DictReader(io.StringIO(response.text), delimiter="\t")
                return [dict(row) for row in reader]

            if response.status_code in {201, 202}:
                wait_seconds = int(response.headers.get("retryIn", "5"))
                print(
                    f"[{report_key}] 报告离线生成中，"
                    f"第 {attempt} 次检查，{wait_seconds} 秒后重试"
                )
                time.sleep(min(max(wait_seconds, 1), 60))
                continue

            if response.status_code in {500, 502} and server_errors < 2:
                server_errors += 1
                time.sleep(3 * server_errors)
                continue

            request_id = response.headers.get("RequestId", "unknown")
            raise RuntimeError(
                f"Direct 报告 {report_key} 请求失败：HTTP {response.status_code}; "
                f"RequestId={request_id}; {response.text[:1200]}"
            )
        raise TimeoutError(f"Direct 报告 {report_key} 在限定重试次数内未生成完成")

    def get_geo_parents(self, region_ids: Iterable[int | str]) -> dict[str, list[str]]:
        ids = sorted({int(item) for item in region_ids if str(item).strip().isdigit()})
        if not ids:
            return {}
        result: dict[str, list[str]] = {}
        # getGeoRegions 对 RegionIds 的单次请求上限是 1,000。
        for start in range(0, len(ids), 1000):
            chunk = ids[start : start + 1000]
            payload = {
                "method": "getGeoRegions",
                "params": {
                    "SelectionCriteria": {"RegionIds": chunk},
                    "FieldNames": [
                        "GeoRegionId",
                        "GeoRegionName",
                        "ParentGeoRegionNames",
                    ],
                },
            }
            response = self.session.post(
                DICTIONARIES_URL,
                headers={
                    "Authorization": self.headers["Authorization"],
                    "Client-Login": self.client_login,
                    "Accept-Language": "en",
                    "Content-Type": "application/json; charset=utf-8",
                },
                json=payload,
                timeout=self.timeout,
            )
            if response.status_code != 200:
                raise RuntimeError(
                    f"地域字典请求失败：HTTP {response.status_code}; "
                    f"{response.text[:1200]}"
                )
            data = response.json()
            if "error" in data:
                raise RuntimeError(f"地域字典返回错误：{data['error']}")
            for item in data.get("result", {}).get("GeoRegions", []):
                parents = item.get("ParentGeoRegionNames") or {}
                result[str(item["GeoRegionId"])] = [
                    item.get("GeoRegionName", ""),
                    *(parents.get("Items") or []),
                ]
        return result

    def get_geo_country_map(
        self,
        region_ids: Iterable[int | str],
        root_country_overrides: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Resolve target-region IDs to countries using the full official geo tree."""
        wanted = {str(item) for item in region_ids if str(item).strip().isdigit()}
        if not wanted:
            return {}
        payload = {
            "method": "get",
            "params": {"DictionaryNames": ["GeoRegions"]},
        }
        response = self.session.post(
            DICTIONARIES_URL,
            headers={
                "Authorization": self.headers["Authorization"],
                "Client-Login": self.client_login,
                "Accept-Language": "en",
                "Content-Type": "application/json; charset=utf-8",
            },
            json=payload,
            timeout=max(self.timeout, 120),
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"完整地域字典请求失败：HTTP {response.status_code}; "
                f"{response.text[:1200]}"
            )
        data = response.json()
        if "error" in data:
            raise RuntimeError(f"完整地域字典返回错误：{data['error']}")
        regions = data.get("result", {}).get("GeoRegions", [])
        return country_map_from_geo_regions(
            regions, wanted, root_country_overrides=root_country_overrides
        )

def country_map_from_geo_regions(
    regions: Iterable[dict[str, Any]],
    region_ids: Iterable[int | str],
    *,
    root_country_overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    """Walk ParentId links until the official ``Country`` node is reached."""
    by_id = {str(item.get("GeoRegionId")): item for item in regions}
    root_country_overrides = root_country_overrides or {}
    output: dict[str, str] = {}
    for source_id in {str(item) for item in region_ids}:
        current_id = source_id
        seen: set[str] = set()
        while current_id and current_id not in seen:
            seen.add(current_id)
            if current_id in root_country_overrides:
                output[source_id] = root_country_overrides[current_id]
                break
            item = by_id.get(current_id)
            if not item:
                break
            if str(item.get("GeoRegionType", "")).casefold() == "country":
                output[source_id] = str(item.get("GeoRegionName", ""))
                break
            parent_id = item.get("ParentId")
            current_id = "" if parent_id in {None, ""} else str(parent_id)
    return output

