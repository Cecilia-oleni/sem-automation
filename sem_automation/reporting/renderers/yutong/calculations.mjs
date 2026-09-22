// 内部宇通计算模块，由统一入口调用。
// 终端输入：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' reports yutong --config '.\config\reports\yutong\2026-08.json' --month 2026-08
export function countLeads(rows, filters, countries) {
  const headers=rows[0]??[];
  const indexes={region:headers.indexOf('经营大区'),country:headers.indexOf('国家或地区'),media:headers.indexOf('媒体名称')};
  if(Object.values(indexes).some(i=>i<0))throw new Error('线索表缺少经营大区、国家或媒体名称表头');
  const counts=Object.fromEntries(countries.map(name=>[name,0]));
  for(const row of rows.slice(1)) {
    const selected=filters.regions.includes(row[indexes.region]) && filters.countries.includes(row[indexes.country]) && Object.hasOwn(counts,row[indexes.country]) && (!filters.mediaMustBeBlank || row[indexes.media]===null || row[indexes.media]===undefined || row[indexes.media]==='');
    if(selected)counts[row[indexes.country]]++;
  }
  return counts;
}
