// 终端输入：node --test tests/test_yutong_renderer.mjs
// 用内存工作表验证真实历史写入算法，无 API、无磁盘工作簿写入。
import test from 'node:test';
import assert from 'node:assert/strict';
import {writeHistories} from '../sem_automation/reporting/renderers/yutong/history_writer.mjs';
import {countLeads} from '../sem_automation/reporting/renderers/yutong/calculations.mjs';

const names=['俄罗斯','阿塞拜疆','亚美尼亚','摩尔多瓦','格鲁吉亚','白俄罗斯','哈萨克斯坦','乌兹别克斯坦','吉尔吉斯斯坦','塔吉克斯坦','土库曼斯坦'];
class Sheet {
  constructor(){this.writes=[];}
  getRange(range) {const writes=this.writes;return {set values(v){writes.push({range,values:v});},set formulas(v){writes.push({range,formulas:v});},copyFrom(){},setNumberFormat(){}};}
}
class Book {
  constructor(names){this.sheets=new Map(names.map(n=>[n,new Sheet()]));this.worksheets={getItem:n=>{assert.ok(this.sheets.has(n),n);return this.sheets.get(n);},add:n=>{assert.ok(!this.sheets.has(n),n);const s=new Sheet();this.sheets.set(n,s);return s;}};}
}
function fixture(month) {
  const [year,m]=month.split('-').map(Number),previous=m===1?`${year-1}-12`:`${year}-${String(m-1).padStart(2,'0')}`,yearAgo=`${year-1}-${String(m).padStart(2,'0')}`,ytd=Array.from({length:m},(_,i)=>`${year}-${String(i+1).padStart(2,'0')}`);
  const history={};let row=1510;
  for(const key of new Set([yearAgo,previous,...ytd])) {
    history[key]={start:row,end:row+13,total:row+13,row_numbers:Object.fromEntries(names.map((n,i)=>[n,row+2+i])),rows:Object.fromEntries(names.map(n=>[n,[n,100,10,1,7.3,2,0.5,0.1,0.73]]))};row+=17;
  }
  const sheetNames=['整理数值','原始数据','公式溯源'], ytdNames=['月度源数据','国家YTD汇总_数值','国家YTD汇总_公式','2026国家YTD_数值','2026国家YTD_公式'];
  const config={reportMonth:month,_periods:{previous,yearAgo,ytd},_histories:{countryHistory:Object.fromEntries(sheetNames.map(n=>[n,structuredClone(history)])),ytdHistory:{月度源数据:structuredClone(history)}},_books:{countryHistory:Object.fromEntries(sheetNames.map(n=>[n,Array(row).fill([])])),ytdHistory:Object.fromEntries(ytdNames.map(n=>[n,[]]))}};
  const records=names.map(label=>({label})), countryRow=r=>[r.label,100,10,1,7.3,2,0.5,0.1,0.73,0.1,0,0.1,0];
  return {config,countryHistoryBook:new Book(sheetNames),ytdBook:new Book(ytdNames),records,total:{label:'合计'},countryHeaders:['国家','展示合计','点击合计','消耗合计','消耗合计人民币','线索','CPA美元','CPC美元','CPC人民币','去年','同比','上月','环比'],countryRow,monthlyYtdRows:Array.from({length:18},(_,i)=>[i===2?'区域':null,...Array(17).fill(null)])};
}
for(const month of ['2026-09','2026-10','2027-01'])test(`${month}: dynamic rows, monthly YTD and repeat update`,()=>{
  const f=fixture(month),index=f.config._histories.countryHistory['整理数值'],before=index[month].start;
  writeHistories(f);assert.equal(index[month].start,before);
  const formulaSheet=f.ytdBook.sheets.get(`${month.slice(0,4)}国家YTD_公式`);
  assert.ok(formulaSheet);
  const ytdFormula=formulaSheet.writes.find(w=>w.range.startsWith('C3:'))?.formulas?.[0][3];
  assert.equal((ytdFormula.match(/月度源数据/g)||[]).length,Number(month.slice(5)));
  assert.ok(!ytdFormula.includes('国家YTD汇总'), 'snapshot must not depend on mutable latest summary');
  writeHistories(f);assert.equal(index[month].start,before);
});
test('new month appends after all actual data, not a fixed row',()=>{
  const f=fixture('2026-09');
  for(const index of Object.values(f.config._histories.countryHistory))delete index['2026-09'];
  delete f.config._histories.ytdHistory['月度源数据']['2026-09'];
  writeHistories(f);
  assert.ok(f.config._histories.countryHistory['整理数值']['2026-09'].start>1500);
});
test('lead data growing beyond old 1049-row limit is counted',()=>{
  const rows=[['经营大区','国家或地区','媒体名称'],...Array.from({length:2000},()=>['中亚','哈萨克斯坦','']),['中亚','哈萨克斯坦','Google'],['其他区','哈萨克斯坦','']];
  assert.deepEqual(countLeads(rows,{regions:['中亚'],countries:['哈萨克斯坦'],mediaMustBeBlank:true},['哈萨克斯坦']),{'哈萨克斯坦':2000});
  assert.throws(()=>countLeads([['错误表头']],{},[]),/缺少/);
});
