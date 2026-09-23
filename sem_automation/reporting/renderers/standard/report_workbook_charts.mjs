// 模块：sem_automation/reporting/renderers/standard/report_workbook_charts.mjs；内部模块由统一入口调用。
// VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化'
// 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' reports standard --client '.\config\clients\lingyu.json' --month 2026-07 --source existing --data-dir '.\outputs\_archive\lingyu\2026-07'
// 该示例复用本地数据；详见 docs/月报操作说明.md。
import {col,quoteSheet} from './report_workbook_data.mjs';
export function addChart(sheet,src,{type,title,category,series,startRow,endRow,startCol=1,endCol=13,colors,knownOnly=false}) {
  const count=knownOnly?src.knownCount:src.rows.length;
  if(!count) {
    sheet.getRange(`${col(startCol)}${startRow}`).values=[[`${title}：无数据`]];
    return null;
  }
  const c=sheet.charts.add(type,{chartType:type,title,hasLegend:true});
  c.title=title;c.titleTextStyle.fontSize=12;
  // setPosition 的第二个单元格包含在矩形内；减一避免覆盖相邻图表或表格。
  c.setPosition(`${col(startCol)}${startRow}`,`${col(endCol-1)}${endRow-1}`);
  const catCol=col(src.fields.indexOf(category)+1);
  series.forEach((entry,i)=>{
    const s=c.series.add(entry.label);
    s.categoryFormula=`${quoteSheet(src.name)}!$${catCol}$2:$${catCol}$${count+1}`;
    const vcol=col(src.fields.indexOf(entry.field)+1);
    s.formula=`${quoteSheet(src.name)}!$${vcol}$2:$${vcol}$${count+1}`;
    if(!['pie','doughnut'].includes(type))s.fill=colors[i%colors.length];
  });
  if(!['pie','doughnut'].includes(type)) {
    const ticks=endCol-startCol<=4?4:8;
    const maxValue=Math.max(0,...src.rows.flatMap(row=>series.map(s=>Number(row[src.fields.indexOf(s.field)])||0)));
    c.xAxis={axisType:'textAxis',textStyle:{fontSize:9},tickLabelInterval:count>ticks?Math.ceil(count/ticks):1};
    c.yAxis={numberFormatCode:series.some(s=>s.field==='Cost')?'0.00':maxValue<5?'0.0':'0',min:0,textStyle:{fontSize:9}};
  }
  return c;
}
