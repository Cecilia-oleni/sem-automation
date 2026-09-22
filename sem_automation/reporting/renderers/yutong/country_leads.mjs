// 模块：sem_automation/reporting/renderers/yutong/country_leads.mjs；内部模块由统一入口调用。
// VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化 - 副本'
// 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' reports yutong --config '.\config\reports\yutong\2026-08.json' --month 2026-08
// 该示例复用本地数据；详见 docs/月报操作说明.md。
import { countLeads } from "./calculations.mjs";
import { writeHistories } from "./history_writer.mjs";
import { normalizeFormulas } from "./formulas.mjs";
import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const configPath = process.argv[2];
const outputDir = process.argv[3];
if (!configPath || !outputDir) {
  throw new Error("Usage: run_country_leads.mjs <config.json> <output-dir>");
}

const config = JSON.parse(await fs.readFile(configPath, "utf8"));
const rate = config.exchangeRateCnyPerUsd;
const SLASH = "/";
const isNumber = (value) => typeof value === "number" && Number.isFinite(value);
const sum = (values) => values.filter(isNumber).reduce((total, value) => total + value, 0);
const ratio = (numerator, denominator) => isNumber(numerator) && isNumber(denominator) && denominator !== 0 ? numerator / denominator : SLASH;
const growth = (current, previous) => {
  const value = ratio(current, previous);
  return isNumber(value) ? value - 1 : SLASH;
};

async function loadWorkbook(filePath) {
  const workbook=await SpreadsheetFile.importXlsx(await FileBlob.load(filePath));
  const key=Object.keys(config.paths).find(k=>config.paths[k]===filePath);
  if(config._formulas[key])normalizeFormulas(workbook,config._formulas[key]);
  return workbook;
}

function firstIndex(rows, predicate) {
  const index = rows.findIndex(predicate);
  if (index < 0) throw new Error("Required data block was not found.");
  return index;
}

function monthBlock(rows, month, name='整理数值') {
  const block=config._histories.countryHistory[name][month];
  if(!block)throw new Error(`缺少历史期间 ${month}`);
  return new Map([...Object.entries(block.rows),['合计',rows[block.total-1]]]);
}
const month=config.reportMonth, periods=config._periods;
const countryDefs = [
  { label: "俄罗斯", lead: "俄罗斯联邦", source: ["Russia"], group: "cis" },
  { label: "阿塞拜疆", lead: "阿塞拜疆", source: ["Azerbaijan"], group: "cis" },
  { label: "亚美尼亚", lead: "亚美尼亚", source: ["Armenia"], group: "cis" },
  { label: "摩尔多瓦", lead: "摩尔多瓦", source: ["Moldova"], group: "cis" },
  { label: "格鲁吉亚", longLabel: "格鲁吉亚（含南奥塞梯、阿布哈兹和格鲁吉亚）", lead: "格鲁吉亚", source: ["Georgia", "South Ossetia", "Abkhazia"], group: "cis" },
  { label: "白俄罗斯", lead: "白俄罗斯", source: [], group: "cis" },
  { label: "哈萨克斯坦", lead: "哈萨克斯坦", source: ["Kazakhstan", "-"], group: "central_asia" },
  { label: "乌兹别克斯坦", lead: "乌兹别克斯坦", source: ["Uzbekistan"], group: "central_asia" },
  { label: "吉尔吉斯斯坦", lead: "吉尔吉斯斯坦", source: ["Kyrgyzstan"], group: "central_asia" },
  { label: "塔吉克斯坦", lead: "塔吉克斯坦", source: ["Tajikistan"], group: "central_asia" },
  { label: "土库曼斯坦", lead: "土库曼斯坦", source: ["Turkmenistan"], group: "central_asia" },
];

const [leadBook, countrySourceBook, monthlyBook, countryHistoryBook, ytdBook] = await Promise.all([
  loadWorkbook(config.paths.leadSource),
  loadWorkbook(config.paths.countrySource),
  loadWorkbook(config.paths.monthlyWorkbook),
  loadWorkbook(config.paths.countryHistory),
  loadWorkbook(config.paths.ytdHistory),
]);

// Lead counts: required regions + required countries + blank media name.
const leadRows = config._books.leadSource.Sheet1;
const leadCounts=countLeads(leadRows,config.leadFilters,countryDefs.map(item=>item.lead));

// Direct country metrics.
const directRows = config._books.countrySource.Sheet0;
const headerIndex=directRows.findIndex(row=>row.includes('Impressions') && row.includes('Clicks'));
if(headerIndex<0)throw new Error('国家数据缺少展示与点击表头');
const headers=directRows[headerIndex];
const column={impressions:headers.indexOf('Impressions'),clicks:headers.indexOf('Clicks'),cost:headers.findIndex(h=>typeof h==='string' && (h==='Cost'||h.startsWith('Cost,')||h.startsWith('Expenditure')))};
if(Object.values(column).some(i=>i<0))throw new Error('国家数据表头无法识别');
const directMap=new Map();
for(const row of directRows.slice(headerIndex+1).filter(r=>r[0])) {
  if(directMap.has(row[0]))throw new Error(`国家数据重复国家 ${row[0]}`);
  const normalized=[...row]; normalized[2]=row[column.impressions];normalized[3]=row[column.clicks];normalized[5]=row[column.cost];directMap.set(row[0],normalized);
}
const directTotal = directMap.get("Total");
if (!directTotal) throw new Error("Direct Total row is missing.");

// Historical comparison metrics and previous YTD totals.
const historySheet = countryHistoryBook.worksheets.getItem("整理数值");
const historyRows = config._books.countryHistory["整理数值"];
const priorYear = monthBlock(historyRows, periods.yearAgo);
const priorMonth = monthBlock(historyRows, periods.previous);
const priorYtdLeads=new Map(),priorYtdSpend=new Map();
for(const country of countryDefs) {
  const rows=periods.ytd.slice(0,-1).map(m=>config._histories.ytdHistory['月度源数据'][m].rows[country.label]);
  for(const row of rows)for(const i of [4,5])if(!isNumber(row[i]) && row[i]!=='/')throw new Error(`YTD历史数值缺失: ${country.label}`);
  priorYtdLeads.set(country.label,sum(rows.map(r=>r[5])));priorYtdSpend.set(country.label,sum(rows.map(r=>r[4])));
}
const records = countryDefs.map((definition) => {
  const sourceRows = definition.source.map((name) => directMap.get(name)).filter(Boolean);
  const hasAds = sourceRows.length > 0;
  const impressions = hasAds ? sum(sourceRows.map((row) => row[2])) : SLASH;
  const clicks = hasAds ? sum(sourceRows.map((row) => row[3])) : SLASH;
  const spendUsd = hasAds ? sum(sourceRows.map((row) => row[5])) : SLASH;
  const spendCny = isNumber(spendUsd) ? spendUsd * rate : SLASH;
  const leads = leadCounts[definition.lead];
  const yearRow = priorYear.get(definition.label);
  const monthRow = priorMonth.get(definition.label);
  const yearCpcUsd = yearRow?.[7] ?? SLASH;
  const monthCpcUsd = monthRow?.[7] ?? SLASH;
  const yearLeads = yearRow?.[5] ?? SLASH;
  const monthLeads = monthRow?.[5] ?? SLASH;
  const yearLeadCost = yearRow?.[4] !== undefined ? ratio(yearRow[4], yearLeads) : SLASH;
  const monthLeadCost = monthRow?.[4] !== undefined ? ratio(monthRow[4], monthLeads) : SLASH;
  const currentLeadCost = ratio(spendCny, leads);
  return {
    ...definition,
    outputLabel: definition.longLabel ?? definition.label,
    impressions,
    clicks,
    spendUsd,
    spendCny,
    leads,
    cpaUsd: ratio(spendUsd, leads),
    cpcUsd: ratio(spendUsd, clicks),
    cpcCny: ratio(spendCny, clicks),
    yearCpcUsd,
    cpcYoy: growth(ratio(spendUsd, clicks), yearCpcUsd),
    monthCpcUsd,
    cpcMom: growth(ratio(spendUsd, clicks), monthCpcUsd),
    yearLeads,
    monthLeads,
    yearLeadCost,
    monthLeadCost,
    currentLeadCost,
    leadYoy: growth(leads, yearLeads),
    leadMom: growth(leads, monthLeads),
    ytdLeads: (isNumber(priorYtdLeads.get(definition.label)) ? priorYtdLeads.get(definition.label) : 0) + leads,
    ytdSpend: (isNumber(priorYtdSpend.get(definition.label)) ? priorYtdSpend.get(definition.label) : 0) + (isNumber(spendCny) ? spendCny : 0),
  };
});

const detailSpendUsd = sum(records.map((row) => row.spendUsd));
const total = {
  label: "合计",
  outputLabel: "合计",
  impressions: directTotal[2],
  clicks: directTotal[3],
  spendUsd: directTotal[5],
  spendCny: directTotal[5] * rate,
  leads: sum(records.map((row) => row.leads)),
};
total.cpaUsd = ratio(total.spendUsd, total.leads);
total.cpcUsd = ratio(total.spendUsd, total.clicks);
total.cpcCny = ratio(total.spendCny, total.clicks);
total.yearCpcUsd = priorYear.get("合计")[7];
total.cpcYoy = growth(total.cpcUsd, total.yearCpcUsd);
total.monthCpcUsd = priorMonth.get("合计")[7];
total.cpcMom = growth(total.cpcUsd, total.monthCpcUsd);
total.yearLeads = priorYear.get("合计")[5];
total.monthLeads = priorMonth.get("合计")[5];
total.yearLeadCost = ratio(priorYear.get("合计")[4], total.yearLeads);
total.monthLeadCost = ratio(priorMonth.get("合计")[4], total.monthLeads);
total.currentLeadCost = ratio(total.spendCny, total.leads);
total.leadYoy = growth(total.leads, total.yearLeads);
total.leadMom = growth(total.leads, total.monthLeads);
total.ytdLeads = sum(records.map((row) => row.ytdLeads));
total.ytdSpend = sum(records.map((row) => row.ytdSpend));

function countryRow(record, label = record.outputLabel) {
  return [
    label, record.impressions, record.clicks, record.spendUsd, record.spendCny,
    record.leads, record.cpaUsd, record.cpcUsd, record.cpcCny,
    record.yearCpcUsd, record.cpcYoy, record.monthCpcUsd, record.cpcMom,
  ];
}

function groupRecord(group) {
  const rows = records.filter((row) => row.group === group);
  const yearSpend = sum(rows.map((row) => priorYear.get(row.label)?.[4]));
  const monthSpend = sum(rows.map((row) => priorMonth.get(row.label)?.[4]));
  const result = {
    impressions: sum(rows.map((row) => row.impressions)),
    clicks: sum(rows.map((row) => row.clicks)),
    spendUsd: sum(rows.map((row) => row.spendUsd)),
    spendCny: sum(rows.map((row) => row.spendCny)),
    leads: sum(rows.map((row) => row.leads)),
    ytdSpend: sum(rows.map((row) => row.ytdSpend)),
    ytdLeads: sum(rows.map((row) => row.ytdLeads)),
    yearLeads: sum(rows.map((row) => row.yearLeads)),
    monthLeads: sum(rows.map((row) => row.monthLeads)),
  };
  result.currentLeadCost = ratio(result.spendCny, result.leads);
  result.yearLeadCost = ratio(yearSpend, result.yearLeads);
  result.monthLeadCost = ratio(monthSpend, result.monthLeads);
  result.leadYoy = growth(result.leads, result.yearLeads);
  result.leadMom = growth(result.leads, result.monthLeads);
  return result;
}

const cis = groupRecord("cis");
const centralAsia = groupRecord("central_asia");

// 1) Monthly workbook country table.
const monthlySheet = monthlyBook.worksheets.getItem("Sheet1");
const countryHeaders = ["国家", "展示合计", "点击合计", "消耗合计", "消耗合计人民币", "线索", "CPA美元", "CPC美元", "CPC人民币", `${periods.yearAgo} CPC美元`, "点击成本同比", `${periods.previous} CPC美元`, "点击成本环比"];
monthlySheet.getRange("A21:M34").values = [
  [`${month} 国家线索数据`, ...Array(12).fill(null)],
  countryHeaders,
  ...records.map((row) => countryRow(row)),
  [null, ...countryRow(total).slice(1)],
];

function ytdDetailRow(record, groupLabel = null) {
  return [
    groupLabel, record.label, record.impressions, record.clicks, record.spendCny,
    record.ytdSpend, record.leads, record.ytdLeads, record.leadMom, record.leadYoy,
    record.currentLeadCost, isNumber(record.spendCny) ? record.spendCny / total.spendCny : SLASH,
    record.yearLeads, record.monthLeads, record.yearLeadCost,
    growth(record.currentLeadCost, record.yearLeadCost), record.monthLeadCost,
    growth(record.currentLeadCost, record.monthLeadCost),
  ];
}

function ytdGroupRow(record, label) {
  return [
    label, null, record.impressions, record.clicks, record.spendCny, record.ytdSpend,
    record.leads, record.ytdLeads, record.leadMom, record.leadYoy, record.currentLeadCost,
    record.spendCny / total.spendCny, record.yearLeads, record.monthLeads,
    record.yearLeadCost, growth(record.currentLeadCost, record.yearLeadCost),
    record.monthLeadCost, growth(record.currentLeadCost, record.monthLeadCost),
  ];
}

const monthlyYtdRows = [
  ["国家维度ytd线索数据", ...Array(17).fill(null)],
  [month, ...Array(17).fill(null)],
  ["区域", "市场", "展示次数", "点击次数", "本周期消耗", "YTD消耗", "本月线索", "YTD线索", "线索环比", "线索同比", "线索成本", "消耗占比（yandex）", `${periods.yearAgo} 同比线索`, `${periods.previous} 线索`, `${periods.yearAgo} 线索成本`, "线索成本同比", `${periods.previous} 线索成本`, "环比增幅"],
  ...records.slice(0, 6).map((row, index) => ytdDetailRow(row, index === 0 ? "独联体大区" : null)),
  ytdGroupRow(cis, "独联体合计"),
  ...records.slice(6).map((row, index) => ytdDetailRow(row, index === 0 ? "中亚大区\n\n（与谷歌共同投放）" : null)),
  [month, null, total.impressions, total.clicks, total.spendCny, total.ytdSpend, total.leads, total.ytdLeads, total.leadMom, total.leadYoy, total.currentLeadCost, 1, total.yearLeads, total.monthLeads, total.yearLeadCost, growth(total.currentLeadCost, total.yearLeadCost), total.monthLeadCost, growth(total.currentLeadCost, total.monthLeadCost)],
  ["yandex\n\n合计（同比）", periods.yearAgo, priorYear.get("合计")[1], priorYear.get("合计")[2], priorYear.get("合计")[4], null, priorYear.get("合计")[5], null, null, null, total.yearLeadCost, null, null, null, null, null, null, null],
  ["yandex\n\n合计（环比）", periods.previous, priorMonth.get("合计")[1], priorMonth.get("合计")[2], priorMonth.get("合计")[4], null, priorMonth.get("合计")[5], null, null, null, total.monthLeadCost, null, null, null, null, null, null, null],
];
monthlySheet.getRange("A37:R54").values = monthlyYtdRows;
monthlySheet.getRange('A39:R39').format={wrapText:true,rowHeight:54};
monthlySheet.getRange('A22:M22').format={wrapText:true,rowHeight:44};

// 2) Current vs prior-year regional table.
const leftRows = records.map((row) => [row.outputLabel, row.impressions, row.clicks, row.spendUsd, row.spendCny, row.leads]);
const priorRows = records.map((row) => {
  const prior = priorYear.get(row.label);
  return [row.outputLabel, prior[1], prior[2], prior[3], prior[4], prior[5]];
});
monthlySheet.getRange("A151:M164").values = [
  [month, null, null, null, null, null, null, periods.yearAgo, null, null, null, null, null],
  ["国家", "展示合计", "点击合计", "消耗合计", "消耗合计人民币", "线索", null, "国家", "展示合计", "点击合计", "消耗合计美金", "消耗合计人民币", "线索"],
  ...leftRows.map((row, index) => [...row, null, ...priorRows[index]]),
  ["合计", total.impressions, total.clicks, total.spendUsd, total.spendCny, total.leads, null, null, priorYear.get("合计")[1], priorYear.get("合计")[2], priorYear.get("合计")[3], priorYear.get("合计")[4], priorYear.get("合计")[5]],
];
monthlySheet.getRange("A166:M169").values = [
  [`${periods.yearAgo} 客车`, null, null, null, null, null, null, `${periods.yearAgo} 客车`, null, null, null, null, null],
  ["中亚", centralAsia.impressions, centralAsia.clicks, centralAsia.spendCny, centralAsia.leads, null, null, "中亚", sum(records.slice(6).map((r) => priorYear.get(r.label)[1])), sum(records.slice(6).map((r) => priorYear.get(r.label)[2])), sum(records.slice(6).map((r) => priorYear.get(r.label)[4])), sum(records.slice(6).map((r) => priorYear.get(r.label)[5])), null],
  ["独联体", cis.impressions, cis.clicks, cis.spendCny, cis.leads, null, null, "独联体", sum(records.slice(0, 6).map((r) => priorYear.get(r.label)[1])), sum(records.slice(0, 6).map((r) => priorYear.get(r.label)[2])), sum(records.slice(0, 6).map((r) => priorYear.get(r.label)[4])), sum(records.slice(0, 6).map((r) => priorYear.get(r.label)[5])), null],
  ["合计", total.impressions, total.clicks, total.spendCny, total.leads, null, null, "合计", priorYear.get("合计")[1], priorYear.get("合计")[2], priorYear.get("合计")[4], priorYear.get("合计")[5], null],
];

// Dynamic, idempotent history update; only in-memory candidate workbooks.
if(total.leads!==config.leadComparisonTotals.current)throw new Error(`线索筛选 ${total.leads} 与核对总数 ${config.leadComparisonTotals.current} 不一致`);
for(const [value,expected] of [[total.impressions,directTotal[2]],[total.clicks,directTotal[3]],[total.spendUsd,directTotal[5]]])if(Math.abs(value-expected)>0.01)throw new Error('国家数据与 Direct 总计不一致');
writeHistories({config,countryHistoryBook,ytdBook,records,total,countryHeaders,countryRow,monthlyYtdRows});
await fs.mkdir(outputDir, { recursive: true });
const outputPaths = {
  monthly: path.join(outputDir, `yutong_${month}_monthly_country_leads.xlsx`),
  countryHistory: path.join(outputDir, `yutong_country_history_through_${month}.xlsx`),
  ytdHistory: path.join(outputDir, `yutong_ytd_history_through_${month}.xlsx`),
};
for (const [workbook, outputPath] of [[monthlyBook, outputPaths.monthly], [countryHistoryBook, outputPaths.countryHistory], [ytdBook, outputPaths.ytdHistory]]) {
  workbook.recalculate();
  const blob = await SpreadsheetFile.exportXlsx(workbook);
  await blob.save(outputPath);
}

const validation = {
  client: config.client,
  reportMonth: config.reportMonth,
  leadTotal: total.leads,
  leadCounts,
  unidentifiedAssignedTo: "哈萨克斯坦",
  conversionRates: {
    哈萨克斯坦: leadCounts.哈萨克斯坦 / directMap.get("Kazakhstan")[3],
    乌兹别克斯坦: leadCounts.乌兹别克斯坦 / directMap.get("Uzbekistan")[3],
  },
  directReconciliation: {
    impressionsDifference: sum(records.map((row) => row.impressions)) - directTotal[2],
    clicksDifference: sum(records.map((row) => row.clicks)) - directTotal[3],
    spendUsdDifference: detailSpendUsd - directTotal[5],
  },
  outputPaths,
};
await fs.writeFile(path.join(outputDir, "validation.json"), `${JSON.stringify(validation, null, 2)}\n`, "utf8");
console.log(JSON.stringify(validation, null, 2));
