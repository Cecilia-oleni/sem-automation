// 模块：sem_automation/reporting/renderers/standard/yandex_report_workbook.mjs；内部模块由统一入口调用。
// VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化'
// 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' reports standard --client '.\config\clients\lingyu.json' --month 2026-07 --source existing --data-dir '.\outputs\_archive\lingyu\2026-07'
// 该示例复用本地数据；详见 docs/月报操作说明.md。
import fs from 'node:fs/promises';
import path from 'node:path';
import {SpreadsheetFile,FileBlob} from '@oai/artifact-tool';
import {buildSources,col,literal,quoteSheet,directValue} from './report_workbook_data.mjs';
import {addChart} from './report_workbook_charts.mjs';
import {renderClassic} from './report_classic_layout.mjs';
import {exportCustomerWorkbook} from './report_customer_workbook.mjs';

const args={};for(let i=2;i<process.argv.length;i+=2)args[process.argv[i].replace(/^--/,'')]=process.argv[i+1];
if(!args.input||!args.output)throw new Error('需要 --input --output');
const bundle=JSON.parse(await fs.readFile(args.input,'utf8'));
if(bundle.schema!=='yandex_report_v1')throw new Error('不支持的数据包版本');
const {client,layout,period, direct,metrika}=bundle, style=layout.style;
const internal=path.join(path.dirname(args.output),'_internal');
await fs.mkdir(path.join(internal,'previews'),{recursive:true});
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(client.template));
const report=wb.worksheets.getItem(layout.report_sheet);
const oldQuery=wb.worksheets.items.find(s=>new RegExp(layout.search_sheet_pattern).test(s.name));
if(!oldQuery)throw new Error('模板未找到搜索词 sheet');
oldQuery.name=layout.search_sheet;
const query=oldQuery;
const negative=wb.worksheets.getItem(layout.negative_sheet);
const negativeSnapshot=negative.getUsedRange().values;
if(client.negative_words==='blank')negative.getUsedRange().clear({applyTo:'contents'});
for(const s of [report,query]) {
  s.deleteAllDrawings();s.getUsedRange().unmerge();s.getUsedRange().clear({applyTo:'all'});
}
const sources=buildSources(wb,bundle);
const endCol=Math.max(12,layout.direct_metrics.length+2), end=col(endCol);
const previews=[],chartRecords=[];
let row=1;
function prepare(r1,r2) {
  report.getRange(`A${r1}:${end}${r2}`).format={fill:'#FFFFFF',font:{name:style.font,size:10,color:style.text},rowHeight:style.row_height,columnWidth:style.column_width,verticalAlignment:'center'};
}
function band(text,r=row) {
  prepare(r,r);report.getRange(`A${r}:${end}${r}`).merge();report.getRange(`A${r}`).values=[[text]];
  report.getRange(`A${r}:${end}${r}`).format={fill:style.title_fill,font:{bold:true,size:12},rowHeight:30};
}
function textRow(text,r=row) {
  prepare(r,r);report.getRange(`A${r}:${end}${r}`).merge();report.getRange(`A${r}`).values=[[text]];
  report.getRange(`A${r}:${end}${r}`).format={wrapText:true,rowHeight:30,font:{size:9,color:'#637088'}};
}
function metricLabel(m){return m.label.replaceAll('{currency}',direct.meta.currency);}
function chart(src,opts) {
  const c=addChart(report,src,{colors:style.colors,endCol:endCol+1,...opts});
  if(c)chartRecords.push({title:opts.title,type:opts.type,source:src.name,startRow:opts.startRow,endRow:opts.endRow});
}
function chartBlock(key,title,src,series,extra={}) {
  const begin=row;band(title);row++;
  prepare(row,row+style.chart_rows);
  chart(src,{type:layout.charts[key].type,title,category:'Date',series,startRow:row,endRow:row+style.chart_rows,...extra});
  row+=style.chart_rows+1;previews.push({name:key,range:`A${begin}:${end}${row}`});row++;
}

if(layout.presentation==='classic') {
  await renderClassic({wb,report,sources,bundle,internal,previews,chartRecords});
} else {
band(`${client.name} | ${layout.title}`);row++;
textRow(`${period.start} 至 ${period.end}  ·  ${period.days} 天  |  Direct：${direct.meta.client_login}  |  Metrika：${metrika.meta.counter_id}`);row+=2;
band('Direct 投放汇总');row++;
prepare(row,row+3);
report.getRange(`A${row}`).values=[['周期']];
layout.direct_metrics.forEach((m,i)=>{
  const c=col(i+2);report.getRange(`${c}${row}`).values=[[metricLabel(m)]];
  for(const [offset,sourceRow] of [[1,2],[2,3]])report.getRange(`${c}${row+offset}`).formulas=[[`=${sources.direct.cell(m.field,sourceRow)}`]];
  report.getRange(`${c}${row+3}`).formulas=[[`=IF(OR(NOT(ISNUMBER(${c}${row+1})),NOT(ISNUMBER(${c}${row+2})),${c}${row+2}=0),"-",${c}${row+1}/${c}${row+2}-1)`]];
  report.getRange(`${c}${row+1}:${c}${row+2}`).setNumberFormat(m.format);
  report.getRange(`${c}${row+3}`).setNumberFormat('0.00%');
});
report.getRange(`A${row+1}:A${row+3}`).values=[['本期'],['上期'],['变化 (%)']];
report.getRange(`A${row}:${end}${row}`).format={font:{bold:true},wrapText:true,rowHeight:40};
row+=4;textRow(`上期：${direct.meta.comparison_period.date_from} 至 ${direct.meta.comparison_period.date_to}。转化口径：${direct.meta.conversion_scope}；不等同于实际询盘。`);row+=2;
const trendStart=row, fields=layout.charts.direct_daily.fields;
prepare(row,row+style.chart_rows);
fields.forEach((f,i)=>{
  const w=endCol/fields.length;
  chart(sources.directDaily,{type:layout.charts.direct_daily.type,title:metricLabel(layout.direct_metrics.find(m=>m.field===f)??{label:f}),
    category:'Date',series:[{field:f,label:f}],startRow:row,endRow:row+style.chart_rows,startCol:Math.floor(i*w)+1,endCol:Math.floor((i+1)*w)+1});
});
row+=style.chart_rows+2;previews.push({name:'direct',range:`A1:${end}${row-1}`});
band('广告系列表现');row++;
prepare(row,row+sources.campaign.rows.length);
report.getRange(`A${row}:B${row}`).merge();report.getRange(`A${row}`).values=[['广告系列']];
layout.direct_metrics.forEach((m,i)=>report.getRange(`${col(i+3)}${row}`).values=[[metricLabel(m)]]);
report.getRange(`A${row}:${end}${row}`).format={font:{bold:true},wrapText:true,rowHeight:40};
sources.campaign.rows.forEach((r,i)=>{
  const dest=row+i+1;report.getRange(`A${dest}:B${dest}`).merge();
  report.getRange(`A${dest}`).formulas=[[`=${sources.campaign.cell('CampaignName',i+2)}`]];
  layout.direct_metrics.forEach((m,j)=>{const c=col(j+3);report.getRange(`${c}${dest}`).formulas=[[`=${sources.campaign.cell(m.field,i+2)}`]];report.getRange(`${c}${dest}`).setNumberFormat(m.format);});
});
row+=sources.campaign.rows.length+2;
const trafficStart=row;
band('网站浏览情况 · Metrika 全站流量');row++;
prepare(row,row+layout.metrika_metrics.length);
report.getRange(`A${row}:D${row}`).merge();report.getRange(`A${row}`).values=[['指标']];
for(const [a,b,label] of [['E','F','本期'],['G','H','上期'],['I','L','环比（跳出率为百分点）']]){report.getRange(`${a}${row}:${b}${row}`).merge();report.getRange(`${a}${row}`).values=[[label]];}
layout.metrika_metrics.forEach((m,i)=>{
  const r=row+i+1;report.getRange(`A${r}:D${r}`).merge();report.getRange(`A${r}`).values=[[m.label]];
  for(const [a,b,sourceRow]of[['E','F',2],['G','H',3]]){report.getRange(`${a}${r}:${b}${r}`).merge();report.getRange(`${a}${r}`).formulas=[[`=${sources.metrika.cell(m.field,sourceRow)}`]];report.getRange(`${a}${r}`).setNumberFormat(m.format);}
  report.getRange(`I${r}:L${r}`).merge();
  report.getRange(`I${r}`).formulas=[[m.change==='points'?`=E${r}-G${r}`:`=IF(G${r}=0,"-",E${r}/G${r}-1)`]];
  report.getRange(`I${r}`).setNumberFormat(m.change==='points'?'0.00" 个百分点"':'0.00%');
});
row+=layout.metrika_metrics.length+2;
textRow('页面浏览量卡片按事件统计；流量图按会话统计。访客数按整个区间去重，不能把每日访客数直接相加。');row+=2;
prepare(row,row+style.chart_rows);
chart(sources.metrikaDaily,{type:layout.charts.traffic.type,title:'网站流量趋势',category:'Date',series:layout.charts.traffic.fields.map(f=>({field:f,label:{'ym:s:visits':'会话数','ym:s:users':'访客数','ym:s:pageviews':'页面浏览量'}[f]})),startRow:row,endRow:row+style.chart_rows});
row+=style.chart_rows+2;previews.push({name:'traffic',range:`A${trafficStart}:${end}${row-1}`});
for(const [key,title]of[['devices','设备分布'],['ages','年龄分布'],['sources','流量来源']]) {
  const begin=row;band(title);row++;
  const src=sources[key],knownOnly=key==='ages'&&layout.charts.ages.exclude_unknown;
  const n=knownOnly?src.knownCount:src.rows.length;
  const height=Math.max(style.chart_rows,n+3);prepare(row,row+height);
  chart(src,{type:layout.charts[key].type,title,category:'Category',series:[{field:'Sessions',label:'会话数'}],startRow:row,endRow:row+height,startCol:1,endCol:8,knownOnly});
  report.getRange(`H${row}:J${row}`).merge();report.getRange(`H${row}`).values=[['分类']];report.getRange(`K${row}`).values=[['会话数']];report.getRange(`L${row}`).values=[['占比']];
  for(let i=0;i<n;i++){
    const r=row+i+1;report.getRange(`H${r}:J${r}`).merge();report.getRange(`H${r}`).formulas=[[`=${src.cell('Category',i+2)}`]];
    report.getRange(`K${r}`).formulas=[[`=${src.cell('Sessions',i+2)}`]];
    report.getRange(`L${r}`).formulas=[[`=IF(SUM(${quoteSheet(src.name)}!C$2:C$${n+1})=0,"-",K${r}/SUM(${quoteSheet(src.name)}!C$2:C$${n+1}))`]];report.getRange(`L${r}`).setNumberFormat('0.00%');
  }
  row+=height+1;
  if(knownOnly){textRow(`年龄图仅展示已识别年龄；未识别会话 ${src.rows.slice(n).reduce((s,r)=>s+r[2],0)} 次，不计入年龄占比。`);row++;}
  previews.push({name:key,range:`A${begin}:${end}${row}`});row++;
}
const nrStart=row;
band('新访客与回访访客');row++;
textRow(metrika.reports.new_returning.rows.map(r=>`${r['ym:s:isNewUser:id']==='yes'?'新访客':'回访访客'} ${r['ym:s:users']}`).join('  |  ')+'；同一访客在区间内可能跨组。');row++;
prepare(row,row+style.chart_rows);
chart(sources.metrikaDaily,{type:layout.charts.new_returning.type,title:'新老访客趋势',category:'Date',series:[{field:'ym:s:newUsers',label:'新访客'},{field:'ReturningUsers',label:'回访访客'}],startRow:row,endRow:row+style.chart_rows});
row+=style.chart_rows+2;previews.push({name:'new_returning',range:`A${nrStart}:${end}${row-1}`});
for(let i=0;i<metrika.goals.length;i++) {
  const g=metrika.goals[i],values=sources.goals.rows[i];
  if(!layout.charts.goals.include_zero&&values[3]===0)continue;
  const begin=row;band(`目标：${g.name}`);row++;
  textRow(`转化次数 ${values[3]}  |  转化会话 ${values[2]}  |  转化率 ${Number(values[4]).toFixed(2)}%  |  Goal ID ${g.id}`);row++;
  if(values[3]===0){textRow('本期无目标达成数据。');row++;}
  else {
    prepare(row,row+style.chart_rows);
    chart(sources.goalDaily,{type:layout.charts.goals.type,title:g.name,category:'Date',series:[{field:`${g.id}:visits`,label:'转化会话'},{field:`${g.id}:reaches`,label:'转化次数'}],startRow:row,endRow:row+style.chart_rows});
    row+=style.chart_rows+1;
  }
  previews.push({name:`goal_${g.id}`,range:`A${begin}:${end}${row}`});row++;
}
band('数据说明');row++;
for(const note of ['Direct 为广告投放数据，Metrika 为网站全站数据，统计与归因范围不同。',`比较周期：${direct.meta.comparison_period.date_from} 至 ${direct.meta.comparison_period.date_to}。上期为零时变化率显示“-”。`,'图表与主要指标引用后方数据 sheet；更新原始 API 数据后重跑可生成新周期报告。','否词页为模板中的人工维护内容，本流程不生成否词。']){textRow(note);row++;}
report.showGridLines=false;report.freezePanes.freezeRows(2);
}

// 搜索词重建全部可见明细；保留 API 17 列，避免品牌分类推断。
const qfields=['Query','CampaignName','CampaignId','AdGroupName','AdGroupId','CriterionType','MatchType','Criterion','TargetingCategory','Impressions','Clicks','Ctr','Cost','AvgCpc','Conversions','ConversionRate','CostPerConversion'];
const qheaders=['Search query','Campaign name','Campaign No.','Group name','Group No.','Criteria type','Match type','Keyword','Request category (legacy)','Impressions','Clicks','CTR, %',`Expenditure, ${direct.meta.currency}`,`CPC, ${direct.meta.currency}`,'Conversions','CR, %',`CPA, ${direct.meta.currency}`];
const qr=direct.raw.search_queries;
query.getRange(`A1:Q${Math.max(6,qr.length+6)}`).format={fill:'#FFFFFF',font:{name:style.font,size:10},columnWidth:18,rowHeight:28};
for(const [r,t]of[[1,`Client: ${client.name} (${direct.meta.client_login})`],[2,'Search queries | Clicks > 0'],[3,`Period: ${period.start} - ${period.end}`]]){query.getRange(`A${r}:Q${r}`).merge();query.getRange(`A${r}`).values=[[t]];}
query.getRange('A5:Q5').values=[qheaders];query.getRange('A5:Q5').format={font:{bold:true},wrapText:true,rowHeight:42};
query.getRange('A6').values=[['Detail total']];
if(qr.length)query.getRange(`A7:Q${qr.length+6}`).values=qr.map(r=>qfields.map(f=>literal(directValue(direct.meta,r,f))));
for(const c of ['J','K','M','O'])query.getRange(`${c}6`).formulas=[[qr.length?`=SUM(${c}7:${c}${qr.length+6})`:'=0']];
for(const [c,f]of Object.entries({L:'=IF(J6=0,"-",K6/J6*100)',N:'=IF(K6=0,"-",M6/K6)',P:'=IF(K6=0,"-",O6/K6*100)',Q:'=IF(O6=0,"-",M6/O6)'}))query.getRange(`${c}6`).formulas=[[f]];
query.getRange(`L6:Q${Math.max(6,qr.length+6)}`).setNumberFormat('0.00');
for(const [c,w]of[['A',58],['B',24],['D',38],['H',68],['I',25]])query.getRange(`${c}1:${c}${qr.length+6}`).format.columnWidth=w;
if(qr.length){query.getRange(`A7:I${qr.length+6}`).format.wrapText=true;query.getRange(`A7:Q${qr.length+6}`).format.rowHeight=80;}
query.freezePanes.freezeRows(6);

if(client.negative_words==='preserve'&&JSON.stringify(negative.getUsedRange().values)!==JSON.stringify(negativeSnapshot))throw new Error('否词内容发生意外变化');
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A',options:{useRegex:true,maxResults:50}});
await fs.writeFile(path.join(internal,'formula-check.ndjson'),errors.ndjson);
await fs.writeFile(path.join(internal,'chart-manifest.json'),JSON.stringify(chartRecords,null,2));
previews.push({name:'search',sheet:query.name,range:'A1:Q10'},{name:'negative',sheet:negative.name,range:'A1:D15'});
for(const src of Object.values(sources))previews.push({name:src.name,sheet:src.name,range:`A1:${col(Math.min(8,src.fields.length))}${Math.min(7,src.rows.length+1)}`});
await fs.writeFile(path.join(internal,'preview-ranges.json'),JSON.stringify(previews,null,2));
for(const p of previews){const img=await wb.render({sheetName:p.sheet??report.name,range:p.range,scale:1,format:'png'});await fs.writeFile(path.join(internal,'previews',`${p.name}.png`),new Uint8Array(await img.arrayBuffer()));}
const output=await SpreadsheetFile.exportXlsx(wb);await output.save(args.output);
if(args['customer-output']){
  await exportCustomerWorkbook(wb,{output:args['customer-output'],keepSheets:[report.name,query.name,negative.name]});
  console.log(`客户版已生成：${args['customer-output']}`);
}
console.log(`报告已生成：${args.output}; 图表 ${chartRecords.length} 个`);
