// 模块：sem_automation/reporting/renderers/standard/report_workbook_data.mjs；内部模块由统一入口调用。
// VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化 - 副本'
// 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' reports standard --client '.\config\clients\lingyu.json' --month 2026-07 --source existing --data-dir '.\outputs\_archive\lingyu\2026-07'
// 该示例复用本地数据；详见 docs/月报操作说明.md。
export const col = n => { let s = ''; for (; n; n = Math.floor((n - 1) / 26)) s = String.fromCharCode(65 + (n - 1) % 26) + s; return s; };
export const literal = x => typeof x === 'string' && x.startsWith('=') ? `'${x}` : x ?? '';
export const quoteSheet = name => `'${name.replaceAll("'", "''")}'`;
export const directValue = (meta, row, field) => row?.[meta.goal_id && ['ConversionRate','CostPerConversion','Conversions'].includes(field) ? `${field}_${meta.goal_id}_${meta.attribution_model}` : field] ?? null;
export function calendarDates(start, end) {
  const dates = [];
  for (let d = new Date(start + 'T00:00:00Z'); d <= new Date(end + 'T00:00:00Z'); d.setUTCDate(d.getUTCDate() + 1)) dates.push(d.toISOString().slice(0, 10));
  return dates;
}
export function writeSource(wb, name, fields, rows) {
  const s = wb.worksheets.add(name), end = col(fields.length), last = Math.max(2, rows.length + 1);
  s.getRange(`A1:${end}${last}`).format = {fill:'#FFFFFF', font:{name:'Arial',size:10,color:'#253047'}, columnWidth:20,rowHeight:24};
  s.getRange(`A1:${end}1`).values = [fields];
  s.getRange(`A1:${end}1`).format = {font:{bold:true},wrapText:true,rowHeight:42};
  if (rows.length) s.getRange(`A2:${end}${rows.length + 1}`).values = rows.map(r => r.map(literal));
  s.freezePanes.freezeRows(1);
  return {sheet:s,name,fields,rows,cell:(field,row) => `${quoteSheet(name)}!${col(fields.indexOf(field)+1)}${row}`,
    range: field => `${quoteSheet(name)}!$${col(fields.indexOf(field)+1)}$2:$${col(fields.indexOf(field)+1)}$${Math.max(2,rows.length+1)}`};
}
export function buildSources(wb, bundle) {
  const {direct:d,metrika:m,period:p}=bundle, reports=m.reports;
  const dates=calendarDates(p.start,p.end);
  const base=['Impressions','Clicks','Ctr','Cost','AvgCpc','AvgPageviews','ConversionRate','CostPerConversion','Conversions'];
  const dvalue=(row,f) => directValue(d.meta,row,f);
  const sources={};
  const old=d.meta.comparison_period;
  const oldDays=calendarDates(old.date_from,old.date_to).length;
  sources.direct=writeSource(wb,'数据_Direct汇总',['Period',...base,'Days','AvgDailyCost'],[
    [`${p.start} - ${p.end}`,...base.map(f=>dvalue(d.raw.account[0],f)),p.days,null],
    [`${old.date_from} - ${old.date_to}`,...base.map(f=>dvalue(d.raw.previous_account[0],f)),oldDays,null],
  ]);
  for (const r of [2,3]) sources.direct.sheet.getRange(`L${r}`).formulas=[[`=IF(K${r}=0,"-",E${r}/K${r})`]];
  sources.campaign=writeSource(wb,'数据_广告系列',['CampaignName','CampaignId',...base,'AvgDailyCost'],d.raw.campaign.map(r=>[r.CampaignName,r.CampaignId,...base.map(f=>dvalue(r,f)),null]));
  for(let i=0;i<d.raw.campaign.length;i++) sources.campaign.sheet.getRange(`L${i+2}`).formulas=[[`=F${i+2}/${sources.direct.cell('Days',2)}`]];
  const dd=new Map(d.raw.daily.map(r=>[r.Date,r]));
  sources.directDaily=writeSource(wb,'数据_每日投放',['Date',...base],dates.map(date=>[date,...base.map(f=>dd.has(date)?dvalue(dd.get(date),f):(['Impressions','Clicks','Cost','Conversions'].includes(f)?0:null))]));
  const mf=[...reports.summary.metrics,'ym:pv:pageviews'];
  sources.metrika=writeSource(wb,'数据_Metrika汇总',['Period',...mf],[
    [`${p.start} - ${p.end}`,...reports.summary.metrics.map(f=>reports.summary.totals[f]),reports.pageviews_hits.totals['ym:pv:pageviews']],
    [`${old.date_from} - ${old.date_to}`,...reports.summary.metrics.map(f=>reports.previous_summary.totals[f]),reports.previous_pageviews_hits.totals['ym:pv:pageviews']],
  ]);
  const daily=new Map(reports.daily.rows.map(r=>[r['ym:s:date'],r]));
  const nr=new Map(reports.new_returning_daily.rows.map(r=>[`${r['ym:s:date']}:${r['ym:s:isNewUser:id']}`,r['ym:s:users']]));
  sources.metrikaDaily=writeSource(wb,'数据_每日流量',['Date',...reports.summary.metrics,'ReturningUsers'],dates.map(date=>[date,...reports.summary.metrics.map(f=>daily.get(date)?.[f] ?? (['ym:s:visits','ym:s:users','ym:s:pageviews','ym:s:newUsers'].includes(f)?0:null)),nr.get(date+':no')??0]));
  for(const key of ['devices','ages','sources']) {
    const report=reports[key],dim=report.dimensions[0];
    const rows=report.rows.slice().sort((a,b)=>(a[dim+':id']==null)-(b[dim+':id']==null)).map(r=>[r[dim]??'Unknown',r[dim+':id']??'',r['ym:s:visits'],null]);
    const src=writeSource(wb,`数据_${key}`,['Category','ID','Sessions','Share'],rows);
    src.knownCount=rows.filter(r=>r[1]!=='').length;
    for(let i=0;i<rows.length;i++)src.sheet.getRange(`D${i+2}`).formulas=[[`=IF(SUM(C$2:C$${rows.length+1})=0,0,C${i+2}/SUM(C$2:C$${rows.length+1}))`]];
    if(rows.length)src.sheet.getRange(`D2:D${rows.length+1}`).setNumberFormat('0.00%');
    sources[key]=src;
  }
  sources.newReturning=writeSource(wb,'数据_新老访客',['Type','ID','Users'],reports.new_returning.rows.map(r=>[r['ym:s:isNewUser'],r['ym:s:isNewUser:id'],r['ym:s:users']]));
  sources.goals=writeSource(wb,'数据_目标汇总',['GoalName','GoalId','ConvertedSessions','Reaches','ConversionRate'],m.goals.map(g=>{
    const t=reports[`goal_${g.id}`].totals;
    return [g.name,g.id,t[`ym:s:goal${g.id}visits`],t[`ym:s:goal${g.id}reaches`],t[`ym:s:goal${g.id}conversionRate`]];
  }));
  const goalFields=['Date',...m.goals.flatMap(g=>[`${g.id}:visits`,`${g.id}:reaches`,`${g.id}:rate`])];
  const gd=Object.fromEntries(m.goals.map(g=>[g.id,new Map(reports[`goal_${g.id}`].rows.map(r=>[r['ym:s:date'],r]))]));
  sources.goalDaily=writeSource(wb,'数据_目标每日',goalFields,dates.map(date=>[date,...m.goals.flatMap(g=>{
    const r=gd[g.id].get(date);
    return [r?.[`ym:s:goal${g.id}visits`]??0,r?.[`ym:s:goal${g.id}reaches`]??0,r?.[`ym:s:goal${g.id}conversionRate`]??null];
  })]));
  for(const src of Object.values(sources)) for(const f of src.fields) {
    const c=col(src.fields.indexOf(f)+1);
    if(/Id$|^ID$|^GoalId$/.test(f))src.sheet.getRange(`${c}2:${c}${Math.max(2,src.rows.length+1)}`).setNumberFormat('@');
  }
  return sources;
}
