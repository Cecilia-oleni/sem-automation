// 模块：sem_automation/reporting/renderers/yutong/history_writer.mjs；内部模块由统一入口调用。
// VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化'
// 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' reports yutong --config '.\config\reports\yutong\2026-08.json' --month 2026-08
// 该示例复用本地数据；详见 docs/月报操作说明.md。
export function writeHistories({config,countryHistoryBook,ytdBook,records,total,countryHeaders,countryRow,monthlyYtdRows}) {
  const month=config.reportMonth, periods=config._periods, year=month.slice(0,4);
  const indexes=config._histories, books=config._books;
  const block=[[month,...Array(12).fill(null)],countryHeaders,...records.map(r=>countryRow(r)),['合计',...countryRow(total).slice(1)]];
  function upsert(book,key,name) {
    const sheet=book.worksheets.getItem(name), idx=indexes[key][name];
    for(const [key,entry] of Object.entries(idx)) {
      sheet.getRange(`A${entry.start}`).values=[[key]];
      sheet.getRange(`A${entry.start}`).setNumberFormat('@');
    }
    const old=idx[month], start=old?.start ?? books[key][name].length+4;
    if(old && old.end-old.start+1!==block.length)throw new Error(`${name}: ${month} 块长度不符`);
    const style=idx[periods.previous];
    if(!old)sheet.getRange(`A${start}:M${start+13}`).copyFrom(sheet.getRange(`A${style.start}:M${style.start+13}`),'all');
    sheet.getRange(`A${start}:M${start+13}`).values=block;
    sheet.getRange(`A${start+1}:M${start+1}`).format={wrapText:true,rowHeight:44};
    sheet.getRange(`A${start+6}`).format={wrapText:true,rowHeight:48};
    sheet.getRange(`A${start}`).setNumberFormat('@');
    const rows=Object.fromEntries(records.map((r,i)=>[r.label,start+2+i]));
    idx[month]={start,end:start+13,total:start+13,row_numbers:rows,rows:Object.fromEntries(records.map(r=>[r.label,countryRow(r)]))};
    return {sheet,start,idx};
  }
  const raw=upsert(countryHistoryBook,'countryHistory','原始数据');
  upsert(countryHistoryBook,'countryHistory','整理数值');
  const formulas=upsert(countryHistoryBook,'countryHistory','公式溯源');
  const fidx=formulas.idx, start=formulas.start;
  for(const [i,r] of records.entries()) {
    const target=start+2+i, source=raw.idx[month].row_numbers[r.label], py=fidx[periods.yearAgo].row_numbers[r.label], pm=fidx[periods.previous].row_numbers[r.label];
    formulas.sheet.getRange(`A${target}:M${target}`).formulas=[[
      ...['A','B','C','D','E','F'].map(c=>`='原始数据'!${c}${source}`),
      `=IFERROR(D${target}/F${target},"/")`,`=IFERROR(D${target}/C${target},"/")`,`=IFERROR(E${target}/C${target},"/")`,
      `=H${py}`,`=IFERROR(H${target}/J${target}-1,"/")`,`=H${pm}`,`=IFERROR(H${target}/L${target}-1,"/")`
    ]];
  }
  const end=start+13;
  formulas.sheet.getRange(`B${end}:M${end}`).formulas=[[
    ...['B','C','D','E','F'].map(c=>`=SUM(${c}${start+2}:${c}${end-1})`),
    `=IFERROR(D${end}/F${end},"/")`,`=IFERROR(D${end}/C${end},"/")`,`=IFERROR(E${end}/C${end},"/")`,
    `=H${fidx[periods.yearAgo].total}`,`=IFERROR(H${end}/J${end}-1,"/")`,`=H${fidx[periods.previous].total}`,`=IFERROR(H${end}/L${end}-1,"/")`
  ]];
  const monthly=upsert(ytdBook,'ytdHistory','月度源数据'), mi=monthly.idx;
  const leadRows=[5,6,7,8,9,10,12,13,14,15,16], spendRows=[23,24,25,26,27,28,30,31,32,33,34];
  const months=[...periods.ytd].reverse();
  const col=n=>String.fromCharCode(65+n);
  for(const mode of ['数值','公式']) {
    const sheet=ytdBook.worksheets.getItem(`国家YTD汇总_${mode}`);
    sheet.getRange('B4:N35').values=Array.from({length:32},()=>Array(13).fill(null));
    sheet.getRange('A1').values=[[`YTD=${year}-01 至 ${month}`]];
    for(const row of [4,22]) {
      sheet.getRange(`A${row}`).values=[[`${year}年`]];
      sheet.getRange(`B${row}`).values=[['YTD总计']];
      sheet.getRange(`C${row}:${col(months.length+1)}${row}`).values=[months];
      sheet.getRange(`C${row}:${col(months.length+1)}${row}`).setNumberFormat('@');
    }
    for(const [i,r] of records.entries()) for(const [row,sourceCol,index] of [[leadRows[i],'F',5],[spendRows[i],'E',4]]) {
      for(const [j,m] of months.entries()) {
        const cell=sheet.getRange(`${col(j+2)}${row}`), source=mi[m].row_numbers[r.label];
        if(mode==='公式')cell.formulas=[[`='月度源数据'!${sourceCol}${source}`]];
        else cell.values=[[mi[m].rows[r.label][index]]];
      }
      sheet.getRange(`B${row}`).formulas=[[`=SUM(C${row}:${col(months.length+1)}${row})`]];
    }
    for(const [row,members] of [[17,leadRows],[35,spendRows]])for(let j=1;j<months.length+2;j++)sheet.getRange(`${col(j)}${row}`).formulas=[[`=SUM(${members.map(r=>`${col(j)}${r}`).join(',')})`]];
  }
  // Each year's snapshots are independent, and every snapshot sums source months.
  const snapshot=[[month,...Array(17).fill(null)],monthlyYtdRows[2],...monthlyYtdRows.slice(3,18)];
  for(const mode of ['数值','公式']) {
    const name=`${year}国家YTD_${mode}`;
    const oldRows=books.ytdHistory[name]??[];
    const matches=[];
    for(const [i,row] of oldRows.entries()) {
      const m=String(row[0]??'').match(/^(20\d{2})[.-](\d{1,2})$/);
      if(m && `${m[1]}-${m[2].padStart(2,'0')}`===month && oldRows[i+1]?.[0]==='区域')matches.push(i+1);
    }
    if(matches.length>1)throw new Error(`${name}: 重复月份 ${month}`);
    let sheet;
    if(books.ytdHistory[name])sheet=ytdBook.worksheets.getItem(name);
    else {
      sheet=ytdBook.worksheets.add(name);
      const prototype=Object.keys(books.ytdHistory).find(n=>n.endsWith(`国家YTD_${mode}`));
      if(prototype)sheet.getRange('A1:R17').copyFrom(ytdBook.worksheets.getItem(prototype).getRange('A4:R20'),'all');
    }
    const row=matches[0]??(oldRows.length?oldRows.length+4:1), totalRow=row+14;
    if(!matches.length && oldRows.length>=20)sheet.getRange(`A${row}:R${row+16}`).copyFrom(sheet.getRange('A4:R20'),'all');
    sheet.getRange(`A${row}:R${row+16}`).values=snapshot;
    sheet.getRange(`A${row+1}:R${row+1}`).format={wrapText:true,rowHeight:54};
    sheet.getRange(`A${row}`).setNumberFormat('@');
    while(oldRows.length<row+16)oldRows.push([]);
    for(const [offset,values] of snapshot.entries())oldRows[row-1+offset]=values;
    books.ytdHistory[name]=oldRows;
    if(mode==='公式') {
      const targets=records.map((_,i)=>row+2+i+(i>=6?1:0));
      for(const [i,r] of records.entries()) {
        const target=targets[i],source=mi[month].row_numbers[r.label],py=mi[periods.yearAgo].row_numbers[r.label],pm=mi[periods.previous].row_numbers[r.label];
        const sumSources=c=>`=SUM(${periods.ytd.map(m=>`'月度源数据'!${c}${mi[m].row_numbers[r.label]}`).join(',')})`;
        sheet.getRange(`C${target}:R${target}`).formulas=[[
          `='月度源数据'!B${source}`,`='月度源数据'!C${source}`,`='月度源数据'!E${source}`,sumSources('E'),`='月度源数据'!F${source}`,sumSources('F'),
          `=IFERROR(G${target}/N${target}-1,"/")`,`=IFERROR(G${target}/M${target}-1,"/")`,`=IFERROR(E${target}/G${target},"/")`,`=IFERROR(E${target}/$E$${totalRow},"/")`,
          `='月度源数据'!F${py}`,`='月度源数据'!F${pm}`,`=IFERROR('月度源数据'!E${py}/M${target},"/")`,`=IFERROR(K${target}/O${target}-1,"/")`,`=IFERROR('月度源数据'!E${pm}/N${target},"/")`,`=IFERROR(K${target}/Q${target}-1,"/")`
        ]];
      }
      for(const [target,members] of [[row+8,targets.slice(0,6)],[totalRow,targets]]) {
        for(const c of ['C','D','E','F','G','H','M','N'])sheet.getRange(`${c}${target}`).formulas=[[`=SUM(${members.map(r=>`${c}${r}`).join(',')})`]];
        sheet.getRange(`I${target}:L${target}`).formulas=[[`=IFERROR(G${target}/N${target}-1,"/")`,`=IFERROR(G${target}/M${target}-1,"/")`,`=IFERROR(E${target}/G${target},"/")`,`=IFERROR(E${target}/$E$${totalRow},"/")`]];
        const selected=members.map(t=>records[targets.indexOf(t)].label);
        for(const [c,m,den] of [['O',periods.yearAgo,'M'],['Q',periods.previous,'N']])sheet.getRange(`${c}${target}`).formulas=[[`=IFERROR(SUM(${selected.map(n=>`'月度源数据'!E${mi[m].row_numbers[n]}`).join(',')})/${den}${target},"/")`]];
        sheet.getRange(`P${target}`).formulas=[[`=IFERROR(K${target}/O${target}-1,"/")`]];sheet.getRange(`R${target}`).formulas=[[`=IFERROR(K${target}/Q${target}-1,"/")`]];
      }
    }
  }
}
