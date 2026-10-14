import fs from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const base=new URL('./第一问结果/',import.meta.url);
const data=JSON.parse(await fs.readFile(new URL('q1_export.json',base),'utf8'));
const w=Workbook.create();
const s=w.worksheets.add('计划购电量');const b=w.worksheets.add('充放电量');
s.getRange('A1:B145').values=[['时间段','购电量'],...data.dispatch.map(r=>[`${r.interval_start}-${r.interval_end}`,r.purchase_kWh])];
b.getRange('A1:E7').values=[['时间段','充电量','放电量','时刻','储电量'],...data.blocks.map((r,i)=>[r.interval,r.charge_ac_kWh,r.discharge_ac_kWh,i<2?['0:00','24:00'][i]:null,i<2?6000:null])];
s.getRange('D1:E5').values=[['第一问核验结果','数值'],['全天购电量 / kWh',null],['全天购电费 / 元',data.verification.cost_yuan],['无储能费用 / 元',data.verification.no_battery_cost_yuan],['节费率',null]];
s.getRange('E2').formulas=[['=SUM(B2:B145)']];s.getRange('E5').formulas=[['=1-E3/E4']];s.getRange('E5').setNumberFormat('0.00%');
s.getRange('D7:E11').values=[['数据来源','用户提供附件1.xlsx、C题.pdf附录1'],['时间口径','原数据为区间结束时刻；显示修正为当天00:00–24:00'],['模板差异','原模板整体晚10分钟；本文件采用修正时间标签'],['效率口径','充电与放电效率各90%；交流侧充放电量'],['结果性质','上述假设下最优；官方勘误优先']];
for(const sheet of [s,b]){
 sheet.showGridLines=false;const r=sheet.getUsedRange();r.format.font={name:'Microsoft YaHei',size:11};r.format.rowHeight=24;
 sheet.getRange(sheet===s?'A1:B1':'A1:E1').format={fill:'#E8EDF2',font:{bold:true,color:'#203449'}};
 sheet.getRange('A1:A145').format.columnWidth=22;
 sheet.getRange('B1:C145').format.columnWidth=18;
 if(sheet===s){sheet.getRange('D1:D11').format.columnWidth=24;sheet.getRange('E1:E11').format.columnWidth=52;sheet.getRange('E7:E11').format.wrapText=true;sheet.getRange('D7:E11').format.rowHeight=38;sheet.getRange('B2:B145').setNumberFormat('#,##0.00');sheet.getRange('E2:E4').setNumberFormat('#,##0.00');sheet.freezePanes.freezeRows(1);}
 else{sheet.getRange('D1:E7').format.columnWidth=18;sheet.getRange('B2:C7').setNumberFormat('#,##0.00');sheet.getRange('E2:E3').setNumberFormat('#,##0.00');}
}
console.log((await w.inspect({kind:'table',range:'计划购电量!D1:E5',include:'values,formulas',tableMaxRows:5,tableMaxCols:2})).ndjson);
console.log((await w.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!',options:{useRegex:true,maxResults:20}})).ndjson);
for(const [sheet,range,file] of [['计划购电量','A1:E12','workbook_plan.png'],['充放电量','A1:E7','workbook_battery.png']]){
 const im=await w.render({sheetName:sheet,range,scale:1.5,format:'png'});await fs.writeFile(new URL(file,base),new Uint8Array(await im.arrayBuffer()));
}
const out=await SpreadsheetFile.exportXlsx(w);await out.save(fileURLToPath(new URL('result1.xlsx',base)));
