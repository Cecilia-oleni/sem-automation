// 模块：sem_automation/reporting/renderers/standard/report_customer_workbook.mjs；内部模块由统一入口调用。
// VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化'
// 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' reports standard --client '.\config\clients\lingyu.json' --month 2026-07 --source existing --data-dir '.\outputs\_archive\lingyu\2026-07'
// 该示例复用本地数据；详见 docs/月报操作说明.md。
import fs from 'node:fs/promises';
import path from 'node:path';
import {SpreadsheetFile} from '@oai/artifact-tool';
import {literal} from './report_workbook_data.mjs';

export async function exportCustomerWorkbook(wb,{output,keepSheets}) {
  if(!keepSheets?.length||new Set(keepSheets).size!==keepSheets.length)throw new Error('客户版保留页不能为空或重复');
  const names=wb.worksheets.items.map(s=>s.name);
  for(const name of keepSheets)if(!names.includes(name))throw new Error(`客户版缺少结果页：${name}`);
  // 原生图表可能引用待删除源表；当前交付皮肤使用已独立的图表图片。
  // 不允许输出包含悬空引用的图表；dashboard 可通过 --internal-only 单独生成。
  for(const name of keepSheets)if(wb.worksheets.getItem(name).charts.items.length)throw new Error('客户版请使用 classic 版式；原生图表完整版本可通过 --internal-only 生成');
  const frozen=[];
  // 先一次性读取所有结果，避免前一个单元格的修改影响后面的公式。
  for(const name of keepSheets){
    const sheet=wb.worksheets.getItem(name),range=sheet.getUsedRange();
    const values=range.values,formulas=range.formulas;
    for(let r=0;r<formulas.length;r++)for(let c=0;c<(formulas[r]?.length??0);c++)if(formulas[r][c]){
      const value=values[r]?.[c];
      if(value===undefined||value===null||typeof value==='string'&&/^#(?:REF!|DIV\/0!|VALUE!|NAME\?|N\/A|NUM!|SPILL!|CALC!)/.test(value))throw new Error(`无法固定 ${name} 的公式结果，请先修复内部版`);
      frozen.push({range:range.getCell(r,c),value});
    }
  }
  for(const cell of frozen)cell.range.values=[[literal(cell.value)]];
  const removed=names.filter(name=>!keepSheets.includes(name));
  await wb.apply(removed.map(name=>({op:'sheet.remove',target:name})));
  for(const name of keepSheets){
    const formulas=wb.worksheets.getItem(name).getUsedRange().formulas;
    if(formulas.some(row=>row.some(Boolean)))throw new Error(`客户版仍有公式：${name}`);
  }
  const report={kept:keepSheets,removed,frozen_formula_count:frozen.length};
  await fs.mkdir(path.dirname(output),{recursive:true});
  await (await SpreadsheetFile.exportXlsx(wb)).save(output);
  await fs.writeFile(output.replace(/\.xlsx$/i,'.delivery.json'),JSON.stringify(report,null,2));
  return report;
}
