// 模块：sem_automation/reporting/renderers/standard/metrika_monthly_workbook.mjs；内部模块由统一入口调用。
// VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化'
// 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' reports standard --client '.\config\clients\lingyu.json' --month 2026-07 --source existing --data-dir '.\outputs\_archive\lingyu\2026-07'
// 该示例复用本地数据；详见 docs/月报操作说明.md。
import fs from 'node:fs/promises';
import path from 'node:path';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';

const args = {};
for (let i = 2; i < process.argv.length; i += 2) args[process.argv[i].replace(/^--/, '')] = process.argv[i + 1];
if (!args.input || !args['out-dir']) throw new Error('需要 --input 和 --out-dir');
const data = JSON.parse(await fs.readFile(args.input, 'utf8'));
if (data.schema !== 'metrika_monthly_v1') throw new Error('不支持的 Metrika 数据格式');
const meta = data.meta, reports = data.reports;
const out = path.resolve(args['out-dir']);
const internal = path.join(out, '_internal', 'metrika');
await fs.mkdir(path.join(internal, 'previews'), {recursive: true});
const wb = Workbook.create();
const names = ['网站汇总', '每日流量', '设备', '年龄', '流量来源', '新老访客', '新老访客每日', '目标汇总', '目标每日', '导出口径'];
for (const name of names) wb.worksheets.add(name);
const col = n => {let s = ''; for (; n; n = Math.floor((n - 1) / 26)) s = String.fromCharCode(65 + (n - 1) % 26) + s; return s;};
const literal = x => typeof x === 'string' && x.startsWith('=') ? `'${x}` : x ?? '';
const ranges = [];
function table(name, headers, rows, widths = {}) {
  const s = wb.worksheets.getItem(name), end = col(headers.length), bottom = Math.max(6, rows.length + 5);
  s.getRange(`A1:${end}${bottom}`).format = {
    fill: '#FFFFFF', font: {name: 'Arial', size: 10, color: '#000000'},
    columnWidth: 20, rowHeight: 25, verticalAlignment: 'center',
  };
  for (const [r, label] of [[1, `Client: ${meta.client_name} | Counter: ${meta.counter_id} | ${meta.counter.site}`],
    [2, 'Report: Yandex Metrika API'], [3, `Period: ${meta.date_from} - ${meta.date_to} | Time zone: ${meta.counter.time_zone_name}`]]) {
    s.getRange(`A${r}:${end}${r}`).merge(); s.getRange(`A${r}`).values = [[label]];
  }
  s.getRange(`A5:${end}5`).values = [headers];
  s.getRange(`A5:${end}5`).format = {font: {bold: true}, rowHeight: 36, wrapText: true};
  if (rows.length) s.getRange(`A6:${end}${bottom}`).values = rows.map(r => r.map(literal));
  for (const [index, width] of Object.entries(widths)) s.getRange(`${col(Number(index))}1:${col(Number(index))}${bottom}`).format.columnWidth = width;
  s.freezePanes.freezeRows(5);
  s.showGridLines = true;
  ranges.push({sheetName: name, range: `A1:${end}${Math.min(bottom, 11)}`});
  return s;
}
const metrics = reports.summary.metrics;
const labels = {
  'ym:s:visits': 'Sessions', 'ym:s:users': 'Users', 'ym:s:pageviews': 'Pageviews (session metric)',
  'ym:s:bounceRate': 'Bounce rate, %', 'ym:s:pageDepth': 'Page depth',
  'ym:s:avgVisitDurationSeconds': 'Avg. time on site, seconds', 'ym:s:newUsers': 'New users',
};
const current = reports.summary.totals, previous = reports.previous_summary.totals;
const summaryRows = metrics.map(m => [labels[m] ?? m, current[m], previous[m], null,
    `${reports.previous_summary.date_from} - ${reports.previous_summary.date_to}`]);
if (reports.pageviews_hits) summaryRows.push(['Pageviews (hit metric / card)', reports.pageviews_hits.totals['ym:pv:pageviews'], reports.previous_pageviews_hits?.totals['ym:pv:pageviews'] ?? '', '', reports.previous_pageviews_hits ? `${reports.previous_pageviews_hits.date_from} - ${reports.previous_pageviews_hits.date_to}` : '']);
const summary = table('网站汇总', ['Metric', 'Current period', 'Previous period', 'Change, %', 'Previous period dates'],
  summaryRows, {1: 40, 5: 32});
if (reports.previous_pageviews_hits) summary.getRange(`D${summaryRows.length + 5}`).formulas = [[`=IF(C${summaryRows.length + 5}=0,"-",B${summaryRows.length + 5}/C${summaryRows.length + 5}-1)`]];
if (reports.previous_pageviews_hits) summary.getRange(`D${summaryRows.length + 5}`).setNumberFormat('0.00%');
summary.getRange(`B6:C${5 + metrics.length}`).setNumberFormat('0.00');
summary.getRange(`D6:D${5 + metrics.length}`).setNumberFormat('0.00%');
for (let i = 0; i < metrics.length; i++) {
  const r = i + 6;
  summary.getRange(`D${r}`).formulas = [[`=IF(C${r}=0,"-",B${r}/C${r}-1)`]];
  if (!['ym:s:bounceRate', 'ym:s:pageDepth', 'ym:s:avgVisitDurationSeconds'].includes(metrics[i])) summary.getRange(`B${r}:C${r}`).setNumberFormat('0');
}

const dates = [];
for (let day = new Date(meta.date_from + 'T00:00:00Z'); day <= new Date(meta.date_to + 'T00:00:00Z'); day.setUTCDate(day.getUTCDate() + 1)) dates.push(day.toISOString().slice(0, 10));
const dailyMap = new Map(reports.daily.rows.map(r => [r['ym:s:date'], r]));
const ratioMetrics = new Set(['ym:s:bounceRate', 'ym:s:pageDepth', 'ym:s:avgVisitDurationSeconds']);
const daily = table('每日流量', ['Date', ...metrics.map(m => labels[m] ?? m)],
  dates.map(date => [date, ...metrics.map(m => dailyMap.get(date)?.[m] ?? (ratioMetrics.has(m) ? '-' : 0))]), {1: 18, 4: 28, 7: 30});
daily.getRange(`E6:G${dates.length + 5}`).setNumberFormat('0.00');

for (const [key, name] of [['devices', '设备'], ['ages', '年龄'], ['sources', '流量来源']]) {
  const report = reports[key], dim = report.dimensions[0];
  const rows = report.rows.map(r => [r[dim] ?? '(Undefined)', r[dim + ':id'] ?? '', r['ym:s:visits'], null, ...(key === 'ages' ? [null] : [])]);
  const s = table(name, ['Category', 'Category ID', 'Sessions', 'Share of listed sessions', ...(key === 'ages' ? ['Share of known ages (chart)'] : [])], rows, {1: 40, 4: 30, ...(key === 'ages' ? {5: 32} : {})});
  s.getRange(`B6:B${Math.max(6, 5 + rows.length)}`).setNumberFormat('@');
  const end = rows.length + 5;
  for (let i = 0; i < rows.length; i++) s.getRange(`D${i + 6}`).formulas = [[`=IF(SUM($C$6:$C$${end})=0,"-",C${i + 6}/SUM($C$6:$C$${end}))`]];
  if (rows.length) s.getRange(`D6:D${end}`).setNumberFormat('0.00%');
  if (key === 'ages' && rows.length) {
    for (let i = 0; i < rows.length; i++) {
      const r = i + 6;
      s.getRange(`E${r}`).formulas = [[`=IF(B${r}="","-",IF(SUMIF($B$6:$B$${end},"<>",$C$6:$C$${end})=0,"-",C${r}/SUMIF($B$6:$B$${end},"<>",$C$6:$C$${end})))`]];
    }
    s.getRange(`E6:E${end}`).setNumberFormat('0.00%');
  }
}

table('新老访客', ['Visitor type', 'Type ID', 'Users (unique within group)'], reports.new_returning.rows.map(r =>
  [r['ym:s:isNewUser'], r['ym:s:isNewUser:id'], r['ym:s:users']]), {1: 40, 3: 40});
table('新老访客每日', ['Date', 'Visitor type', 'Type ID', 'Users (daily unique)'], reports.new_returning_daily.rows.map(r =>
  [r['ym:s:date'], r['ym:s:isNewUser'], r['ym:s:isNewUser:id'], r['ym:s:users']]), {1: 18, 2: 30, 4: 30});

const goalSummary = [], goalDaily = [];
for (const goal of data.goals) {
  const report = reports[`goal_${goal.id}`], keys = report.metrics.slice(0, 3);
  goalSummary.push([goal.name, goal.id, ...keys.map(k => report.totals[k])]);
  const dateMap = new Map(report.rows.map(r => [r['ym:s:date'], r]));
  for (const date of dates) goalDaily.push([date, goal.name, goal.id,
    ...keys.map((k, i) => dateMap.get(date)?.[k] ?? (i === 0 ? '-' : 0))]);
}
const gs = table('目标汇总', ['Goal', 'Goal ID', 'Conversion rate, %', 'Converted sessions', 'Conversions (reaches)'], goalSummary,
  {1: 38, 3: 26, 4: 26, 5: 28});
gs.getRange(`B6:B${Math.max(6, 5 + goalSummary.length)}`).setNumberFormat('@');
gs.getRange(`C6:C${Math.max(6, 5 + goalSummary.length)}`).setNumberFormat('0.00');
const gd = table('目标每日', ['Date', 'Goal', 'Goal ID', 'Conversion rate, %', 'Converted sessions', 'Conversions (reaches)'], goalDaily,
  {1: 18, 2: 35, 4: 26, 5: 26, 6: 28});
gd.getRange(`C6:C${Math.max(6, 5 + goalDaily.length)}`).setNumberFormat('@');
gd.getRange(`D6:D${Math.max(6, 5 + goalDaily.length)}`).setNumberFormat('0.00');

const notes = [
  ['Counter ID', String(meta.counter_id)], ['Site', meta.counter.site], ['Time zone', meta.counter.time_zone_name],
  ['Attribution (traffic source)', meta.attribution], ['Extra filters', meta.filters || '(none: all site traffic)'],
  ['Accuracy requested', 'full'], ['Fetched at (UTC)', meta.fetched_at],
  ...meta.notes.map((n, i) => [`Note ${i + 1}`, n]),
  ...Object.entries(reports).filter(([, r]) => r.pages.some(p => p.contains_sensitive_data)).map(([key]) => ['Limited disclosure', key]),
  ['Raw response files', '_internal/metrika/*.page*.json'],
  ['API definitions', 'https://yandex.com/dev/metrika/en/stat/attrandmetr/dim_all'],
];
const info = table('导出口径', ['Setting', 'Value'], notes, {1: 34, 2: 120});
info.getRange(`A6:B${notes.length + 5}`).format.rowHeight = 36;
info.getRange(`B6:B${notes.length + 5}`).format.wrapText = true;
const inspect = await wb.inspect({kind: 'table', range: '网站汇总!A5:E12', include: 'values,formulas', tableMaxRows: 8, tableMaxCols: 5});
await fs.writeFile(path.join(internal, 'xlsx-inspection.ndjson'), inspect.ndjson);
const errors = await wb.inspect({kind: 'match', searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A', options: {useRegex: true, maxResults: 30}});
await fs.writeFile(path.join(internal, 'formula-check.ndjson'), errors.ndjson);
for (let i = 0; i < ranges.length; i++) {
  const blob = await wb.render({...ranges[i], scale: 1, format: 'png'});
  await fs.writeFile(path.join(internal, 'previews', `sheet-${i + 1}.png`), new Uint8Array(await blob.arrayBuffer()));
}
const xlsx = await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(path.join(out, 'metrika_api_review.xlsx'));
console.log(`XLSX: ${path.join(out, 'metrika_api_review.xlsx')}`);
