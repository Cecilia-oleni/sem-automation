// 模块：sem_automation/reporting/renderers/yutong/search_network.mjs；内部模块由统一入口调用。
// VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化 - 副本'
// 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' reports yutong --config '.\config\reports\yutong\2026-08.json' --month 2026-08
// 该示例复用本地数据；详见 docs/月报操作说明.md。
import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const configPath = process.argv[2];
const workbookPath = process.argv[3];
if (!configPath || !workbookPath) throw new Error("Usage: update_search_network.mjs <config.json> <monthly-output.xlsx>");
const config = JSON.parse(await fs.readFile(configPath, "utf8"));
const rate = config.exchangeRateCnyPerUsd;
const periods=config._periods;
const growth = (current, previous) => previous ? current / previous - 1 : "/";

async function loadWorkbook(filePath) {
  return SpreadsheetFile.importXlsx(await FileBlob.load(filePath));
}

async function readPlatformData(filePath) {
  const workbook = await loadWorkbook(filePath);
  const sheet = workbook.worksheets.getItem("Sheet0");
  const key=Object.keys(config.paths).find(k=>config.paths[k]===filePath);
  const all=config._books[key].Sheet0;
  const header=all.findIndex(r=>r.includes('Impressions')&&r.includes('Clicks'));
  if(header<0)throw new Error(`无法识别搜索网盟表头: ${filePath}`);
  const h=all[header], indexes=[0,h.indexOf('Impressions'),h.indexOf('Clicks'),h.findIndex(v=>String(v).startsWith('Conversions')),h.findIndex(v=>String(v).startsWith('Cost')||String(v).startsWith('Expenditure'))];
  if(indexes.some(i=>i<0))throw new Error('搜索网盟缺少指标列');
  const values=[h,...all.slice(header+1).filter(r=>['Total','Network','Search'].includes(r[0])).map(r=>indexes.map(i=>r[i]))];
  const result = new Map();
  for (const row of values.slice(1)) {
    if(result.has(row[0]))throw new Error(`重复广告类型 ${row[0]}`);
    result.set(row[0], {
      impressions: Number(row[1]),
      clicks: Number(row[2]),
      conversions: Number(row[3]),
      spendUsd: Number(row[4]),
    });
  }
  for (const key of ["Total", "Network", "Search"]) {
    if (!result.has(key)) throw new Error(`Missing ${key} row in ${filePath}`);
  }
  return result;
}

function enrich(row) {
  const spendCny = row.spendUsd * rate;
  return {
    ...row,
    spendCny,
    ctr: row.impressions ? row.clicks / row.impressions : "/",
    cpcUsd: row.clicks ? row.spendUsd / row.clicks : "/",
    cpcCny: row.clicks ? spendCny / row.clicks : "/",
    conversionCostCny: row.conversions ? spendCny / row.conversions : "/",
  };
}

const current = new Map([...await readPlatformData(config.paths.searchNetworkCurrent)].map(([key, value]) => [key, enrich(value)]));
const priorMonth = new Map([...await readPlatformData(config.paths.searchNetworkPriorMonth)].map(([key, value]) => [key, enrich(value)]));
const priorYear = new Map([...await readPlatformData(config.paths.searchNetworkPriorYear)].map(([key, value]) => [key, enrich(value)]));
const currentTotal = current.get("Total");
const priorMonthTotal = priorMonth.get("Total");
const priorYearTotal = priorYear.get("Total");
const leads = config.leadComparisonTotals;

const topRows = [
  [null, periods.current, "美金", "环比", "同比", periods.previous, periods.yearAgo],
  ["消耗", currentTotal.spendCny, currentTotal.spendUsd, growth(currentTotal.spendCny, priorMonthTotal.spendCny), growth(currentTotal.spendCny, priorYearTotal.spendCny), priorMonthTotal.spendCny, priorYearTotal.spendCny],
  ["展示", currentTotal.impressions, null, growth(currentTotal.impressions, priorMonthTotal.impressions), growth(currentTotal.impressions, priorYearTotal.impressions), priorMonthTotal.impressions, priorYearTotal.impressions],
  ["点击", currentTotal.clicks, null, growth(currentTotal.clicks, priorMonthTotal.clicks), growth(currentTotal.clicks, priorYearTotal.clicks), priorMonthTotal.clicks, priorYearTotal.clicks],
  ["单次点击成本", currentTotal.cpcCny, null, growth(currentTotal.cpcCny, priorMonthTotal.cpcCny), growth(currentTotal.cpcCny, priorYearTotal.cpcCny), priorMonthTotal.cpcCny, priorYearTotal.cpcCny],
  ["点击率", currentTotal.ctr, null, growth(currentTotal.ctr, priorMonthTotal.ctr), growth(currentTotal.ctr, priorYearTotal.ctr), priorMonthTotal.ctr, priorYearTotal.ctr],
  ["线索数量", leads.current, null, growth(leads.current, leads.priorMonth), growth(leads.current, leads.priorYear), leads.priorMonth, leads.priorYear],
  ["线索成本", currentTotal.spendCny / leads.current, null, growth(currentTotal.spendCny / leads.current, priorMonthTotal.spendCny / leads.priorMonth), growth(currentTotal.spendCny / leads.current, priorYearTotal.spendCny / leads.priorYear), priorMonthTotal.spendCny / leads.priorMonth, priorYearTotal.spendCny / leads.priorYear],
];

const detailHeaders = [
  "广告类型", "总费用", "花费占比", "总费用 同比", "展示", "互动数", "互动率",
  "平均费用人民币(cpc)", "平均每次点击费用同比(cpc)", "转化数量", "转化成本",
  `${periods.current} 消耗美金`, `${periods.yearAgo} 消耗人民币`, `${periods.current} CPC美金`, `${periods.yearAgo} CPC人民币`,
];

function detailRow(label, key) {
  const now = current.get(key);
  const year = priorYear.get(key);
  return [
    label, now.spendCny, now.spendUsd / currentTotal.spendUsd, growth(now.spendUsd, year.spendUsd),
    now.impressions, now.clicks, now.ctr, now.cpcCny, growth(now.cpcUsd, year.cpcUsd),
    now.conversions, now.conversionCostCny, now.spendUsd, year.spendCny, now.cpcUsd, year.cpcCny,
  ];
}

const detailRows = [
  detailHeaders,
  detailRow("搜索广告系列", "Search"),
  detailRow("展示广告系列", "Network"),
  detailRow("合计", "Total"),
];

const workbook = await loadWorkbook(workbookPath);
const sheet = workbook.worksheets.getItem("Sheet1");
sheet.getRange("A1:G8").values = topRows;
sheet.getRange("A13:O16").values = detailRows;
sheet.getRange('A13:O13').format={wrapText:true,rowHeight:54};
sheet.getRange("N14:N16").setNumberFormat("0.00");

const validation = {
  client: config.client,
  reportMonth: config.reportMonth,
  exchangeRateCnyPerUsd: rate,
  leads,
  sourceTotals: {
    current: currentTotal,
    priorMonth: priorMonthTotal,
    priorYear: priorYearTotal,
  },
  checks: {
    currentSpendPartsUsd: current.get("Search").spendUsd + current.get("Network").spendUsd - currentTotal.spendUsd,
    currentImpressionParts: current.get("Search").impressions + current.get("Network").impressions - currentTotal.impressions,
    currentClickParts: current.get("Search").clicks + current.get("Network").clicks - currentTotal.clicks,
    currentConversionParts: current.get("Search").conversions + current.get("Network").conversions - currentTotal.conversions,
  },
};
for (const [name, value] of Object.entries(validation.checks)) {
  if (Math.abs(value) > 1e-9) throw new Error(`Reconciliation failed: ${name}=${value}`);
}

workbook.recalculate();
const exported = await SpreadsheetFile.exportXlsx(workbook);
await exported.save(workbookPath);
const validationPath = path.join(path.dirname(workbookPath), "search_network_validation.json");
await fs.writeFile(validationPath, `${JSON.stringify(validation, null, 2)}\n`, "utf8");
console.log(JSON.stringify({ workbookPath, validationPath, validation }, null, 2));
