// 模块：sem_automation/reporting/renderers/standard/direct_monthly_workbook.mjs；内部模块由统一入口调用。
// VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化 - 副本'
// 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' reports standard --client '.\config\clients\lingyu.json' --month 2026-07 --source existing --data-dir '.\outputs\_archive\lingyu\2026-07'
// 该示例复用本地数据；详见 docs/月报操作说明.md。
import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const args = {};
for (let i = 2; i < process.argv.length; i += 2) args[process.argv[i].replace(/^--/, '')] = process.argv[i + 1];
if (!args.input || !args['out-dir']) throw new Error('需要 --input 和 --out-dir');
const data = JSON.parse(await fs.readFile(args.input, 'utf8'));
if (data.schema_version !== 1) throw new Error('不支持的通用报告 JSON 版本');
const meta = data.meta;
const outputDir = path.resolve(args['out-dir']);
await fs.mkdir(path.join(outputDir, '_internal', 'previews'), { recursive: true });
const wb = Workbook.create();
for (const name of ['账户汇总', '广告系列', '搜索词', '对账', '导出口径']) wb.worksheets.add(name);
for (const [key, name] of [['daily', '每日投放'], ['previous_account', '上期汇总']]) if (data.raw[key]) wb.worksheets.add(name);
const col = (n) => { let s = ''; for (; n; n = Math.floor((n - 1) / 26)) s = String.fromCharCode(65 + (n - 1) % 26) + s; return s; };
const field = (f) => meta.goal_id && ['Conversions', 'ConversionRate', 'CostPerConversion'].includes(f) ? `${f}_${meta.goal_id}_${meta.attribution_model}` : f;
// Treat externally supplied queries/names as text even if they start with '='.
const literal = (v) => typeof v === 'string' && v.startsWith('=') ? `'${v}` : v ?? '';
const value = (row, key) => literal(row?.[field(key)] ?? '-');
const period = `${meta.date_from} - ${meta.date_to}`;
const money = meta.currency === 'USD' ? '$' : meta.currency;
const previews = [];

function sheet(name, headers, rows, {widths = {}, integerCols = [], textCols = []} = {}) {
  const s = wb.worksheets.getItem(name);
  const end = col(headers.length);
  const rowEnd = Math.max(6, 5 + rows.length);
  s.getRange(`A1:${end}${rowEnd}`).format = {
    fill: '#FFFFFF', font: { name: 'Arial', size: 10, color: '#000000' },
    rowHeight: 28, columnWidth: 16, verticalAlignment: 'center',
  };
  for (const [n, text] of [[1, `Client: ${meta.client_name} (${meta.client_login})`],
                         [2, 'Report: Direct API / Report wizard'], [3, `Period: ${period}`]]) {
    s.getRange(`A${n}:${end}${n}`).merge();
    s.getRange(`A${n}`).values = [[text]];
  }
  s.getRange(`A5:${end}5`).values = [headers];
  s.getRange(`A5:${end}5`).format = {font: {bold: true}, wrapText: true, rowHeight: 42};
  if (rows.length) s.getRange(`A6:${end}${5 + rows.length}`).values = rows;
  s.getRange(`A6:${end}${rowEnd}`).setNumberFormat('0.00');
  for (const index of integerCols) s.getRange(`${col(index)}6:${col(index)}${rowEnd}`).setNumberFormat('0');
  for (const index of textCols) s.getRange(`${col(index)}6:${col(index)}${rowEnd}`).setNumberFormat('@');
  for (const [index, width] of Object.entries(widths)) s.getRange(`${col(Number(index))}1:${col(Number(index))}${rowEnd}`).format.columnWidth = width;
  s.freezePanes.freezeRows(5);
  s.showGridLines = true;
  previews.push({sheetName: name, range: `A1:${end}${Math.min(rowEnd, 10)}`});
  return s;
}

const metricKeys = ['Impressions', 'Clicks', 'Ctr', 'Cost', 'AvgCpc', 'AvgPageviews', 'ConversionRate', 'CostPerConversion', 'Conversions'];
const metricHeaders = ['Impressions', 'Clicks', 'CTR, %', `Expenditure, ${money}`, `CPC, ${money}`, 'Depth (pages)', 'CR, %', `CPA, ${money}`, 'Conversions'];
const accountRow = data.raw.account[0];
const account = sheet('账户汇总', ['Period', `Avg. expenditure per day, ${money}`, ...metricHeaders],
  accountRow ? [[period, null, ...metricKeys.map(k => value(accountRow, k))]] : [['No data', '', ...metricKeys.map(() => '')]],
  {widths: {1: 32, 2: 24}, integerCols: [3, 4]});
if (accountRow) account.getRange('B6').formulas = [["=F6/'导出口径'!B9"]];

const campaign = sheet('广告系列', ['Campaign', 'Campaign No.', 'Period', ...metricHeaders.slice(0, 5),
  `Avg. expenditure per day, ${money}`, ...metricHeaders.slice(5)],
  data.raw.campaign.map(r => [value(r, 'CampaignName'), value(r, 'CampaignId'), period,
    ...metricKeys.slice(0, 5).map(k => value(r, k)), null, ...metricKeys.slice(5).map(k => value(r, k))]),
  {widths: {1: 27, 2: 18, 3: 32, 9: 24}, integerCols: [4, 5], textCols: [2]});
for (let i = 0; i < data.raw.campaign.length; i++) campaign.getRange(`I${6 + i}`).formulas = [[`=G${6 + i}/'导出口径'!B9`]];

const queryHeaders = ['Search query', 'Campaign name', 'Campaign No.', 'Group name', 'Group No.',
  'Type of impressions criteria', 'Match type', 'Keyword', 'Request category (API legacy)',
  'Impressions', 'Clicks', 'CTR, %', `Expenditure, ${money}`, `CPC, ${money}`,
  'Conversions', 'CR, %', `CPA, ${money}`];
const names = {
  CriterionType: {KEYWORD: 'Phrase', AUTOTARGETING: 'Autotargeting'},
  MatchType: {KEYWORD: 'Keyword', SYNONYM: 'Semantic', RELATED_KEYWORD: 'Related keyword', NONE: '-'},
  TargetingCategory: {EXACT: 'Targeted queries', ALTERNATIVE: 'Alternative queries', COMPETITOR: 'Competitor queries', BROADER: 'Broad queries', ACCESSORY: 'Related queries'},
};
const display = (r, key) => literal(names[key]?.[r[key]] ?? r[key] ?? '-');
const queryRows = data.raw.search_queries.map(r => [value(r, 'Query'), value(r, 'CampaignName'), value(r, 'CampaignId'),
  value(r, 'AdGroupName'), value(r, 'AdGroupId'), display(r, 'CriterionType'), display(r, 'MatchType'),
  value(r, 'Criterion'), display(r, 'TargetingCategory'), ...['Impressions', 'Clicks', 'Ctr', 'Cost', 'AvgCpc',
  'Conversions', 'ConversionRate', 'CostPerConversion'].map(k => value(r, k))]);
const query = sheet('搜索词', queryHeaders, [['Detail total', ...Array(16).fill('')], ...queryRows],
  {widths: {1: 62, 2: 26, 3: 18, 4: 40, 5: 18, 6: 22, 7: 19, 8: 68, 9: 26}, integerCols: [10, 11], textCols: [3, 5]});
const queryEnd = 6 + queryRows.length;
for (const c of ['J', 'K', 'M', 'O']) query.getRange(`${c}6`).formulas = [[queryRows.length ? `=SUM(${c}7:${c}${queryEnd})` : '=0']];
for (const [c, f] of Object.entries({L: '=IF(J6=0,"-",K6/J6*100)', N: '=IF(K6=0,"-",M6/K6)', P: '=IF(K6=0,"-",O6/K6*100)', Q: '=IF(O6=0,"-",M6/O6)'})) query.getRange(`${c}6`).formulas = [[f]];
query.getRange('A6:Q6').format.font.bold = true;
if (queryRows.length) {
  query.getRange(`A7:I${queryEnd}`).format.wrapText = true;
  // Long original queries/keywords remain fully readable, without widening the whole workbook.
  query.getRange(`A7:Q${queryEnd}`).format.rowHeight = 66;
  for (let i = 0; i < queryRows.length; i++) {
    const chars = v => [...String(v ?? '')].reduce((n, c) => n + (c.charCodeAt(0) > 0x2e7f ? 2 : 1), 0);
    const lines = Math.max(Math.ceil(chars(queryRows[i][0]) / 60), Math.ceil(chars(queryRows[i][7]) / 65));
    if (lines > 4) query.getRange(`A${i + 7}:Q${i + 7}`).format.rowHeight = Math.min(409, lines * 15 + 8);
  }
}

const checkRows = data.checks.map(c => [c.report, c.metric, c.account, c.detail, c.difference, c.status]);
sheet('对账', ['Report', 'Metric', 'Account', 'Detail total', 'Difference', 'Status'], checkRows,
  {widths: {1: 25, 2: 20, 6: 36}});

// Stable row B9 holds the inclusive calendar-day denominator used by visible formulas.
const notes = [
  ['Client', meta.client_name], ['Login', meta.client_login], ['Currency', meta.currency],
  ['Calendar days', meta.days], ['Attribution', meta.attribution_model],
  ['Goals', meta.conversion_label ?? meta.conversion_scope], ['IncludeVAT', meta.include_vat],
  ['IncludeDiscount', meta.include_discount], ['Fetched at (UTC)', meta.fetched_at],
  ...meta.notes.map((n, i) => [`Note ${i + 1}`, n]),
  ['API fields', 'https://yandex.com/dev/direct/doc/en/fields-list'],
  ['API definitions', 'https://yandex.com/dev/direct/doc/en/report-format'],
  ['Raw evidence', '_internal/*.tsv and *.request.json'],
  ['Tolerance: count absolute', meta.tolerance?.count_absolute ?? 2],
  ['Tolerance: cost absolute', meta.tolerance?.cost_absolute ?? 1],
  ['Tolerance: relative', meta.tolerance?.relative ?? 0.005],
  ['Tolerance rule', 'Absolute AND relative limits must both pass; within tolerance is WARN. Different scopes are INFO, not a tolerance pass.'],
];
const info = sheet('导出口径', ['Setting', 'Value'], notes, {widths: {1: 28, 2: 120}, textCols: [1, 2]});
for (const [key, name] of [['daily', '每日投放'], ['previous_account', '上期汇总']]) {
  if (!data.raw[key]) continue;
  const rows = data.raw[key];
  const fields = key === 'daily' ? ['Date', ...metricKeys] : metricKeys;
  const s = sheet(name, fields, rows.map(r => fields.map(k => value(r, k))));
  if (key === 'previous_account') s.getRange('A3').values = [[`Period: ${meta.comparison_period.date_from} - ${meta.comparison_period.date_to}`]];
}
info.getRange(`B6:B${5 + notes.length}`).format.wrapText = true;
info.getRange(`A6:B${5 + notes.length}`).format.rowHeight = 32;
info.getRange('B9').setNumberFormat('0');

const inspected = await wb.inspect({kind: 'table', range: '账户汇总!A5:K6', include: 'values,formulas', tableMaxRows: 2, tableMaxCols: 11});
await fs.writeFile(path.join(outputDir, '_internal', 'xlsx-inspection.ndjson'), inspected.ndjson);
const errors = await wb.inspect({kind: 'match', searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A', options: {useRegex: true, maxResults: 30}, summary: 'formula errors'});
await fs.writeFile(path.join(outputDir, '_internal', 'formula-check.ndjson'), errors.ndjson);
for (let i = 0; i < previews.length; i++) {
  const preview = await wb.render({...previews[i], scale: 1, format: 'png'});
  await fs.writeFile(path.join(outputDir, '_internal', 'previews', `sheet-${i + 1}.png`), new Uint8Array(await preview.arrayBuffer()));
}
const file = await SpreadsheetFile.exportXlsx(wb);
await file.save(path.join(outputDir, 'direct_api_review.xlsx'));
console.log(`XLSX: ${path.join(outputDir, 'direct_api_review.xlsx')}`);
