// 模块：sem_automation/reporting/renderers/standard/report_chart_images.mjs；内部模块由统一入口调用。
// VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化 - 副本'
// 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' reports standard --client '.\config\clients\lingyu.json' --month 2026-07 --source existing --data-dir '.\outputs\_archive\lingyu\2026-07'
// 该示例复用本地数据；详见 docs/月报操作说明.md。
import sharp from 'sharp';

const esc = value => String(value ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
const isNumber = value => typeof value === 'number' && Number.isFinite(value);
const ink='#242B38', muted='#7B89A6', grid='#E1E6EF';
const text=(x,y,value,size=13,color=ink,extra='')=>`<text x="${x}" y="${y}" font-size="${size}" fill="${color}" ${extra}>${esc(value)}</text>`;
const document=(w,h,body)=>`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><rect width="100%" height="100%" fill="white"/><g font-family="Arial, Microsoft YaHei, sans-serif">${body}</g></svg>`;
const pretty=v=>Number.isInteger(v)?String(v):v.toFixed(v<1?2:1).replace(/0+$/,'').replace(/\.$/,'');
const niceMax=value=>{if(!value)return 1;const base=10**Math.floor(Math.log10(value));return Math.ceil(value/base/0.5)*base*0.5;};

export function trendSvg({width=1400,height=260,dates,series,type='line',independent=false,dual=false,legend=true}) {
  const left=dual?48:independent?18:45,right=dual?48:18,top=15,bottom=legend?62:36;
  const pw=width-left-right,ph=height-top-bottom,n=dates.length;
  const maximum = group => niceMax(Math.max(0,...series.filter(s=>!dual||(s.axis??'count')===group).flatMap(s=>s.values.filter(isNumber))));
  const commonMax=maximum('count'),rateMax=maximum('rate');
  const maxFor=s=>independent?niceMax(Math.max(0,...s.values.filter(isNumber))):dual&&s.axis==='rate'?rateMax:commonMax;
  const x=i=>left+(type==='bar'?(i+0.5)*pw/Math.max(1,n):n<2?pw/2:i*pw/(n-1));
  const y=(v,s)=>top+ph*(1-v/maxFor(s));
  let body='';
  // 周末底色与 Metrika 一致，仅由日期决定，不改变数据。
  dates.forEach((date,i)=>{if([0,6].includes(new Date(`${date}T00:00:00Z`).getUTCDay())){
    const step=type==='bar'?pw/Math.max(1,n):pw/Math.max(1,n-1);
    const a=Math.max(left,x(i)-step/2),b=Math.min(width-right,x(i)+step/2);
    body+=`<rect x="${a}" y="${top}" width="${b-a}" height="${ph}" fill="#F3F5F9"/>`;
  }});
  for(let t=0;t<=2;t++){
    const yy=top+ph*t/2;
    body+=`<path d="M${left} ${yy}H${width-right}" stroke="${grid}"/>`;
    if(!independent)body+=text(left-8,yy+4,pretty((dual?rateMax:commonMax)*(1-t/2))+(dual?'%':''),11,muted,'text-anchor="end"');
    if(dual)body+=text(width-right+8,yy+4,pretty(commonMax*(1-t/2)),11,muted);
  }
  const indexes=[...new Set([0,...dates.map((_,i)=>i).filter(i=>i%Math.max(1,Math.ceil((n-1)/6))===0),n-1])].filter(i=>i>=0);
  indexes.forEach(i=>body+=text(x(i),top+ph+24,dates[i]?.slice(8,10)+'.'+dates[i]?.slice(5,7),11,muted,`text-anchor="${i===0?'start':i===n-1?'end':'middle'}"`));
  series.forEach((s,k)=>{
    if(type==='bar'){
      const bw=pw/Math.max(1,n)*0.78/series.length;
      s.values.forEach((v,i)=>{if(isNumber(v))body+=`<rect x="${x(i)-bw*series.length/2+k*bw}" y="${y(v,s)}" width="${Math.max(1,bw-1)}" height="${ph*v/maxFor(s)}" rx="1.2" fill="${s.color}"/>`;});
    }else{
      let segment=[];
      const flush=()=>{if(segment.length===1)body+=`<circle cx="${segment[0][0]}" cy="${segment[0][1]}" r="2" fill="${s.color}"/>`;
        if(segment.length>1)body+=`<polyline points="${segment.map(p=>p.join(',')).join(' ')}" fill="none" stroke="${s.color}" stroke-width="1.8" stroke-linejoin="round"/>`;segment=[];};
      s.values.forEach((v,i)=>{if(isNumber(v))segment.push([x(i),y(v,s)]);else flush();});flush();
    }
  });
  if(legend){let xx=left;series.forEach(s=>{body+=`<rect x="${xx}" y="${height-18}" width="10" height="10" rx="3" fill="${s.color}"/>`+text(xx+17,height-9,s.label+(s.total!==undefined?'  '+s.total:''),12);xx+=Math.max(145,s.label.length*7+80);});}
  return document(width,height,body);
}

export function distributionSvg({width=1400,height=260,title,metric='Sessions',rows,colors,type='doughnut',note=''}) {
  const total=rows.reduce((s,r)=>s+r.value,0);
  let body=text(18,31,title,21)+text(18,56,metric,13,muted);
  if(!total)return document(width,height,body+text(18,110,'No data',15,muted));
  if(!['pie','doughnut'].includes(type)){
    // 非圆环模式仍使用真实分类值。
    // 分类轴另绘，不将分类伪装成日期。
    const x0=220,y0=35,h=150,w=width-260,max=Math.max(...rows.map(r=>r.value));
    if(type==='bar')rows.forEach((r,i)=>{const y=y0+i*h/rows.length;body+=text(x0-12,y+12,r.label,12,ink,'text-anchor="end"')+`<rect x="${x0}" y="${y}" width="${w*r.value/max}" height="${Math.min(20,h/rows.length-4)}" fill="${colors[i%colors.length]}"/>`;});
    else {const points=rows.map((r,i)=>[x0+(i+0.5)*w/rows.length,y0+h*(1-r.value/max)]);body+=`<polyline points="${points.map(p=>p.join(',')).join(' ')}" stroke="${colors[0]}" stroke-width="2" fill="none"/>`;rows.forEach((r,i)=>body+=text(points[i][0],y0+h+22,r.label,11,muted,'text-anchor="middle"'));}
  }else{
    const cx=width*0.79,cy=118,rad=76,inner=type==='pie'?0:34;
    let angle=-Math.PI/2;
    rows.forEach((r,i)=>{
      const end=angle+r.value/total*Math.PI*2;
      if(r.value===total)body+=`<circle cx="${cx}" cy="${cy}" r="${rad}" fill="${colors[i%colors.length]}"/>`;
      else if(r.value>0){const p=a=>[cx+rad*Math.cos(a),cy+rad*Math.sin(a)];const [x1,y1]=p(angle),[x2,y2]=p(end);
        body+=`<path d="M${cx} ${cy}L${x1} ${y1}A${rad} ${rad} 0 ${end-angle>Math.PI?1:0} 1 ${x2} ${y2}Z" fill="${colors[i%colors.length]}"/>`;}
      angle=end;
    });
    if(inner)body+=`<circle cx="${cx}" cy="${cy}" r="${inner}" fill="white"/>`+text(cx,cy-1,total,15,ink,'text-anchor="middle"')+text(cx,cy+17,'100%',11,muted,'text-anchor="middle"');
  }
  let xx=18,yy=height-(note?43:22);
  rows.forEach((r,i)=>{const label=`${r.label}  ${(r.value/total*100).toFixed(2)}%`;const span=label.length*7+35;if(xx+span>width-20){xx=18;yy+=22;}
    body+=`<circle cx="${xx+5}" cy="${yy-5}" r="5" fill="${colors[i%colors.length]}"/>`+text(xx+17,yy,label,13);xx+=span;});
  if(note)body+=text(18,height-5,note,11,muted);
  return document(width,height,body);
}

export async function pngFromSvg(svg) {
  // 两倍分辨率，在 Excel 中按逻辑尺寸显示，缩放后仍清晰。
  return sharp(Buffer.from(svg),{density:144}).png().toBuffer();
}
