// 模块：sem_automation/reporting/renderers/standard/report_classic_layout.mjs；内部模块由统一入口调用。
// VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化'
// 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' reports standard --client '.\config\clients\lingyu.json' --month 2026-07 --source existing --data-dir '.\outputs\_archive\lingyu\2026-07'
// 该示例复用本地数据；详见 docs/月报操作说明.md。
import fs from 'node:fs/promises';
import path from 'node:path';
import {col,quoteSheet} from './report_workbook_data.mjs';
import {addChart} from './report_workbook_charts.mjs';
import {trendSvg,distributionSvg,pngFromSvg} from './report_chart_images.mjs';

export async function renderClassic({wb,report,sources,bundle,internal,previews,chartRecords}) {
  const {client,layout,period,direct,metrika}=bundle;
  const cfg=layout.classic, colors=layout.style.colors, cols=Math.max(12,layout.direct_metrics.length+2),last=col(cols);
  const widths=Array.from({length:cols},(_,i)=>i===0?220:i===1?125:110);
  const width=widths.reduce((a,b)=>a+b,0),rh=24;
  const money=direct.meta.currency==='USD'?'$':direct.meta.currency;
  const labelMap={Impressions:'Impressions',Clicks:'Clicks',Ctr:'CTR (%)',Cost:`Expenditure (${money})`,AvgCpc:`Avg. CPC (${money})`,AvgDailyCost:`Avg. expenditure per day (${money})`,AvgPageviews:'Depth (pages)',ConversionRate:'Conversion (%)',CostPerConversion:`CPA (${money})`,Conversions:'Conversions'};
  const shortDate=d=>`${d.slice(8)}.${d.slice(5,7)}.${d.slice(0,4)}`;
  const dates=sources.directDaily.rows.map(r=>r[0]);
  let row=1,nativeRow=3;
  const native=wb.worksheets.add('可编辑图表');
  native.showGridLines=false;
  const info=wb.worksheets.add('期间对比与说明');
  info.showGridLines=false;
  function prepare(a,b){report.getRange(`A${a}:${last}${b}`).format={fill:'#FFFFFF',font:{name:'Arial',size:10,color:'#242B38'},rowHeightPx:rh,verticalAlignment:'center'};}
  function span(cell,text,format={}){report.getRange(cell).merge();report.getRange(cell).values=[[text]];report.getRange(cell).format=format;}
  function band(title,r){prepare(r,r);span(`A${r}:${last}${r}`,title,{fill:'#DAE3F4',font:{name:'Microsoft YaHei',bold:true,size:11},rowHeightPx:28});}
  function value(cell,formula,format='0.00',fontSize=10){report.getRange(cell).formulas=[[formula]];report.getRange(cell).setNumberFormat(format);report.getRange(cell).format.font.size=fontSize;}
  function delta(cell,current,previous){value(cell,`=IF(OR(NOT(ISNUMBER(${current})),NOT(ISNUMBER(${previous})),${previous}=0),"-",${current}/${previous}-1)`,'"▲ +"0.00%;"▼ -"0.00%;0.00%',10);
    report.getRange(cell).format.horizontalAlignment='left';
    report.getRange(cell).conditionalFormats.add('cellIs',{operator:'greaterThan',formula:0,format:{font:{color:'#25AD49'}}});
    report.getRange(cell).conditionalFormats.add('cellIs',{operator:'lessThan',formula:0,format:{font:{color:'#E94343'}}});}
  async function picture(name,svg,height,r){prepare(r,r+Math.ceil(height/rh)-1);const png=await pngFromSvg(svg);
    const filename=path.join(internal,'previews',`${name}_chart.png`);await fs.writeFile(filename,png);
    report.images.add({dataUrl:`data:image/png;base64,${png.toString('base64')}`,anchor:{from:{row:r-1,col:0},extent:{widthPx:width,heightPx:height}}});
    return Math.ceil(height/rh);
  }
  function keepNative(src,{key,title,series,knownOnly=false,type=layout.charts[key].type}){
    native.getRange(`A${nativeRow}:L${nativeRow+13}`).format={fill:'#FFFFFF',font:{name:'Arial',size:10},columnWidth:15,rowHeight:23};
    const c=addChart(native,src,{title,type,category:src.fields.includes('Date')?'Date':'Category',series,knownOnly,colors,startRow:nativeRow,endRow:nativeRow+12});
    if(c)chartRecords.push({title,type,source:src.name,sheet:native.name,startRow:nativeRow,endRow:nativeRow+12,presentation:'classic'});
    if(nativeRow===3)previews.push({name:'editable_charts',sheet:native.name,range:'A1:L15'});
    nativeRow+=14;
  }
  function fieldValues(src,field){const i=src.fields.indexOf(field);return src.rows.map(r=>typeof r[i]==='number'?r[i]:null);}
  native.getRange('A1:L1').merge();native.getRange('A1').values=[['可编辑图表（引用数据 sheet）；主报告的展示图片在重新运行时同步更新。']];

  prepare(1,3);widths.forEach((w,i)=>report.getRange(`${col(i+1)}1`).format.columnWidthPx=w);
  span(`A1:${last}1`,`Client ${client.name} (${direct.meta.client_login}), period ${shortDate(period.start)} - ${shortDate(period.end)}`,
    {fill:'#DAE3F4',font:{name:'Microsoft YaHei',size:11,bold:true},horizontalAlignment:'center',rowHeightPx:30});
  span('A2:B2','Total:',{font:{bold:true}});
  span('A3:B3',`from ${shortDate(period.start)} to ${shortDate(period.end)}`,{font:{size:9}});
  const order=cfg.summary_order.filter(f=>layout.direct_metrics.some(m=>m.field===f));
  for(const m of layout.direct_metrics)if(!order.includes(m.field))order.push(m.field);
  order.forEach((f,i)=>{const c=col(i+3),m=layout.direct_metrics.find(m=>m.field===f);report.getRange(`${c}2`).values=[[labelMap[f]??m.label]];value(`${c}3`,`=${sources.direct.cell(f,2)}`,m.format);});
  report.getRange(`C2:${last}2`).format={font:{bold:true,size:9},wrapText:true,rowHeightPx:42};
  report.getRange(`A3:${last}3`).format.borders={bottom:{style:'thin',color:'#DAE3F4'}};

  row=5;prepare(row,row+3);span(`A${row}:${last}${row}`,'Key metrics',{font:{size:18,bold:true},rowHeightPx:32});row++;
  const directColors={Clicks:'#3488FF',Conversions:'#79CA1C',Cost:'#E86475',Impressions:'#7945E8'};
  const trendFields=layout.charts.direct_daily.fields;
  trendFields.forEach((f,i)=>{const a=Math.floor(i*cols/trendFields.length)+1,b=Math.floor((i+1)*cols/trendFields.length);const title=f==='Conversions'?`Conversions: ${direct.meta.goal_id??'All goals'}`:f==='Cost'?'Expenses':f;
    span(`${col(a)}${row}:${col(b)}${row}`,`■ ${title}`,{font:{size:11,color:directColors[f]}});
    const mid=Math.max(a,Math.floor((a+b)/2));report.getRange(`${col(a)}${row+1}:${col(mid)}${row+1}`).merge();value(`${col(a)}${row+1}`,`=${sources.direct.cell(f,2)}`,f==='Cost'?`"${money}"#,##0.00`:f==='Conversions'?'0.00':'#,##0',20);
    report.getRange(`${col(a)}${row+1}`).format.horizontalAlignment='left';
    if(mid<b){report.getRange(`${col(mid+1)}${row+1}:${col(b)}${row+1}`).merge();delta(`${col(mid+1)}${row+1}`,sources.direct.cell(f,2),sources.direct.cell(f,3));}
    keepNative(sources.directDaily,{key:'direct_daily',title:labelMap[f],series:[{field:f,label:title}]});
  });
  report.getRange(`A${row+1}:${last}${row+1}`).format.rowHeightPx=35;row+=3;
  const directSeries=trendFields.map(f=>({label:f,values:fieldValues(sources.directDaily,f),color:directColors[f]}));
  row+=await picture('direct',trendSvg({width,height:230,dates,series:directSeries,type:layout.charts.direct_daily.type,independent:true,legend:false}),230,row);
  prepare(row,row);span(`A${row}:${last}${row}`,'趋势图各指标独立缩放，仅比较走势；金额、点击与转化请以上方原值为准。',{font:{size:9,color:'#7B89A6'}});row+=2;
  previews.push({name:'direct',range:`A1:${last}${row-1}`});

  const campaignStart=row;
  prepare(row,row+sources.campaign.rows.length);report.getRange(`A${row}`).values=[['Campaign']];report.getRange(`B${row}`).values=[['Date']];
  layout.direct_metrics.forEach((m,i)=>report.getRange(`${col(i+3)}${row}`).values=[[labelMap[m.field]??m.label]]);
  report.getRange(`A${row}:${last}${row}`).format={fill:'#DAE3F4',font:{size:9,bold:true},wrapText:true,rowHeightPx:42};
  sources.campaign.rows.forEach((r,i)=>{const rr=row+i+1;value(`A${rr}`,`=${sources.campaign.cell('CampaignName',i+2)}`,'General');report.getRange(`B${rr}`).values=[[period.start+' - '+period.end]];report.getRange(`B${rr}`).format={font:{size:8},wrapText:true};
    layout.direct_metrics.forEach((m,j)=>value(`${col(j+3)}${rr}`,`=${sources.campaign.cell(m.field,i+2)}`,m.format));report.getRange(`A${rr}:${last}${rr}`).format.rowHeightPx=36;});
  row+=sources.campaign.rows.length+2;
  previews.push({name:'campaign',range:`A${campaignStart}:${last}${row-1}`});

  const trafficStart=row;band('网站浏览情况',row);row+=2;
  const cardOrder=cfg.metrika_cards.filter(f=>layout.metrika_metrics.some(m=>m.field===f));
  // 额外选中的字段也会展示，不能因使用经典皮肤而丢失指标。
  const extra=layout.metrika_metrics.filter(m=>!cardOrder.includes(m.field)&&m.field!=='ym:s:pageviews');
  cardOrder.push(...extra.map(m=>m.field));
  const metricNames={'ym:pv:pageviews':'Pageviews','ym:s:users':'Users','ym:s:visits':'Sessions','ym:s:avgVisitDurationSeconds':'Time on site','ym:s:pageDepth':'Page depth','ym:s:bounceRate':'Bounce rate'};
  prepare(row,row+Math.ceil(cardOrder.length/3)*4-1);
  cardOrder.forEach((f,i)=>{const r=row+Math.floor(i/3)*4,a=Math.floor(i%3*cols/3)+1,b=Math.floor((i%3+1)*cols/3);
    span(`${col(a)}${r}:${col(b)}${r}`,metricNames[f]??layout.metrika_metrics.find(m=>m.field===f).label,{font:{size:11,color:'#7B89A6'}});
    const mid=a+1;report.getRange(`${col(a)}${r+1}:${col(mid)}${r+1}`).merge();
    const ref=sources.metrika.cell(f,2),format=f.includes('Duration')?'[m]:ss':f.includes('bounceRate')?'0.00"%"':layout.metrika_metrics.find(m=>m.field===f).format;
    value(`${col(a)}${r+1}`,`=${ref}${f.includes('Duration')?'/86400':''}`,format,23);
    report.getRange(`${col(a)}${r+1}`).format.horizontalAlignment='left';
    report.getRange(`${col(mid+1)}${r+1}:${col(b)}${r+1}`).merge();
    if(f==='ym:s:bounceRate')value(`${col(mid+1)}${r+1}`,`=${ref}-${sources.metrika.cell(f,3)}`,'+0.00" pp";-0.00" pp";0.00" pp"',10);
    else delta(`${col(mid+1)}${r+1}`,ref,sources.metrika.cell(f,3));
    report.getRange(`A${r+1}:${last}${r+1}`).format.rowHeightPx=38;
    report.getRange(`${col(a)}${r+2}:${col(b)}${r+2}`).format.borders={bottom:{style:'thin',color:'#EEF2F8'}};
  });
  row+=Math.ceil(cardOrder.length/3)*4;
  prepare(row,row);span(`A${row}:${last}${row}`,'Site traffic',{font:{size:18},rowHeightPx:32});row++;
  const trafficSeries=layout.charts.traffic.fields.map((f,i)=>({field:f,label:{'ym:s:visits':'Sessions','ym:s:users':'Users','ym:s:pageviews':'Pageviews'}[f],values:fieldValues(sources.metrikaDaily,f),total:metrika.reports.summary.totals[f],color:colors[i]}));
  row+=await picture('traffic',trendSvg({width,height:255,dates,series:trafficSeries,type:layout.charts.traffic.type}),255,row);
  keepNative(sources.metrikaDaily,{key:'traffic',title:'Site traffic',series:trafficSeries});
  row++;previews.push({name:'traffic',range:`A${trafficStart}:${last}${row-1}`});

  for(const [key,title] of [['devices','Device type'],['ages','Age'],['sources','Traffic sources']]){
    const start=row,src=sources[key],knownOnly=key==='ages'&&layout.charts.ages.exclude_unknown;
    const n=knownOnly?src.knownCount:src.rows.length;
    const data=src.rows.slice(0,n).map(r=>({label:r[0],value:r[2]})).sort((a,b)=>b.value-a.value);
    const unknown=knownOnly?src.rows.slice(n).reduce((s,r)=>s+r[2],0):0;
    const note=unknown?`未识别年龄的 ${unknown} 次会话保留在数据页；本图按已识别年龄计算占比。`:'';
    const height=data.length>4?280:250;
    row+=await picture(key,distributionSvg({width,height,title,rows:data,colors,type:layout.charts[key].type,note}),height,row);
    keepNative(src,{key,title,series:[{field:'Sessions',label:'Sessions'}],knownOnly});
    prepare(row,row);report.getRange(`A${row}:${last}${row}`).format.fill='#EEF2F8';row++;
    previews.push({name:key,range:`A${start}:${last}${row-1}`});
  }

  const nrStart=row;prepare(row,row);span(`A${row}:${last}${row}`,'New and returning users',{font:{size:18},rowHeightPx:32});row++;
  const nrSeries=[{field:'ym:s:newUsers',label:'New users',id:'yes',color:colors[0]},{field:'ReturningUsers',label:'Returning users',id:'no',color:colors[1]}].map(s=>({...s,values:fieldValues(sources.metrikaDaily,s.field),total:metrika.reports.new_returning.rows.find(r=>r['ym:s:isNewUser:id']===s.id)?.['ym:s:users']??0}));
  row+=await picture('new_returning',trendSvg({width,height:235,dates,series:nrSeries,type:layout.charts.new_returning.type}),235,row);
  keepNative(sources.metrikaDaily,{key:'new_returning',title:'New and returning users',series:nrSeries});row++;
  previews.push({name:'new_returning',range:`A${nrStart}:${last}${row-1}`});

  band('转化情况',row);row++;
  for(let i=0;i<metrika.goals.length;i++){
    const g=metrika.goals[i],values=sources.goals.rows[i],start=row;
    if(!layout.charts.goals.include_zero&&values[3]===0)continue;
    prepare(row,row+1);span(`A${row}:D${row}`,g.name,{font:{name:'Microsoft YaHei',size:11,bold:true}});
    span(`E${row}:${last}${row}`,`ID ${g.id}`,{font:{size:9,color:'#7B89A6'}});row++;
    if(values[3]===0){span(`A${row}:${last}${row}`,'No goal data',{font:{size:10,color:'#7B89A6'}});row++;}
    else{
      prepare(row,row+5);
      for(const [k,label,field,fmt] of [[0,'Conversion rate','ConversionRate','0.00"%"'],[1,'Converted sessions','ConvertedSessions','0'],[2,'Conversions','Reaches','0']]){
        span(`A${row+k}:B${row+k}`,`■ ${label}`,{font:{size:10,color:colors[k]}});report.getRange(`C${row+k}:D${row+k}`).merge();value(`C${row+k}`,`=${sources.goals.cell(field,i+2)}`,fmt);
      }
      const chartWidth=width-widths.slice(0,4).reduce((a,b)=>a+b,0);
      const goalSeries=[{field:`${g.id}:rate`,label:'Conversion rate',axis:'rate',color:colors[0]}, {field:`${g.id}:visits`,label:'Converted sessions',color:colors[1]}, {field:`${g.id}:reaches`,label:'Conversions',color:colors[2]}].map(s=>({...s,values:fieldValues(sources.goalDaily,s.field)}));
      const png=await pngFromSvg(trendSvg({width:chartWidth,height:140,dates,series:goalSeries,type:layout.charts.goals.type,dual:true,legend:false}));
      report.images.add({dataUrl:`data:image/png;base64,${png.toString('base64')}`,anchor:{from:{row:row-1,col:4},extent:{widthPx:chartWidth,heightPx:140}}});
      keepNative(sources.goalDaily,{key:'goals',title:g.name,series:goalSeries.slice(1)});row+=6;
    }
    prepare(row,row);report.getRange(`A${row}:${last}${row}`).format={fill:'#EEF2F8',rowHeightPx:5};row++;
    previews.push({name:`goal_${g.id}`,range:`A${start}:${last}${row-1}`});
  }
  prepare(row,row+1);span(`A${row}:${last}${row}`,`统计周期：${period.start} 至 ${period.end}；比较周期：${direct.meta.comparison_period.date_from} 至 ${direct.meta.comparison_period.date_to}。`,{font:{size:9,color:'#7B89A6'}});
  row++;span(`A${row}:${last}${row}`,'转化为 Direct All goals / Metrika 目标统计，并非实际询盘；具体客户咨询以实际收到的反馈为准。',{font:{size:9,color:'#7B89A6'}});
  report.showGridLines=false;report.freezePanes.freezeRows(3);

  const metrics=[...layout.direct_metrics.map(m=>({m,src:sources.direct,label:'Direct · '+(labelMap[m.field]??m.label)})),...layout.metrika_metrics.map(m=>({m,src:sources.metrika,label:'Metrika · '+m.label}))];
  info.getRange(`A1:D${metrics.length+14}`).format={fill:'#FFFFFF',font:{name:'Microsoft YaHei',size:10},columnWidth:24,rowHeight:25};
  info.getRange('A1:D1').merge();info.getRange('A1').values=[[`${client.name} | ${period.start} 至 ${period.end}`]];
  info.getRange('A2:D2').values=[['指标','本期','上期','变化']];info.getRange('A2:D2').format.fill='#DAE3F4';info.getRange(`A1:A${metrics.length+14}`).format.columnWidth=48;
  metrics.forEach(({m,src,label},i)=>{const r=i+3;info.getRange(`A${r}`).values=[[label]];info.getRange(`B${r}:C${r}`).formulas=[[`=${src.cell(m.field,2)}`,`=${src.cell(m.field,3)}`]];info.getRange(`B${r}:C${r}`).setNumberFormat(m.format);
    info.getRange(`D${r}`).formulas=[[m.change==='points'?`=B${r}-C${r}`:`=IF(OR(NOT(ISNUMBER(B${r})),NOT(ISNUMBER(C${r})),C${r}=0),"-",B${r}/C${r}-1)`]];info.getRange(`D${r}`).setNumberFormat(m.change==='points'?'0.00" pp"':'0.00%');});
  const notes=[`上期：${direct.meta.comparison_period.date_from} 至 ${direct.meta.comparison_period.date_to}。`,`Metrika Counter：${metrika.meta.counter_id}；Direct：${direct.meta.client_login}。`,
    '主报告按原版视觉自动绘图；修改数据后需重跑以同步图片。可编辑图表页保留原生 Excel 图表。',
    '顶部 Pageviews 卡片为页面事件量；Site traffic 的 Pageviews 为会话口径，二者不可混用。',
    '设备、年龄、来源图按 Sessions 统计；不能与按 Users 统计的图表直接互换占比。',
    '访客数按整个区间去重，不等于每日访客数之和；新访客与回访访客可能跨组。',
    '年龄占比按配置排除未识别年龄；未识别记录仍保留在数据页。',
    '主报告的卡片变化使用紧邻比较期；截图的自动比较区间可能不同。',
    '否词页为人工维护内容；不生成否词，也不复制参考客户的分析文字。'];
  notes.forEach((note,i)=>{const r=metrics.length+5+i;info.getRange(`A${r}:D${r}`).merge();info.getRange(`A${r}`).values=[[note]];info.getRange(`A${r}:D${r}`).format={wrapText:true,rowHeight:30,font:{size:9,color:'#68748B'}};});
  previews.push({name:'comparison',sheet:info.name,range:`A1:D${metrics.length+14}`});
}
