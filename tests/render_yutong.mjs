// 终端输入：node tests/render_yutong.mjs <运行目录>
import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const run=process.argv[2],out=path.join(run,'_internal/previews');
const config=JSON.parse(await fs.readFile(path.join(run,'_internal/resolved_config.json'),'utf8'));
const historyView=name=>{const block=config._histories.countryHistory[name][config.reportMonth];return [name,`A${block.start}:M${block.end}`];};
await fs.mkdir(out,{recursive:true});
for(const [folder,pattern,views] of [
  ['deliverables','monthly',[['Sheet1','A1:O16'],['Sheet1','A21:M34'],['Sheet1','A37:R54']]],
  ['history_candidates','country_history',[historyView('整理数值'),historyView('公式溯源')]],
  ['history_candidates','ytd_history',[['国家YTD汇总_数值','A1:J35'],['国家YTD汇总_公式','A1:J35'],['2026国家YTD_公式','A144:R160']]],
]) {
  const name=(await fs.readdir(path.join(run,folder))).find(n=>n.includes(pattern)&&n.endsWith('.xlsx'));
  const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(run,folder,name)));
  for(const [sheetName,range] of views) {
    const blob=await wb.render({sheetName,range,scale:1.4});
    await fs.writeFile(path.join(out,`${pattern}-${sheetName}-${range.replace(':','_')}.png`),new Uint8Array(await blob.arrayBuffer()));
  }
}
