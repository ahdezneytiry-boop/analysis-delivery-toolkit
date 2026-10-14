"""核验已导出的Excel后打包；不包含机器依赖环境。"""
import solve as m,analyze as a
from pathlib import Path
from openpyxl import load_workbook
import json,zipfile,shutil,hashlib
def main():
    f=m.ROOT/'问题3结果';sel=json.loads((m.OUT/'selection.json').read_text());alpha=sel['selected_alpha'];raw=json.loads((f/'结果数据.json').read_text(encoding='utf8'))
    w=load_workbook(f/'result3.xlsx',data_only=True,read_only=True)
    for sheet,key in [('计划购电量','plan'),('调整购电量','adjust')]:
        rows=list(w[sheet].values);assert len(rows)==335 and len(rows[0])==147
        for r,e in zip(rows[1:],raw[key]):assert max(abs(float(x)-float(y)) for x,y in zip(r[1:],e[1:]))<1e-5
    (f/'Excel核验.txt').write_text('通过：334天144段电量及日汇总与原始计算结果逐值一致。',encoding='utf8')
    original=load_workbook(m.INPUT/'附件5'/'result3.xlsx',read_only=True).worksheets[0];old=list(next(original.values))[1:145]
    a.csvwrite(f/'时段映射.csv',['t','原模板时间','规范区间'],[[t,old[t],a.interval(t,t+1)] for t in range(144)])
    code=f/'代码';code.mkdir(exist_ok=True)
    for name in ['solve.py','analyze.py','test_model.py','revise.py','summarize.py','export_results.mjs']:shutil.copy2(m.ROOT/name,code/name)
    (code/'重新计算主结果.py').write_text(f"import solve,analyze\nif __name__=='__main__':\n    solve.run(3,S=1,alpha={alpha},name='q3_main')\n    analyze.report('q3_main',3)\n",encoding='utf8')
    (code/'requirements.txt').write_text('numpy>=2.0\nscipy>=1.14\nopenpyxl>=3.1\nmatplotlib>=3.9\n',encoding='utf8')
    (code/'全量重算敏感性.py').write_text("from concurrent.futures import ProcessPoolExecutor\nimport solve,revise,json\ndef job(alpha):\n    solve.run(3,S=1,alpha=alpha,name=f'a{alpha:.2f}_all')\nif __name__=='__main__':\n    with ProcessPoolExecutor(max_workers=3) as pool:list(pool.map(job,revise.ALPHAS))\n    revise.main()\n    import summarize\n    summarize.main()\n",encoding='utf8')
    # revise的缓存复用只影响速度；完全重算已有全部alpha后不会读取旧压缩包。
    provenance={'source_zip_sha256':hashlib.sha256(Path(__import__('revise').ARCHIVE).read_bytes()).hexdigest(),'cache':'原五系数前364天保持旧规则；末日重新求解','new_full_runs':[.51,.52,.55,.60,.65],'source_inputs':{x:hashlib.sha256((m.INPUT/x).read_bytes()).hexdigest() for x in ['附件1.xlsx','附件2.xlsx','附件3.xlsx']}}
    (f/'来源与复用说明.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf8')
    shutil.copy2(m.OUT/'单元验证.json',f/'单元验证.json')
    (f/'README.md').write_text(f'''# 第三问终端修订结果
主结果alpha={alpha}，S=1。lambda=alpha×median(p)，旧terminal_scale=alpha/0.9。12月31日lambda=0，期末SOC至少6000，现金账单不含库存估值。

## 输出
result3.xlsx为主结果；逐时段审计数据.csv与逐日费用与储能.csv保留未舍入数值；四个指定日期结果见表1至表3 CSV。
终端系数敏感性.csv包含全部10个候选；逐日敏感性.csv提供各候选334天的费用、日末SOC、满电比例、弃光与未利用购电。
信息价值.json比较同一alpha下仅0时与全部预报。不能直接将它等同于第二问对第三问。
计算记录内NPZ保存全部轨迹和求解日志；验证报告和全部轨迹核验.json提供独立检查。

## 本地复现
1. 安装Python依赖：`python -m pip install -r 代码/requirements.txt`。
2. **修改代码/solve.py中的INPUT为自己的附件目录**。
3. 在代码目录运行`python test_model.py`，然后`python 重新计算主结果.py`。**输出位于代码/计算结果以及代码/问题3结果**。
4. 全部候选重跑可运行`python 全量重算敏感性.py`，需要较长计算时间。若需仅0时策略，运行`solve.run(3,S=1,alpha={alpha},updates=(),name='a{alpha:.2f}_none')`。
5. Excel导出需要Node.js和@oai/artifact-tool，修改export_results.mjs中input模板目录，运行`node export_results.mjs 3`。现成Excel直接打开即可。

## 解释边界
固定S比较；参数按1月15—31日费用选择，2—12月费用不参与排序。但新增候选来自对既有全年结果的复查，属于事后修订，不能宣称完全独立样本外验证。
本次固定退款结算：pq0−0.5p下调+1.5p上调+5p紧急。未重算另一计费解释。
日末SOC均值与全部时段SOC均值分开；满电比例按时段末SOC≥10799.999统计。弃光和未利用计划电分配采用固定核算顺序，并非唯一物理来源分解。
模板表头修正为每日00:00—24:00，详见映射CSV。期末库存下界属于明确评价假设，非题面明示。
''',encoding='utf8')
    out=m.ROOT/'第3问结果交付包_终端修订版.zip'
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for p in f.rglob('*'):
            if p.is_file() and not p.name.endswith('.inspect.ndjson') and '预览' not in p.name and p.name!='结果数据.json':z.write(p,p.relative_to(f))
        for p in m.OUT.glob('a*.npz'):z.write(p,'计算记录/'+p.name)
    print(out,out.stat().st_size)
if __name__=='__main__':main()
