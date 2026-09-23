// 终端输入：python sem.py materials wordstat prepare --project '通亚'
// 内部 Excel 渲染器，由 Python 传入结构化数据。
import fs from 'node:fs/promises';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';
const [input, output, preview] = process.argv.slice(2);
const {fields, rows} = JSON.parse(await fs.readFile(input, 'utf8'));
const wb = Workbook.create();
const sheet = wb.worksheets.add('关键词审核');
const end = String.fromCharCode(64 + fields.length);
const n = rows.length + 1;
const range = sheet.getRange(`A1:${end}${n}`);
range.setNumberFormat('@');
range.values = [fields, ...rows.map(r => fields.map(f => {
  const v = r[f] ?? '';
  return typeof v === 'string' && v.startsWith('=') ? "'" + v : v;
}))];
range.format = {font:{name:'Arial',size:11,color:'#172B4D'}, rowHeight:30, wrapText:true, verticalAlignment:'center'};
fields.forEach((f,i) => {
  const col = String.fromCharCode(65+i);
  sheet.getRange(`${col}1:${col}${n}`).format.columnWidth = f === 'volume' ? 14 : f === 'keywords' ? 58 : 32;
  if(f === 'volume' && n > 1) sheet.getRange(`${col}2:${col}${n}`).setNumberFormat('#,##0');
});
const table = sheet.tables.add(`A1:${end}${n}`, true, 'KeywordsTable');
table.showFilterButton = true;
sheet.getRange(`A1:${end}1`).format = {fill:'#264564',font:{bold:true,color:'#FFFFFF'},rowHeight:32};
sheet.freezePanes.freezeRows(1);
sheet.showGridLines = false;
wb.recalculate();
if(preview) {
  const blob = await wb.render({sheetName:sheet.name,range:`A1:${end}${Math.min(n,12)}`,scale:1.5});
  await fs.writeFile(preview,new Uint8Array(await blob.arrayBuffer()));
}
const file = await SpreadsheetFile.exportXlsx(wb);
await file.save(output + '.tmp');
await fs.rename(output + '.tmp', output);
