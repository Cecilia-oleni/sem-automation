# 模块：sem_automation/reporting/angel_yeast/dataset.py；内部模块由统一入口调用。
# VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化'
# 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' reports angel-yeast --month 2026-08 --reuse-raw '.\outputs\_archive\angel_yeast\2026-08\_internal\direct_monthly_data.json' --skip-translation
# 该示例复用本地数据；详见 docs/月报操作说明.md。
"""安琪酵母专用 Yandex Direct 月报数据抓取与标准化。

本模块只负责 API、口径、分类和翻译，不直接写 Excel。Excel 由
``direct_report_workbooks.mjs`` 从本模块输出的 JSON 数据构建。
"""

from __future__ import annotations

from sem_automation.integrations.yandex.direct.angel_adapter import DICTIONARIES_URL, DirectReportsClient, REPORTS_URL, country_map_from_geo_regions

from sem_automation.core.paths import PROJECT_ROOT

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



DEFAULT_CONFIG = PROJECT_ROOT / "config" / "angel_yeast_direct_monthly.json"

INTEGER_FIELDS = {"Impressions", "Clicks"}
FLOAT_FIELDS = {"Cost"}


@dataclass(frozen=True)
class MonthRange:
    label: str
    start: str
    end: str
    month_start: str


def month_range(month: str) -> MonthRange:
    """Convert YYYY-MM to an inclusive Direct report date range."""
    match = re.fullmatch(r"(\d{4})-(\d{2})", month)
    if not match:
        raise ValueError("月份必须使用 YYYY-MM 格式，例如 2026-08")
    year, month_number = int(match.group(1)), int(match.group(2))
    if not 1 <= month_number <= 12:
        raise ValueError(f"无效月份：{month}")
    last_day = calendar.monthrange(year, month_number)[1]
    return MonthRange(
        label=month,
        start=f"{year:04d}-{month_number:02d}-01",
        end=f"{year:04d}-{month_number:02d}-{last_day:02d}",
        month_start=f"{year:04d}-{month_number:02d}-01",
    )


def previous_month(month: str) -> str:
    current = month_range(month)
    year, month_number = map(int, current.label.split("-"))
    if month_number == 1:
        return f"{year - 1:04d}-12"
    return f"{year:04d}-{month_number - 1:02d}"


def load_config(path: Path | str = DEFAULT_CONFIG) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _number(value: Any, integer: bool = False) -> int | float:
    if value is None:
        return 0
    text = str(value).strip().replace("\u00a0", "").replace(" ", "")
    if text in {"", "--", "-", "null", "None"}:
        return 0
    text = text.replace(",", ".")
    number = float(text)
    return int(round(number)) if integer else number


def _goal_column(goal_id: str, attribution_model: str) -> str:
    return f"Conversions_{goal_id}_{attribution_model}"


def normalize_report_rows(
    rows: list[dict[str, str]],
    goal_ids: list[str],
    attribution_model: str,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for source in rows:
        row: dict[str, Any] = {}
        for key, value in source.items():
            if key in INTEGER_FIELDS:
                row[key] = _number(value, integer=True)
            elif key in FLOAT_FIELDS or key.startswith("Conversions_"):
                row[key] = _number(value)
            else:
                row[key] = value.strip() if isinstance(value, str) else value

        for goal_id in goal_ids:
            field = _goal_column(goal_id, attribution_model)
            row.setdefault(field, 0)
        normalized.append(row)
    return normalized




REPORT_SPECS: dict[str, tuple[str, list[str]]] = {
    "account": (
        "CUSTOM_REPORT",
        ["Impressions", "Clicks", "Cost", "Conversions"],
    ),
    "network": (
        "CUSTOM_REPORT",
        ["AdNetworkType", "Impressions", "Clicks", "Cost", "Conversions"],
    ),
    "campaign": (
        "CAMPAIGN_PERFORMANCE_REPORT",
        [
            "CampaignId",
            "CampaignName",
            "Impressions",
            "Clicks",
            "Cost",
            "Conversions",
        ],
    ),
    "geo": (
        "CUSTOM_REPORT",
        [
            "TargetingLocationId",
            "TargetingLocationName",
            "Impressions",
            "Clicks",
            "Cost",
            "Conversions",
        ],
    ),
    "criteria": (
        "CRITERIA_PERFORMANCE_REPORT",
        [
            "CampaignId",
            "CampaignName",
            "AdGroupId",
            "AdGroupName",
            "CriterionId",
            "Criterion",
            "CriterionType",
            "Impressions",
            "Clicks",
            "Cost",
            "Conversions",
        ],
    ),
    "adgroup": (
        "ADGROUP_PERFORMANCE_REPORT",
        [
            "CampaignId",
            "CampaignName",
            "AdGroupId",
            "AdGroupName",
            "Impressions",
            "Clicks",
            "Cost",
            "Conversions",
        ],
    ),
}


def conversion_total(row: dict[str, Any], config: dict[str, Any]) -> float:
    model = config["attribution_model"]
    return sum(
        float(row.get(_goal_column(goal["id"], model), 0) or 0)
        for goal in config["goals"]
    )


def metric_totals(rows: Iterable[dict[str, Any]], config: dict[str, Any]) -> dict[str, float]:
    totals = {"Impressions": 0.0, "Clicks": 0.0, "Cost": 0.0, "ConversionsTotal": 0.0}
    for row in rows:
        totals["Impressions"] += float(row.get("Impressions", 0) or 0)
        totals["Clicks"] += float(row.get("Clicks", 0) or 0)
        totals["Cost"] += float(row.get("Cost", 0) or 0)
        totals["ConversionsTotal"] += conversion_total(row, config)
    totals["Impressions"] = int(round(totals["Impressions"]))
    totals["Clicks"] = int(round(totals["Clicks"]))
    return totals


def _aggregate(
    rows: Iterable[dict[str, Any]],
    key_fields: list[str],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row.get(field, "") for field in key_fields)].append(row)
    output = []
    for keys, grouped_rows in groups.items():
        item = dict(zip(key_fields, keys))
        item.update(metric_totals(grouped_rows, config))
        output.append(item)
    return output


COUNTRY_ALIASES = {
    "russian federation": "Russia",
    "russia": "Russia",
    "kazakhstan": "Kazakhstan",
    "belarus": "Belarus",
    "uzbekistan": "Uzbekistan",
    "moldova": "Moldova",
    "republic of moldova": "Moldova",
    "armenia": "Armenia",
    "tajikistan": "Tajikistan",
    "kyrgyzstan": "Kyrgyzstan",
    "azerbaijan": "Azerbaijan",
    "turkmenistan": "Turkmenistan",
    "abkhazia": "Abkhazia",
    "south ossetia": "South Ossetia",
}




def resolve_country(names: Iterable[str], known_countries: list[str]) -> str:
    candidates = [str(name).strip() for name in names if str(name).strip()]
    for candidate in candidates:
        normalized = candidate.casefold()
        if normalized in COUNTRY_ALIASES:
            return COUNTRY_ALIASES[normalized]
    for country in known_countries:
        target = country.casefold()
        if any(target in candidate.casefold() for candidate in candidates):
            return country
    return "Others"


def categorize(campaign_name: str, adgroup_name: str, config: dict[str, Any]) -> str:
    combined = f"{campaign_name} {adgroup_name}".casefold()
    # 品牌优先级最高，与用户提供的映射表一致。
    if "brand" in combined:
        return "brand"
    if any(pattern.casefold() in combined for pattern in config["exhibition_patterns"]):
        return "展会"
    for rule in config["category_rules"]:
        if rule["category"] == "brand":
            continue
        if any(pattern.casefold() in combined for pattern in rule["patterns"]):
            return rule["category"]
    return "待确认"


CATEGORY_REPORT_GROUP = {
    "brand": "brand",
    "Baking Yeast": "Baking Yeast",
    "Brewing Yeast": "Brewing Yeast",
    "Animal Nutrition": "Animal Nutrition",
    "YE": "YE",
    "Raising Agent": "膨松剂/生物技术",
    "Biotechnology Yeast": "膨松剂/生物技术",
    "展会": "展会",
    "待确认": "待确认",
}


CATEGORY_ZH = {
    "brand": "品牌",
    "Baking Yeast": "烘焙酵母",
    "Brewing Yeast": "酿造酵母",
    "Animal Nutrition": "动物营养",
    "YE": "YE",
    "Raising Agent": "膨松剂",
    "Biotechnology Yeast": "生物技术酵母",
    "展会": "展会",
    "待确认": "待确认",
}


def autotargeting_translation(campaign: str, adgroup: str, category: str) -> str:
    combined = f"{campaign} {adgroup}".casefold()
    if combined.lstrip().startswith("s-") or campaign.casefold().lstrip().startswith("s-"):
        channel = "搜索广告"
        region = ""
    else:
        channel = "网盟广告"
        if "y-cis" in combined:
            region = "中亚"
        elif "y-ru" in combined or "y-russia" in combined:
            region = "俄罗斯"
        else:
            region = ""
    category_zh = CATEGORY_ZH.get(category, category)
    qualifier = "B/C端词" if "b/c" in combined or "2b/c" in combined else ""
    return f"{region}{category_zh}{channel}{qualifier}自动定向"


def _parse_json_array(text: str) -> list[dict[str, str]]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start, end = cleaned.find("["), cleaned.rfind("]")
    if start < 0 or end < start:
        raise ValueError("翻译模型未返回 JSON 数组")
    parsed = json.loads(cleaned[start : end + 1])
    if not isinstance(parsed, list):
        raise ValueError("翻译模型返回结构不是数组")
    return parsed


def translate_missing_keywords(
    keywords: list[str],
    translations: dict[str, str],
) -> dict[str, str]:
    missing = sorted(
        {
            keyword.strip()
            for keyword in keywords
            if keyword.strip()
            and "autotarget" not in keyword.casefold()
            and keyword.strip().casefold() not in translations
        }
    )
    if not missing:
        return translations

    from sem_automation.ai.llm_client import call_llm

    prompt = (
        "请把下面的俄语 Yandex 广告关键词翻译成简洁、自然、适合中文月报表格的中文。"
        "不要扩写，不要解释；品牌 Angel 保持 Angel。只返回 JSON 数组，"
        "格式为 [{\"source\":\"原词\",\"zh\":\"中文\"}]。\n\n"
        + json.dumps(missing, ensure_ascii=False)
    )
    try:
        result = call_llm(
            prompt=prompt,
            system_prompt="你是俄语搜索广告关键词翻译助手，只输出有效 JSON。",
            temperature=0.1,
            max_tokens=3000,
            use_premium=False,
        )
        for item in _parse_json_array(result["content"]):
            source = str(item.get("source", "")).strip()
            zh = str(item.get("zh", "")).strip()
            if source and zh:
                translations[source.casefold()] = zh
    except Exception as exc:  # 保留数据交付，不因翻译服务暂时失败而丢失报表。
        print(f"关键词自动翻译失败，将使用待翻译标记：{exc}")

    for keyword in missing:
        translations.setdefault(keyword.casefold(), f"待翻译：{keyword}")
    return translations


def _sort_top(rows: list[dict[str, Any]], primary: str, limit: int = 12) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            float(row.get(primary, 0) or 0),
            float(row.get("Clicks", 0) or 0),
            float(row.get("Cost", 0) or 0),
        ),
        reverse=True,
    )[:limit]


def build_processed_data(
    raw: dict[str, list[dict[str, Any]]],
    config: dict[str, Any],
    report_month: str,
    geo_country_map: dict[str, str] | None = None,
    *,
    translate_keywords: bool = True,
) -> dict[str, Any]:
    current = month_range(report_month).month_start
    previous = month_range(previous_month(report_month)).month_start

    account = {row.get("Month"): {**row, "ConversionsTotal": conversion_total(row, config)} for row in raw["account"]}

    network_rows = _aggregate(raw["network"], ["Month", "AdNetworkType"], config)
    campaign_rows = _aggregate(raw["campaign"], ["Month", "CampaignId", "CampaignName"], config)

    geo_enriched = []
    geo_country_map = geo_country_map or {}
    for row in raw["geo"]:
        # 2026 年新版 Report Wizard 可直接选 Targeting country，
        # 但公开 Reports API v501 仍只暴露目标地域。用官方地域字典
        # 的上级链条得到等价的国家粒度，不使用用户实际所在地。
        region_id = str(row.get("TargetingLocationId", ""))
        mapped_country = geo_country_map.get(region_id, "")
        country = resolve_country(
            [mapped_country or row.get("TargetingLocationName", "")],
            config["known_countries"],
        )
        geo_enriched.append({**row, "Country": country})
    geo_country_rows = _aggregate(geo_enriched, ["Month", "Country"], config)

    criteria_rows = []
    for index, row in enumerate(raw["criteria"], start=1):
        item = {**row, "ConversionsTotal": conversion_total(row, config), "RawIndex": index}
        item["Category"] = categorize(
            str(row.get("CampaignName", "")), str(row.get("AdGroupName", "")), config
        )
        criteria_rows.append(item)
    current_criteria = [row for row in criteria_rows if row.get("Month") == current]
    top_clicks = _sort_top(current_criteria, "Clicks")
    top_conversions = _sort_top(current_criteria, "ConversionsTotal")

    translations = {
        source.casefold(): zh for source, zh in config.get("keyword_translations", {}).items()
    }
    if translate_keywords:
        translations = translate_missing_keywords(
            [str(row.get("Criterion", "")) for row in {id(row): row for row in top_clicks + top_conversions}.values()],
            translations,
        )
    for row in top_clicks + top_conversions:
        criterion = str(row.get("Criterion", ""))
        if "autotarget" in criterion.casefold():
            row["ChineseKeyword"] = autotargeting_translation(
                str(row.get("CampaignName", "")),
                str(row.get("AdGroupName", "")),
                row["Category"],
            )
        else:
            row["ChineseKeyword"] = translations.get(
                criterion.casefold(), f"待翻译：{criterion}"
            )

    category_detail = []
    for index, row in enumerate(raw["adgroup"], start=1):
        category = categorize(
            str(row.get("CampaignName", "")), str(row.get("AdGroupName", "")), config
        )
        category_detail.append(
            {
                **row,
                "Category": category,
                "ReportCategory": CATEGORY_REPORT_GROUP[category],
                "ConversionsTotal": conversion_total(row, config),
                "RawIndex": index,
            }
        )
    category_summary = _aggregate(
        category_detail, ["Month", "ReportCategory"], config
    )

    return {
        "current_month_start": current,
        "previous_month_start": previous,
        "account": account,
        "network": network_rows,
        "campaign": campaign_rows,
        "geo_country": geo_country_rows,
        "geo_enriched": geo_enriched,
        "criteria_all": criteria_rows,
        "top_clicks": top_clicks,
        "top_conversions": top_conversions,
        "translations": [
            {"Keyword": source, "ChineseKeyword": zh}
            for source, zh in sorted(translations.items())
        ],
        "category_detail": category_detail,
        "category_summary": category_summary,
    }


def fetch_all_reports(
    client: DirectReportsClient,
    config: dict[str, Any],
    report_month: str,
    *,
    include_vat: str,
    include_discount: str,
) -> dict[str, list[dict[str, Any]]]:
    current = month_range(report_month)
    previous = month_range(previous_month(report_month))
    goals = [item["id"] for item in config["goals"]]
    raw: dict[str, list[dict[str, Any]]] = {}
    for key, (report_type, fields) in REPORT_SPECS.items():
        print(f"正在拉取 Direct 报表：{key}")
        combined: list[dict[str, Any]] = []
        # Direct 的日期区间是查询条件，不是月报需要的分组维度。
        # 分别请求上月和本月，并在本地追加 Month 标记。
        for period in (previous, current):
            rows = client.get_report(
                report_key=f"{key}_{period.label}",
                report_type=report_type,
                field_names=fields,
                date_from=period.start,
                date_to=period.end,
                goals=goals,
                attribution_model=config["attribution_model"],
                include_vat=include_vat,
                include_discount=include_discount,
            )
            normalized = normalize_report_rows(rows, goals, config["attribution_model"])
            combined.extend({"Month": period.month_start, **row} for row in normalized)
        raw[key] = combined
        print(f"  获得 {len(raw[key])} 行")
    return raw


def calibrate_cost_flags(
    client: DirectReportsClient,
    config: dict[str, Any],
    *,
    month: str = "2026-07",
    expected_cost: float = 2332.35,
) -> dict[str, Any]:
    period = month_range(month)
    goal_ids = [item["id"] for item in config["goals"]]
    candidates = []
    for vat, discount in [("NO", "NO"), ("YES", "NO"), ("NO", "YES"), ("YES", "YES")]:
        rows = client.get_report(
            report_key=f"calibration_{vat}_{discount}",
            report_type="CUSTOM_REPORT",
            field_names=["Impressions", "Clicks", "Cost", "Conversions"],
            date_from=period.start,
            date_to=period.end,
            goals=goal_ids,
            attribution_model=config["attribution_model"],
            include_vat=vat,
            include_discount=discount,
        )
        normalized = normalize_report_rows(rows, goal_ids, config["attribution_model"])
        totals = metric_totals(normalized, config)
        candidates.append(
            {
                "IncludeVAT": vat,
                "IncludeDiscount": discount,
                **totals,
                "CostDifference": round(float(totals["Cost"]) - expected_cost, 4),
            }
        )
    best = min(candidates, key=lambda item: abs(item["CostDifference"]))
    return {"candidates": candidates, "selected": best}


def build_dataset(
    *,
    report_month: str,
    output_json: Path | str,
    config_path: Path | str = DEFAULT_CONFIG,
    calibrate: bool = True,
    translate_keywords: bool = True,
) -> dict[str, Any]:
    config = load_config(config_path)
    load_dotenv(PROJECT_ROOT / ".env")
    token = os.getenv("YANDEX_OAUTH_TOKEN", "")
    timeout = int(os.getenv("REQUEST_TIMEOUT", "60"))
    client = DirectReportsClient(token, config["client_login"], timeout=timeout)

    calibration = None
    include_vat = config.get("include_vat", "NO")
    include_discount = config.get("include_discount", "NO")
    if calibrate:
        print("正在用 2026 年 7 月总消耗校准 VAT / Discount 口径")
        calibration = calibrate_cost_flags(client, config)
        include_vat = calibration["selected"]["IncludeVAT"]
        include_discount = calibration["selected"]["IncludeDiscount"]
        print(
            "校准选择："
            f"IncludeVAT={include_vat}, IncludeDiscount={include_discount}, "
            f"7月消耗={calibration['selected']['Cost']:.2f} USD"
        )

    raw = fetch_all_reports(
        client,
        config,
        report_month,
        include_vat=include_vat,
        include_discount=include_discount,
    )
    region_ids = [row.get("TargetingLocationId", "") for row in raw["geo"]]
    print(f"正在沿官方 ParentId 地域树回溯 {len(set(map(str, region_ids)))} 个目标地域的国家")
    geo_country_map = client.get_geo_country_map(
        region_ids, config.get("geo_country_root_overrides")
    )
    processed = build_processed_data(
        raw,
        config,
        report_month,
        geo_country_map,
        translate_keywords=translate_keywords,
    )

    dataset = {
        "meta": {
            "client_name": config["client_name"],
            "client_login": config["client_login"],
            "report_month": report_month,
            "previous_month": previous_month(report_month),
            "attribution_model": config["attribution_model"],
            "include_vat": include_vat,
            "include_discount": include_discount,
            "exchange_rate_usd_cny": config["exchange_rate_usd_cny"],
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "goals": config["goals"],
            "july_ppt_geo_baseline": config.get("july_ppt_geo_baseline", []),
            "source": "Yandex Direct Reports API v501",
        },
        "calibration": calibration,
        "raw": raw,
        "geo_country_map": geo_country_map,
        "processed": processed,
    }
    destination = Path(output_json)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(dataset, handle, ensure_ascii=False, indent=2)
    print(f"标准化数据已保存：{destination}")
    return dataset


def rebuild_existing_dataset(
    *,
    report_month: str,
    dataset_path: Path | str,
    config_path: Path | str = DEFAULT_CONFIG,
    translate_keywords: bool = True,
) -> dict[str, Any]:
    """Reprocess an existing raw dataset without spending report API points again."""
    destination = Path(dataset_path)
    with destination.open("r", encoding="utf-8") as handle:
        dataset = json.load(handle)
    config = load_config(config_path)
    load_dotenv(PROJECT_ROOT / ".env")
    raw = dataset["raw"]
    # Preserve previously reviewed translations during offline rebuilds.
    cached = {row['Keyword']: row['ChineseKeyword'] for row in dataset.get('processed', {}).get('translations', [])}
    config['keyword_translations'] = {**cached, **config.get('keyword_translations', {})}
    region_ids = [row.get("TargetingLocationId", "") for row in raw["geo"]]
    geo_country_map = dataset.get("geo_country_map") or {}
    if geo_country_map:
        print(f"复用已保存的 {len(geo_country_map)} 条国家映射")
    else:
        print(f"正在沿官方 ParentId 地域树回溯 {len(set(map(str, region_ids)))} 个目标地域的国家")
        client = DirectReportsClient(
            os.getenv("YANDEX_OAUTH_TOKEN", ""), config["client_login"],
            timeout=int(os.getenv("REQUEST_TIMEOUT", "60")),
        )
        geo_country_map = client.get_geo_country_map(
            region_ids, config.get("geo_country_root_overrides")
        )
    dataset["geo_country_map"] = geo_country_map
    dataset.pop("geo_parents", None)
    dataset["processed"] = build_processed_data(
        raw,
        config,
        report_month,
        geo_country_map,
        translate_keywords=translate_keywords,
    )
    dataset["meta"]["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    dataset["meta"]["july_ppt_geo_baseline"] = config.get(
        "july_ppt_geo_baseline", []
    )
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(dataset, handle, ensure_ascii=False, indent=2)
    print(f"已使用现有 Raw 数据重建标准化数据：{destination}")
    return dataset
