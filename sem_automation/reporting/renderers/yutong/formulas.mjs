// 模块：sem_automation/reporting/renderers/yutong/formulas.mjs；内部模块由统一入口调用。
// VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化'
// 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' reports yutong --config '.\config\reports\yutong\2026-08.json' --month 2026-08
// 该示例复用本地数据；详见 docs/月报操作说明.md。
export function normalizeFormulas(workbook, formulas) {
  const escape=s=>s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
  const names=Object.keys(formulas).sort((a,b)=>b.length-a.length);
  for(const [name,cells] of Object.entries(formulas)) {
    const sheet=workbook.worksheets.getItem(name);
    for(const [cell,original] of Object.entries(cells)) {
      let formula=original;
      for(const target of names)formula=formula.replace(new RegExp(`(?<![\\w'])${escape(target)}!`,'gu'),`'${target.replaceAll("'","''")}'!`);
      if(formula!==original)sheet.getRange(cell).formulas=[[formula]];
    }
  }
}
