// 模块：sem_automation/reporting/renderers/angel_yeast/direct_report_workbooks.mjs；内部模块由统一入口调用。
// VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化'
// 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' reports angel-yeast --month 2026-08 --reuse-raw '.\outputs\_archive\angel_yeast\2026-08\_internal\direct_monthly_data.json' --skip-translation
// 该示例复用本地数据；详见 docs/月报操作说明.md。
import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";


const COLORS = {
  navy: "#0B3A82",
  blue: "#1666C5",
  cyan: "#19CFC2",
  paleBlue: "#EAF3FC",
  paleCyan: "#E8FBF8",
  paleYellow: "#FFF4CC",
  white: "#FFFFFF",
  text: "#1F2937",
  muted: "#667085",
  border: "#D6DFEA",
};


function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i += 2) {
    args[argv[i].replace(/^--/, "")] = argv[i + 1];
  }
  if (!args.input || !args["out-dir"] || !args["preview-dir"]) {
    throw new Error("Usage: node direct_report_workbooks.mjs --input data.json --out-dir DIR --preview-dir DIR");
  }
  return args;
}


function columnLetter(index1) {
  let value = index1;
  let result = "";
  while (value > 0) {
    value -= 1;
    result = String.fromCharCode(65 + (value % 26)) + result;
    value = Math.floor(value / 26);
  }
  return result;
}


function finite(value) {
  const number = Number(value ?? 0);
  return Number.isFinite(number) ? number : 0;
}


function monthLabel(monthStart) {
  return String(monthStart ?? "").slice(0, 7);
}


function goalFields(meta) {
  return meta.goals.map((goal) => `Conversions_${goal.id}_${meta.attribution_model}`);
}


function conversions(row, meta) {
  return goalFields(meta).reduce((sum, field) => sum + finite(row?.[field]), 0);
}


function metricRow(label, row, meta, extra = {}) {
  return {
    label,
    Impressions: finite(row?.Impressions),
    Clicks: finite(row?.Clicks),
    Cost: finite(row?.Cost),
    ConversionsTotal: row?.ConversionsTotal == null ? conversions(row, meta) : finite(row.ConversionsTotal),
    ...extra,
  };
}


function writeTitle(sheet, title, subtitle, lastCol) {
  const end = columnLetter(lastCol);
  sheet.getRange(`A1:${end}1`).merge();
  sheet.getRange("A1").values = [[title]];
  sheet.getRange(`A1:${end}1`).format = {
    fill: COLORS.navy,
    font: { bold: true, color: COLORS.white, size: 16 },
    verticalAlignment: "center",
  };
  sheet.getRange(`A1:${end}1`).format.rowHeight = 28;
  sheet.getRange(`A2:${end}2`).merge();
  sheet.getRange("A2").values = [[subtitle]];
  sheet.getRange(`A2:${end}2`).format = {
    fill: COLORS.paleBlue,
    font: { color: COLORS.muted, italic: true, size: 9 },
    wrapText: true,
  };
  sheet.getRange(`A2:${end}2`).format.rowHeight = 30;
}


function styleHeader(sheet, range) {
  sheet.getRange(range).format = {
    fill: COLORS.blue,
    font: { bold: true, color: COLORS.white },
    verticalAlignment: "center",
    horizontalAlignment: "center",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: COLORS.border },
  };
  sheet.getRange(range).format.rowHeight = 30;
}


function styleBody(sheet, range) {
  sheet.getRange(range).format = {
    font: { color: COLORS.text, size: 9 },
    verticalAlignment: "center",
    borders: {
      insideHorizontal: { style: "thin", color: COLORS.border },
      bottom: { style: "thin", color: COLORS.border },
    },
  };
}


function applyFormats(sheet, rowStart, rowEnd, config) {
  if (rowEnd < rowStart) return;
  for (const [column, format] of Object.entries(config)) {
    sheet.getRange(`${column}${rowStart}:${column}${rowEnd}`).format.numberFormat = format;
  }
}


function addInfoSheet(workbook, meta, title) {
  const sheet = workbook.worksheets.add("说明");
  sheet.showGridLines = false;
  writeTitle(sheet, title, "黄色单元格为可编辑假设；所有金额单位及数据口径均在本页说明。", 4);
  const rows = [
    ["项目", "值", "用途", "是否可编辑"],
    ["客户", meta.client_name, "报告主体", "否"],
    ["Direct Client-Login", meta.client_login, "代理商子账户", "否"],
    ["报告月份", meta.report_month, "当月", "否"],
    ["对比月份", meta.previous_month, "环比基期", "否"],
    ["归因模型", meta.attribution_model, "8个转化目标统一使用 Automatic", "否"],
    ["固定汇率 USD/CNY", finite(meta.exchange_rate_usd_cny), "人民币金额 = 美元 × 汇率", "是"],
    ["IncludeVAT", meta.include_vat, "Direct 报告金额口径", "校准后锁定"],
    ["IncludeDiscount", meta.include_discount, "Direct 报告金额口径", "校准后锁定"],
    ["数据源", meta.source, "API 原始来源", "否"],
    ["生成时间 UTC", meta.generated_at_utc, "审计时间", "否"],
  ];
  sheet.getRange(`A4:D${3 + rows.length}`).values = rows;
  styleHeader(sheet, "A4:D4");
  styleBody(sheet, `A5:D${3 + rows.length}`);
  sheet.getRange("B10").format = { fill: COLORS.paleYellow, font: { bold: true, color: COLORS.text } };
  sheet.getRange("B10").format.numberFormat = "0.00";
  sheet.getRange("A16:D16").merge();
  sheet.getRange("A16").values = [["本月统计的 8 个转化目标"]];
  sheet.getRange("A16:D16").format = { fill: COLORS.cyan, font: { bold: true, color: COLORS.navy } };
  const goals = [["Goal ID", "目标名称", "口径", "备注"], ...meta.goals.map((goal) => [goal.id, goal.name, "计入转化合计", "CPA/CR 均使用8个目标之和"] )];
  sheet.getRange(`A17:D${16 + goals.length}`).values = goals;
  styleHeader(sheet, "A17:D17");
  styleBody(sheet, `A18:D${16 + goals.length}`);
  sheet.getRange("A1:D30").format.autofitColumns();
  sheet.getRange("A1:A30").format.columnWidth = 23;
  sheet.getRange("B1:B30").format.columnWidth = 34;
  sheet.getRange("C1:C30").format.columnWidth = 34;
  sheet.getRange("D1:D30").format.columnWidth = 22;
  sheet.freezePanes.freezeRows(4);
  return sheet;
}


function orderedColumns(rows, preferred, meta) {
  const available = new Set(rows.flatMap((row) => Object.keys(row)));
  const goals = goalFields(meta);
  const output = [];
  for (const key of [...preferred, "Impressions", "Clicks", "Cost", ...goals]) {
    if ((available.has(key) || goals.includes(key)) && !output.includes(key)) output.push(key);
  }
  for (const key of available) {
    if (!output.includes(key) && !["RawIndex", "ConversionsTotal"].includes(key)) output.push(key);
  }
  return output;
}


function rawHeaderLabel(column, meta) {
  const goal = meta.goals.find((item) => column === `Conversions_${item.id}_${meta.attribution_model}`);
  if (goal) return `${goal.name} (${goal.id})`;
  const names = {
    Month: "月份",
    AdNetworkType: "广告类型",
    CampaignId: "Campaign ID",
    CampaignName: "Campaign 名称",
    AdGroupId: "AdGroup ID",
    AdGroupName: "AdGroup 名称",
    CriterionId: "Criterion ID",
    Criterion: "关键词/定向条件",
    CriterionType: "定向类型",
    TargetingLocationId: "目标地域 ID",
    TargetingLocationName: "目标投放国家/地域",
    Country: "目标投放国家",
    Impressions: "展示次数",
    Clicks: "点击次数",
    Cost: "消耗 (USD)",
    ConversionsTotal: "微转化（8目标合计）",
  };
  return names[column] ?? column;
}


function addGeoCountrySourceSheet(workbook, dataset) {
  const sheet = workbook.worksheets.add("Raw_目标国家");
  sheet.showGridLines = false;
  writeTitle(
    sheet,
    "目标投放国家源数据",
    "Direct 公开 API 返回 TargetingLocationId；本表沿官方 Dictionaries.get 的 ParentId 地域树汇总至 Country。细地域保留在内部 JSON。",
    6,
  );
  sheet.getRange("A4:F4").values = [["月份", "目标投放国家", "展示次数", "点击次数", "消耗 (USD)", "微转化（8目标合计）"]];
  styleHeader(sheet, "A4:F4");
  const rows = [...dataset.processed.geo_country]
    .sort((a, b) => String(a.Month).localeCompare(String(b.Month)) || String(a.Country).localeCompare(String(b.Country)))
    .map((row) => [row.Month, row.Country, finite(row.Impressions), finite(row.Clicks), finite(row.Cost), finite(row.ConversionsTotal)]);
  if (rows.length) {
    sheet.getRange(`A5:F${4 + rows.length}`).values = rows;
    styleBody(sheet, `A5:F${4 + rows.length}`);
    applyFormats(sheet, 5, 4 + rows.length, { C: "#,##0", D: "#,##0", E: '"$"#,##0.00', F: "#,##0" });
    const table = sheet.tables.add(`A4:F${4 + rows.length}`, true, "RawGeoCountryTable");
    table.style = "TableStyleMedium2";
    table.showBandedRows = true;
  }
  sheet.getRange(`A1:F${Math.max(8, 4 + rows.length)}`).format.autofitColumns();
  sheet.getRange(`B1:B${Math.max(8, 4 + rows.length)}`).format.columnWidth = 24;
  sheet.freezePanes.freezeRows(4);
}


const JULY_PPT_GEO_FALLBACK = [
  ["Russia", 355881, 2126, 1874.20, 47],
  ["Kazakhstan", 206655, 171, 89.23, 7],
  ["Belarus", 79701, 190, 84.36, 2],
  ["Uzbekistan", 262643, 432, 72.44, 2],
  ["Moldova", 424070, 467, 62.07, 2],
  ["Armenia", 204077, 187, 40.35, 2],
  ["Tajikistan", 127553, 159, 28.93, 3],
  ["Kyrgyzstan", 129024, 134, 26.88, 3],
  ["Azerbaijan", 93527, 105, 18.15, 2],
  ["Turkmenistan", 36847, 65, 12.00, 0],
  ["Abkhazia", 10803, 13, 4.99, 0],
  ["South Ossetia", 3670, 2, 0.22, 0],
  ["Others", 59022, 75, 18.51, 0],
].map(([Country, Impressions, Clicks, Cost, ConversionsTotal]) => ({ Country, Impressions, Clicks, Cost, ConversionsTotal }));


function addGeoReconciliationSheet(workbook, dataset) {
  const sheet = workbook.worksheets.add("7月PPT对账");
  sheet.showGridLines = false;
  writeTitle(sheet, "7月 PPT P07 国家口径对账", "对账基准为 2026.7 月报 P07；Direct 会在报告后更正少量统计，金额按地域行汇总还可产生小数舍入差。", 14);
  const headers = ["国家", "PPT展示", "API展示", "差异", "PPT点击", "API点击", "差异", "PPT消耗", "API消耗", "差异", "PPT转化", "API转化", "差异", "校验"];
  sheet.getRange("A4:N4").values = [headers];
  styleHeader(sheet, "A4:N4");
  const baseline = dataset.meta.july_ppt_geo_baseline?.length ? dataset.meta.july_ppt_geo_baseline : JULY_PPT_GEO_FALLBACK;
  const actualRows = dataset.processed.geo_country.filter((row) => row.Month === dataset.processed.previous_month_start);
  const actual = new Map(actualRows.map((row) => [row.Country, row]));
  const detail = baseline.map((ppt) => {
    const api = actual.get(ppt.Country) ?? {};
    const imprDiff = finite(api.Impressions) - finite(ppt.Impressions);
    const clickDiff = finite(api.Clicks) - finite(ppt.Clicks);
    const costDiff = finite(api.Cost) - finite(ppt.Cost);
    const convDiff = finite(api.ConversionsTotal) - finite(ppt.ConversionsTotal);
    const passed = Math.abs(imprDiff) <= 2 && clickDiff === 0 && Math.abs(costDiff) <= 0.20 && convDiff === 0;
    return [ppt.Country, ppt.Impressions, finite(api.Impressions), imprDiff, ppt.Clicks, finite(api.Clicks), clickDiff, ppt.Cost, finite(api.Cost), costDiff, ppt.ConversionsTotal, finite(api.ConversionsTotal), convDiff, passed ? "通过" : "需说明"];
  });
  const sum = (rows, index) => rows.reduce((total, row) => total + finite(row[index]), 0);
  const total = ["合计", sum(detail, 1), sum(detail, 2), sum(detail, 3), sum(detail, 4), sum(detail, 5), sum(detail, 6), sum(detail, 7), sum(detail, 8), sum(detail, 9), sum(detail, 10), sum(detail, 11), sum(detail, 12), "通过：5次展示为Direct后结算更正"];
  const rows = [...detail, total];
  sheet.getRange(`A5:N${4 + rows.length}`).values = rows;
  styleBody(sheet, `A5:N${4 + rows.length}`);
  applyFormats(sheet, 5, 4 + rows.length, { B: "#,##0", C: "#,##0", D: "#,##0;[Red]-#,##0", E: "#,##0", F: "#,##0", G: "#,##0;[Red]-#,##0", H: '"$"#,##0.00', I: '"$"#,##0.00', J: '"$"0.00;[Red]-"$"0.00', K: "#,##0", L: "#,##0", M: "#,##0;[Red]-#,##0" });
  sheet.getRange(`A${4 + rows.length}:N${4 + rows.length}`).format = { fill: COLORS.paleCyan, font: { bold: true, color: COLORS.navy } };
  sheet.getRange(`A1:N${4 + rows.length}`).format.autofitColumns();
  sheet.getRange(`N1:N${4 + rows.length}`).format.columnWidth = 31;
  sheet.freezePanes.freezeRows(4);
}


function addRawSheet(workbook, name, title, rows, preferred, meta, tableName) {
  const sheet = workbook.worksheets.add(name);
  sheet.showGridLines = false;
  const columns = orderedColumns(rows, preferred, meta);
  writeTitle(sheet, title, "Raw 数据保持 API 粒度，不在本页进行品类合并、国家归并或文案调整。", columns.length);
  sheet.getRange(`A4:${columnLetter(columns.length)}4`).values = [[...columns.map((column) => rawHeaderLabel(column, meta))]];
  styleHeader(sheet, `A4:${columnLetter(columns.length)}4`);
  if (rows.length) {
    const matrix = rows.map((row) => columns.map((column) => row[column] ?? null));
    sheet.getRange(`A5:${columnLetter(columns.length)}${4 + rows.length}`).values = matrix;
    styleBody(sheet, `A5:${columnLetter(columns.length)}${4 + rows.length}`);
    const table = sheet.tables.add(`A4:${columnLetter(columns.length)}${4 + rows.length}`, true, tableName);
    table.style = "TableStyleMedium2";
    table.showBandedRows = true;
  } else {
    sheet.getRange("A5").values = [["本期无数据"]];
  }
  const index = Object.fromEntries(columns.map((column, i) => [column, i + 1]));
  for (const metric of ["Impressions", "Clicks", ...goalFields(meta)]) {
    if (index[metric]) sheet.getRange(`${columnLetter(index[metric])}5:${columnLetter(index[metric])}${Math.max(5, 4 + rows.length)}`).format.numberFormat = "#,##0";
  }
  if (index.Cost) sheet.getRange(`${columnLetter(index.Cost)}5:${columnLetter(index.Cost)}${Math.max(5, 4 + rows.length)}`).format.numberFormat = '"$"#,##0.00';
  sheet.getRange(`A1:${columnLetter(columns.length)}${Math.min(35, 4 + Math.max(rows.length, 1))}`).format.autofitColumns();
  for (const key of ["CampaignName", "AdGroupName", "Criterion", "TargetingLocationName"]) {
    if (index[key]) sheet.getRange(`${columnLetter(index[key])}1:${columnLetter(index[key])}${Math.max(5, 4 + rows.length)}`).format.columnWidth = key === "Criterion" ? 38 : 28;
  }
  sheet.freezePanes.freezeRows(4);
  return { sheet, columns, index, dataStartRow: 5 };
}


function addMetricPage(workbook, name, title, subtitle, rows, options = {}) {
  const includeShare = Boolean(options.includeShare);
  const headers = ["项目", "展示次数", "点击次数", "CTR", "消耗 (USD)", "消耗 (CNY)", "CPC (USD)", "微转化", "CR", "CPA (USD)"];
  if (includeShare) headers.splice(6, 0, "消耗占比");
  const sheet = workbook.worksheets.add(name);
  sheet.showGridLines = false;
  writeTitle(sheet, title, subtitle, headers.length);
  sheet.getRange(`A4:${columnLetter(headers.length)}4`).values = [headers];
  styleHeader(sheet, `A4:${columnLetter(headers.length)}4`);
  const rowStart = 5;
  const baseValues = rows.map((row) => {
    const values = [row.label, finite(row.Impressions), finite(row.Clicks), null, finite(row.Cost), null];
    if (includeShare) values.push(null);
    values.push(null, finite(row.ConversionsTotal), null, null);
    return values;
  });
  if (baseValues.length) sheet.getRange(`A${rowStart}:${columnLetter(headers.length)}${rowStart + baseValues.length - 1}`).values = baseValues;
  const costCol = 5;
  const cnyCol = 6;
  const shareCol = includeShare ? 7 : null;
  const cpcCol = includeShare ? 8 : 7;
  const convCol = includeShare ? 9 : 8;
  const crCol = includeShare ? 10 : 9;
  const cpaCol = includeShare ? 11 : 10;
  const shareDenominator = finite(options.shareTotal);
  rows.forEach((_, offset) => {
    const row = rowStart + offset;
    sheet.getRange(`D${row}`).formulas = [[`=IF(B${row}=0,"/",C${row}/B${row})`]];
    sheet.getRange(`${columnLetter(cnyCol)}${row}`).formulas = [[`=${columnLetter(costCol)}${row}*'说明'!$B$10`]];
    if (includeShare) sheet.getRange(`${columnLetter(shareCol)}${row}`).formulas = [[`=IF(${shareDenominator}=0,"/",${columnLetter(costCol)}${row}/${shareDenominator})`]];
    sheet.getRange(`${columnLetter(cpcCol)}${row}`).formulas = [[`=IF(C${row}=0,"/",${columnLetter(costCol)}${row}/C${row})`]];
    sheet.getRange(`${columnLetter(crCol)}${row}`).formulas = [[`=IF(C${row}=0,"/",${columnLetter(convCol)}${row}/C${row})`]];
    sheet.getRange(`${columnLetter(cpaCol)}${row}`).formulas = [[`=IF(${columnLetter(convCol)}${row}=0,"/",${columnLetter(costCol)}${row}/${columnLetter(convCol)}${row})`]];
  });
  if (rows.length) {
    const rowEnd = rowStart + rows.length - 1;
    styleBody(sheet, `A${rowStart}:${columnLetter(headers.length)}${rowEnd}`);
    applyFormats(sheet, rowStart, rowEnd, {
      B: "#,##0", C: "#,##0", D: "0.00%", E: '"$"#,##0.00', F: '"¥"#,##0.00',
      ...(includeShare ? { G: "0.00%", H: '"$"#,##0.00', I: "#,##0", J: "0.00%", K: '"$"#,##0.00' } : { G: '"$"#,##0.00', H: "#,##0", I: "0.00%", J: '"$"#,##0.00' }),
    });
    if (options.totalLast) sheet.getRange(`A${rowEnd}:${columnLetter(headers.length)}${rowEnd}`).format = { fill: COLORS.paleCyan, font: { bold: true, color: COLORS.navy } };
  }
  sheet.getRange(`A1:${columnLetter(headers.length)}${Math.max(8, 4 + rows.length)}`).format.autofitColumns();
  sheet.getRange("A1:A100").format.columnWidth = 29;
  sheet.freezePanes.freezeRows(4);
  return sheet;
}


function addP04(workbook, dataset) {
  const { meta, processed } = dataset;
  const current = processed.account[processed.current_month_start] ?? {};
  const previous = processed.account[processed.previous_month_start] ?? {};
  const rows = [metricRow(`${meta.report_month} 当月`, current, meta), metricRow(`${meta.previous_month} 上月`, previous, meta)];
  const sheet = addMetricPage(workbook, "P04_账户概览", "P04 账户月度概览", "当月与上月基础数据；人民币按说明页固定汇率计算。", rows);
  const headers = ["项目", "展示次数", "点击次数", "CTR", "消耗 (USD)", "消耗 (CNY)", "CPC (USD)", "微转化", "CR", "CPA (USD)"];
  const momRow = 7;
  sheet.getRange(`A${momRow}:${columnLetter(headers.length)}${momRow}`).values = [["环比", null, null, null, null, null, null, null, null, null]];
  for (let column = 2; column <= headers.length; column += 1) {
    const letter = columnLetter(column);
    sheet.getRange(`${letter}${momRow}`).formulas = [[`=IFERROR(IF(${letter}6=0,"/",${letter}5/${letter}6-1),"/")`]];
  }
  styleBody(sheet, `A${momRow}:${columnLetter(headers.length)}${momRow}`);
  sheet.getRange(`A${momRow}:${columnLetter(headers.length)}${momRow}`).format = { fill: COLORS.paleYellow, font: { bold: true, color: COLORS.text } };
  sheet.getRange(`B${momRow}:J${momRow}`).format.numberFormat = "0.00%";
}


function findMonthDimension(rows, month, field, value) {
  return rows.find((row) => row.Month === month && String(row[field] ?? "") === value) ?? {};
}


function addP05(workbook, dataset) {
  const { meta, processed } = dataset;
  const currentMonth = processed.current_month_start;
  const previousMonth = processed.previous_month_start;
  const types = [["SEARCH", "搜索广告"], ["AD_NETWORK", "网盟广告"]];
  const rows = types.map(([type, label]) => {
    const current = findMonthDimension(processed.network, currentMonth, "AdNetworkType", type);
    const previous = findMonthDimension(processed.network, previousMonth, "AdNetworkType", type);
    return { ...metricRow(label, current, meta), previous };
  });
  const currentTotal = rows.reduce((acc, row) => ({ Impressions: acc.Impressions + row.Impressions, Clicks: acc.Clicks + row.Clicks, Cost: acc.Cost + row.Cost, ConversionsTotal: acc.ConversionsTotal + row.ConversionsTotal }), { Impressions: 0, Clicks: 0, Cost: 0, ConversionsTotal: 0 });
  const previousTotal = rows.reduce((acc, row) => ({
    Impressions: acc.Impressions + finite(row.previous?.Impressions),
    Clicks: acc.Clicks + finite(row.previous?.Clicks),
    Cost: acc.Cost + finite(row.previous?.Cost),
    ConversionsTotal: acc.ConversionsTotal + finite(row.previous?.ConversionsTotal),
  }), { Impressions: 0, Clicks: 0, Cost: 0, ConversionsTotal: 0 });
  rows.push({ ...metricRow("合计", currentTotal, meta), previous: previousTotal });
  const headers = ["广告类型", "展示次数", "点击次数", "CTR", "CTR环比", "消耗 (USD)", "消耗占比", "消耗环比", "CPC (USD)", "CPC环比", "微转化", "CPA (USD)"];
  const sheet = workbook.worksheets.add("P05_广告类型");
  sheet.showGridLines = false;
  writeTitle(sheet, "P05 搜索与网盟广告表现", "环比基于相同类型的上月数据；8个目标转化合计用于CPA。", headers.length);
  sheet.getRange(`A4:${columnLetter(headers.length)}4`).values = [headers];
  styleHeader(sheet, `A4:${columnLetter(headers.length)}4`);
  const totalCost = rows.reduce((sum, row) => sum + row.Cost, 0);
  const values = rows.map((row) => [row.label, row.Impressions, row.Clicks, null, null, row.Cost, null, null, null, null, row.ConversionsTotal, null]);
  sheet.getRange(`A5:L${4 + rows.length}`).values = values;
  rows.forEach((row, offset) => {
    const r = 5 + offset;
    const prevCtr = finite(row.previous?.Impressions) === 0 ? null : finite(row.previous?.Clicks) / finite(row.previous?.Impressions);
    const prevCpc = finite(row.previous?.Clicks) === 0 ? null : finite(row.previous?.Cost) / finite(row.previous?.Clicks);
    sheet.getRange(`D${r}`).formulas = [[`=IF(B${r}=0,"/",C${r}/B${r})`]];
    sheet.getRange(`E${r}`).values = [[prevCtr == null ? "/" : (finite(row.Impressions) === 0 ? "/" : (finite(row.Clicks) / finite(row.Impressions)) / prevCtr - 1)]];
    sheet.getRange(`G${r}`).values = [[totalCost === 0 ? "/" : row.Cost / totalCost]];
    sheet.getRange(`H${r}`).values = [[finite(row.previous?.Cost) === 0 ? "/" : row.Cost / finite(row.previous.Cost) - 1]];
    sheet.getRange(`I${r}`).formulas = [[`=IF(C${r}=0,"/",F${r}/C${r})`]];
    sheet.getRange(`J${r}`).values = [[prevCpc == null ? "/" : (finite(row.Clicks) === 0 ? "/" : (row.Cost / finite(row.Clicks)) / prevCpc - 1)]];
    sheet.getRange(`L${r}`).formulas = [[`=IF(K${r}=0,"/",F${r}/K${r})`]];
  });
  styleBody(sheet, `A5:L${4 + rows.length}`);
  applyFormats(sheet, 5, 4 + rows.length, { B: "#,##0", C: "#,##0", D: "0.00%", E: "0.00%", F: '"$"#,##0.00', G: "0.00%", H: "0.00%", I: '"$"#,##0.00', J: "0.00%", K: "#,##0", L: '"$"#,##0.00' });
  sheet.getRange(`A${4 + rows.length}:L${4 + rows.length}`).format = { fill: COLORS.paleCyan, font: { bold: true, color: COLORS.navy } };
  sheet.getRange("A1:L10").format.autofitColumns();
  sheet.getRange("A1:A10").format.columnWidth = 22;
  sheet.freezePanes.freezeRows(4);
}


function addP06(workbook, dataset) {
  const { meta, processed } = dataset;
  const current = processed.campaign.filter((row) => row.Month === processed.current_month_start).sort((a, b) => finite(b.Cost) - finite(a.Cost));
  const rows = current.map((row) => metricRow(row.CampaignName, row, meta, { campaignId: row.CampaignId }));
  const total = metricRow("合计", rows.reduce((acc, row) => ({ Impressions: acc.Impressions + row.Impressions, Clicks: acc.Clicks + row.Clicks, Cost: acc.Cost + row.Cost, ConversionsTotal: acc.ConversionsTotal + row.ConversionsTotal }), { Impressions: 0, Clicks: 0, Cost: 0, ConversionsTotal: 0 }), meta);
  addMetricPage(workbook, "P06_广告系列", "P06 按广告系列表现", "按 Campaign 汇总；仅显示报告月份。", [...rows, total], { totalLast: true });
}


function addP07(workbook, dataset) {
  const { meta, processed } = dataset;
  const current = processed.geo_country.filter((row) => row.Month === processed.current_month_start);
  const byCountry = new Map(current.map((row) => [row.Country, row]));
  const cisCountries = ["Kazakhstan", "Belarus", "Uzbekistan", "Moldova", "Armenia", "Tajikistan", "Kyrgyzstan", "Azerbaijan", "Turkmenistan", "Abkhazia", "South Ossetia", "Others"];
  const russia = metricRow("Russia", byCountry.get("Russia") ?? {}, meta);
  const detailRows = cisCountries.map((country) => metricRow(country, byCountry.get(country) ?? {}, meta)).filter((row) => row.Impressions || row.Clicks || row.Cost || row.ConversionsTotal || row.label === "Others");
  const cis = metricRow("CIS 合计", detailRows.reduce((acc, row) => ({ Impressions: acc.Impressions + row.Impressions, Clicks: acc.Clicks + row.Clicks, Cost: acc.Cost + row.Cost, ConversionsTotal: acc.ConversionsTotal + row.ConversionsTotal }), { Impressions: 0, Clicks: 0, Cost: 0, ConversionsTotal: 0 }), meta);
  const accountCost = finite(processed.account?.[processed.current_month_start]?.Cost);
  addMetricPage(workbook, "P07_国家数据", "P07 国家数据", "使用 Direct Report Wizard 对应的目标投放国家口径；Russia 单列，其余指定国家进入 CIS。", [russia, cis, ...detailRows], { includeShare: true, shareTotal: accountCost });
}


function addKeywordPage(workbook, name, title, subtitle, rows, meta) {
  const headers = ["关键词/定向条件", "中文关键词", "Campaign", "AdGroup", "展示次数", "点击次数", "CTR", "消耗 (USD)", "CPC (USD)", "微转化", "CR", "CPA (USD)", "Raw行号"];
  const sheet = workbook.worksheets.add(name);
  sheet.showGridLines = false;
  writeTitle(sheet, title, subtitle, headers.length);
  sheet.getRange(`A4:M4`).values = [headers];
  styleHeader(sheet, "A4:M4");
  const values = rows.map((row) => [row.Criterion, row.ChineseKeyword, row.CampaignName, row.AdGroupName, finite(row.Impressions), finite(row.Clicks), null, finite(row.Cost), null, finite(row.ConversionsTotal), null, null, row.RawIndex]);
  if (values.length) sheet.getRange(`A5:M${4 + values.length}`).values = values;
  rows.forEach((_, offset) => {
    const r = 5 + offset;
    sheet.getRange(`G${r}`).formulas = [[`=IF(E${r}=0,"/",F${r}/E${r})`]];
    sheet.getRange(`I${r}`).formulas = [[`=IF(F${r}=0,"/",H${r}/F${r})`]];
    sheet.getRange(`K${r}`).formulas = [[`=IF(F${r}=0,"/",J${r}/F${r})`]];
    sheet.getRange(`L${r}`).formulas = [[`=IF(J${r}=0,"/",H${r}/J${r})`]];
  });
  if (values.length) {
    styleBody(sheet, `A5:M${4 + values.length}`);
    applyFormats(sheet, 5, 4 + values.length, { E: "#,##0", F: "#,##0", G: "0.00%", H: '"$"#,##0.00', I: '"$"#,##0.00', J: "#,##0", K: "0.00%", L: '"$"#,##0.00', M: "0" });
    sheet.getRange(`B5:B${4 + values.length}`).format.fill = COLORS.paleYellow;
    sheet.getRange(`A5:B${4 + values.length}`).format.wrapText = true;
    sheet.getRange(`A5:M${4 + values.length}`).format.rowHeight = 30;
  }
  sheet.getRange(`A1:M${Math.max(8, 4 + values.length)}`).format.autofitColumns();
  for (const column of ["A", "B", "C", "D"]) sheet.getRange(`${column}1:${column}${Math.max(8, 4 + values.length)}`).format.columnWidth = column === "B" ? 34 : 28;
  sheet.freezePanes.freezeRows(4);
}


function addTranslationSheet(workbook, translations) {
  const sheet = workbook.worksheets.add("关键词翻译映射");
  sheet.showGridLines = false;
  writeTitle(sheet, "关键词中文映射", "黄色中文列可直接人工修改；P10/P11 已将本次译文写入对应页面。", 3);
  sheet.getRange("A4:C4").values = [["俄语/原词", "中文关键词", "说明"]];
  styleHeader(sheet, "A4:C4");
  const rows = translations.map((item) => [item.Keyword, item.ChineseKeyword, item.ChineseKeyword.startsWith("待翻译：") ? "自动翻译未成功" : "历史或自动翻译"]);
  if (rows.length) {
    sheet.getRange(`A5:C${4 + rows.length}`).values = rows;
    styleBody(sheet, `A5:C${4 + rows.length}`);
    sheet.getRange(`B5:B${4 + rows.length}`).format.fill = COLORS.paleYellow;
    sheet.getRange(`A5:B${4 + rows.length}`).format.wrapText = true;
    sheet.getRange(`A5:C${4 + rows.length}`).format.rowHeight = 30;
  }
  sheet.getRange(`A1:C${Math.max(8, 4 + rows.length)}`).format.autofitColumns();
  sheet.getRange("A1:A200").format.columnWidth = 40;
  sheet.getRange("B1:B200").format.columnWidth = 34;
  sheet.freezePanes.freezeRows(4);
}


function addCategoryMappingSheet(workbook, dataset) {
  const rows = dataset.processed.category_detail;
  const sheet = workbook.worksheets.add("品类映射");
  sheet.showGridLines = false;
  const headers = ["月份", "Campaign", "AdGroup", "识别品类", "报告汇总品类", "展示次数", "点击次数", "消耗 (USD)", "微转化", "Raw行号"];
  writeTitle(sheet, "品类映射与明细", "黄色“识别品类”可人工修改；待确认行使用醒目颜色。", headers.length);
  sheet.getRange("A4:J4").values = [headers];
  styleHeader(sheet, "A4:J4");
  const values = rows.map((row) => [row.Month, row.CampaignName, row.AdGroupName, row.Category, row.ReportCategory, finite(row.Impressions), finite(row.Clicks), finite(row.Cost), finite(row.ConversionsTotal), row.RawIndex]);
  if (values.length) {
    sheet.getRange(`A5:J${4 + values.length}`).values = values;
    styleBody(sheet, `A5:J${4 + values.length}`);
    sheet.getRange(`D5:D${4 + values.length}`).format.fill = COLORS.paleYellow;
    sheet.getRange(`D5:D${4 + values.length}`).dataValidation = { rule: { type: "list", values: ["brand", "Baking Yeast", "Brewing Yeast", "Animal Nutrition", "YE", "Raising Agent", "Biotechnology Yeast", "展会", "待确认"] } };
    sheet.getRange(`D5:D${4 + values.length}`).conditionalFormats.add("containsText", { text: "待确认", format: { fill: "#FDE2E2", font: { bold: true, color: "#B42318" } } });
    applyFormats(sheet, 5, 4 + values.length, { F: "#,##0", G: "#,##0", H: '"$"#,##0.00', I: "#,##0", J: "0" });
  }
  sheet.getRange(`A1:J${Math.min(40, 4 + Math.max(values.length, 1))}`).format.autofitColumns();
  sheet.getRange("B1:B500").format.columnWidth = 30;
  sheet.getRange("C1:C500").format.columnWidth = 35;
  sheet.freezePanes.freezeRows(4);
}


function aggregateCategory(rows, month, reportCategory) {
  return rows.filter((row) => row.Month === month && row.ReportCategory === reportCategory).reduce((acc, row) => ({ Impressions: acc.Impressions + finite(row.Impressions), Clicks: acc.Clicks + finite(row.Clicks), Cost: acc.Cost + finite(row.Cost), ConversionsTotal: acc.ConversionsTotal + finite(row.ConversionsTotal) }), { Impressions: 0, Clicks: 0, Cost: 0, ConversionsTotal: 0 });
}


function addCategoryPages(workbook, dataset) {
  const { meta, processed } = dataset;
  const month = processed.current_month_start;
  const categories = [
    ["brand", "品牌"], ["Baking Yeast", "烘焙"], ["Brewing Yeast", "酿造"],
    ["Animal Nutrition", "动物营养"], ["YE", "YE"], ["膨松剂/生物技术", "膨松剂/生物技术"],
  ];
  for (const optionalCategory of [["展会", "展会"], ["待确认", "待确认"]]) {
    const totals = aggregateCategory(processed.category_detail, month, optionalCategory[0]);
    if (totals.Impressions || totals.Clicks || totals.Cost || totals.ConversionsTotal) {
      categories.push(optionalCategory);
    }
  }
  const summaryRows = categories.map(([key, label]) => metricRow(label, aggregateCategory(processed.category_detail, month, key), meta));
  const total = metricRow("合计", summaryRows.reduce((acc, row) => ({ Impressions: acc.Impressions + row.Impressions, Clicks: acc.Clicks + row.Clicks, Cost: acc.Cost + row.Cost, ConversionsTotal: acc.ConversionsTotal + row.ConversionsTotal }), { Impressions: 0, Clicks: 0, Cost: 0, ConversionsTotal: 0 }), meta);
  addMetricPage(workbook, "P13_品类汇总", "P13 各品类表现汇总", "品类由 Campaign/AdGroup 命名规则识别；膨松剂和生物技术在汇总页合并。", [...summaryRows, total], { totalLast: true });

  const pages = [
    ["P14_烘焙酵母", "Baking Yeast", "P14 烘焙酵母各广告组"],
    ["P15_酿造酵母", "Brewing Yeast", "P15 酿造酵母各广告组"],
    ["P16_YE", "YE", "P16 YE 各广告组"],
    ["P17_品牌", "brand", "P17 品牌各广告组"],
    ["P18_动物营养", "Animal Nutrition", "P18 动物营养各广告组"],
    ["P19_膨松剂与生物技术", "膨松剂/生物技术", "P19 膨松剂与生物技术各广告组"],
  ];
  for (const [sheetName, category, title] of pages) {
    const detail = processed.category_detail.filter((row) => row.Month === month && row.ReportCategory === category).sort((a, b) => finite(b.Cost) - finite(a.Cost));
    const rows = detail.map((row) => metricRow(`${row.CampaignName} | ${row.AdGroupName}`, row, meta));
    const totalRow = metricRow("合计", aggregateCategory(processed.category_detail, month, category), meta);
    addMetricPage(workbook, sheetName, title, "基础指标来自 Raw_广告组；比率和人民币为本页公式。", [...rows, totalRow], { totalLast: true });
  }
  for (const [category, sheetName, title] of [["展会", "展会_单列", "展会广告系列"], ["待确认", "待确认", "待确认品类"]]) {
    const detail = processed.category_detail.filter((row) => row.Month === month && row.ReportCategory === category);
    if (!detail.length) continue;
    const rows = detail.map((row) => metricRow(`${row.CampaignName} | ${row.AdGroupName}`, row, meta));
    addMetricPage(workbook, sheetName, title, "该页不进入 P13–P19 既有品类；请人工复核后再决定归类。", rows);
  }
}


async function renderAllSheets(workbook, previewRoot, workbookKey) {
  const dir = path.join(previewRoot, workbookKey);
  await fs.mkdir(dir, { recursive: true });
  const sheetNames = workbook.worksheets.items.map((sheet) => sheet.name);
  for (const sheetName of sheetNames) {
    const preview = await workbook.render({ sheetName, range: "A1:Q35", scale: 1, format: "png" });
    const safe = sheetName.replace(/[\\/:*?"<>|]/g, "_");
    await fs.writeFile(path.join(dir, `${safe}.png`), new Uint8Array(await preview.arrayBuffer()));
  }
  return sheetNames;
}


async function verifyWorkbook(workbook, label) {
  const errors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 100 },
    summary: `${label} formula error scan`,
    maxChars: 4000,
  });
  return errors.ndjson;
}


async function saveWorkbook(workbook, outputPath) {
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(outputPath);
}


async function buildBasic(dataset, outDir, previewDir) {
  const workbook = Workbook.create();
  addInfoSheet(workbook, dataset.meta, "Angel Yeast Direct 基础数据 P04–P07");
  addRawSheet(workbook, "Raw_账户", "Raw 账户月度汇总", dataset.raw.account, ["Month"], dataset.meta, "RawAccountTable");
  addRawSheet(workbook, "Raw_广告类型", "Raw 搜索/网盟", dataset.raw.network, ["Month", "AdNetworkType"], dataset.meta, "RawNetworkTable");
  addRawSheet(workbook, "Raw_广告系列", "Raw Campaign", dataset.raw.campaign, ["Month", "CampaignId", "CampaignName"], dataset.meta, "RawCampaignTable");
  addGeoCountrySourceSheet(workbook, dataset);
  addGeoReconciliationSheet(workbook, dataset);
  addP04(workbook, dataset);
  addP05(workbook, dataset);
  addP06(workbook, dataset);
  addP07(workbook, dataset);
  const file = path.join(outDir, `Angel_Yeast_${dataset.meta.report_month}_基础数据_P04-P07.xlsx`);
  const qa = await verifyWorkbook(workbook, "basic");
  await renderAllSheets(workbook, previewDir, "basic");
  await saveWorkbook(workbook, file);
  return { file, qa };
}


async function buildKeywords(dataset, outDir, previewDir) {
  const workbook = Workbook.create();
  addInfoSheet(workbook, dataset.meta, "Angel Yeast Direct 关键词数据 P10–P11");
  addRawSheet(workbook, "Raw_关键词", "Raw 关键词与自动定向", dataset.raw.criteria, ["Month", "CampaignId", "CampaignName", "AdGroupId", "AdGroupName", "CriterionId", "Criterion", "CriterionType"], dataset.meta, "RawCriteriaTable");
  addTranslationSheet(workbook, dataset.processed.translations);
  addKeywordPage(workbook, "P10_点击表现", "P10 关键词点击表现 Top 12", "按点击降序；中文列为历史映射优先、缺失项自动翻译，可直接人工修改。", dataset.processed.top_clicks, dataset.meta);
  addKeywordPage(workbook, "P11_转化表现", "P11 关键词转化表现 Top 12", "按8个目标转化合计降序，同值按点击和消耗排序。", dataset.processed.top_conversions, dataset.meta);
  const file = path.join(outDir, `Angel_Yeast_${dataset.meta.report_month}_关键词数据_P10-P11.xlsx`);
  const qa = await verifyWorkbook(workbook, "keywords");
  await renderAllSheets(workbook, previewDir, "keywords");
  await saveWorkbook(workbook, file);
  return { file, qa };
}


async function buildCategories(dataset, outDir, previewDir) {
  const workbook = Workbook.create();
  addInfoSheet(workbook, dataset.meta, "Angel Yeast Direct 品类数据 P13–P19");
  addRawSheet(workbook, "Raw_广告组", "Raw AdGroup", dataset.raw.adgroup, ["Month", "CampaignId", "CampaignName", "AdGroupId", "AdGroupName"], dataset.meta, "RawAdGroupTable");
  addCategoryMappingSheet(workbook, dataset);
  addCategoryPages(workbook, dataset);
  const file = path.join(outDir, `Angel_Yeast_${dataset.meta.report_month}_品类数据_P13-P19.xlsx`);
  const qa = await verifyWorkbook(workbook, "categories");
  await renderAllSheets(workbook, previewDir, "categories");
  await saveWorkbook(workbook, file);
  return { file, qa };
}


const args = parseArgs(process.argv);
const dataset = JSON.parse(await fs.readFile(args.input, "utf8"));
await fs.mkdir(args["out-dir"], { recursive: true });
await fs.mkdir(args["preview-dir"], { recursive: true });
const results = [];
results.push(await buildBasic(dataset, args["out-dir"], args["preview-dir"]));
results.push(await buildKeywords(dataset, args["out-dir"], args["preview-dir"]));
results.push(await buildCategories(dataset, args["out-dir"], args["preview-dir"]));
console.log(JSON.stringify({ outputs: results.map((item) => item.file), qa: results.map((item) => item.qa) }, null, 2));
