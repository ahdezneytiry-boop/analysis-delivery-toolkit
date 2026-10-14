"""生成可核验的独立交付包；不打包运行环境与临时文件。"""
import solve as m
import analyze as a
import json,shutil,hashlib,zipfile
from openpyxl import load_workbook

def package(q):
    folder=m.ROOT/f'问题{q}结果'
    src=load_workbook(m.INPUT/'附件5'/f'result{q}.xlsx',read_only=True).worksheets[0]
    old=list(next(src.values))[1:145]
    a.csvwrite(folder/'时段映射.csv',['零基索引','输入右端点','原模板表头','本次输出区间'],[[t,a.timepoint(t+1),old[t],a.interval(t,t+1)] for t in range(144)])
    dates,L,V,p,base,F=m.data()
    audit={'输入文件SHA256':{f:hashlib.sha256((m.INPUT/f).read_bytes()).hexdigest() for f in ['附件1.xlsx','附件2.xlsx','附件3.xlsx']},'负荷及光伏维度':list(L.shape),'预报维度':list(F.shape),'单位':'每段kWh；原始kW除以6','缺失或负值':'未发现，未填补或删除','异常处理':'保留真实高低波动，不以IQR机械删除','预测与实际分离':'历史切片严格在当前时刻以前；当前段实测只用于当前段执行'}
    (folder/'数据预处理说明.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
    code=folder/'代码';code.mkdir(exist_ok=True)
    for f in ['solve.py','analyze.py','test_model.py','export_results.mjs','fullrun.py','tune.py']:
        shutil.copy2(m.ROOT/f,code/f)
    shutil.copy2(m.OUT/'validation.json',folder/'参数验证.json')
    shutil.copy2(m.OUT/'单元验证.json',folder/'单元验证.json')
    shutil.copy2(m.OUT/f'q{q}_main.npz',folder/'原始计算记录.npz')
    (code/'requirements.txt').write_text('numpy>=2.0\nscipy>=1.14\nopenpyxl>=3.1\nmatplotlib>=3.9\n',encoding='utf8')
    s=10 if q==2 else 1;scale=.5 if q==2 else 1
    (code/'重新计算.py').write_text(f"import solve, analyze\nif __name__ == '__main__':\n    solve.run({q},S={s},terminal_scale={scale},name='q{q}_main')\n    analyze.report('q{q}_main',{q})\n",encoding='utf8')
    (folder/'README_结果与复现.md').write_text(f'''# 第{q}问独立结果
本包为实际执行代码所得结果，旧版结果不再使用。统计区间2025-02-01至12-31，1月用于因果初始化及参数验证。

## 文件
- result{q}.xlsx：题目要求的工作表；144段表头已按0:00至24:00规范，映射详见时段映射.csv。
- 逐时段审计数据.csv：未舍入的逐段电量、SOC、费用。
- 指定日期表1/2/3.csv：论文指定四天的结果。
- 验证报告.json：独立重算约束与费用；求解最优性日志.csv：每次优化的目标与最优界。
- 原始计算记录.npz：含1月初始化轨迹及发布版本；参数验证.json：仅用1月选择参数。

## 复现
1. Python 3.12或更新版本，在代码目录运行 `python -m pip install -r requirements.txt`。
2. **必须修改代码/solve.py的INPUT为自己的附件目录**，保留附件1/2/3.xlsx原名。
3. **输出路径**由代码/solve.py的ROOT和OUT控制，默认输出到代码/计算结果；审计CSV和图表输出到代码/问题{q}结果。
4. 运行 `python test_model.py`，再运行 `python 重新计算.py`。全年约5万次优化，需要数分钟至数十分钟。
5. CSV与图表由Python直接生成；Excel由export_results.mjs生成，需要Node.js及@oai/artifact-tool，并修改其input模板目录，运行 `node export_results.mjs {q}`。已交付的xlsx无需安装工具即可使用。
6. 核验记录应为334×144段，费用逐项重算相符，SOC范围1200至10800，充放电无重叠，跨日SOC连续。

## 口径
{'第二问计划费用按计划全额计费，再加5倍电价紧急购电费用。' if q==2 else '第三问主口径：原计划费用−0.5p下调量+1.5p上调量+5p紧急电量；另有正0.5p下调罚费口径的独立重算比较。题面存在解释空间，不能将主口径称为唯一答案。'}
库存终端价值只用于决策，不计入实际账单。年末设置SOC至少6000作为评价边界假设。各次模型最优不等于未知未来下策略全局最优。
''',encoding='utf8')
    wb=load_workbook(folder/f'result{q}.xlsx',data_only=True,read_only=True)
    dat=json.loads((folder/'结果数据.json').read_text(encoding='utf8'))
    for sheet,key in [('计划购电量','plan')]+([('调整购电量','adjust')] if q==3 else []):
        rows=list(wb[sheet].values)
        assert len(rows)==335 and len(rows[0])==147
        for row,expected in zip(rows[1:],dat[key]):
            assert max(abs(float(x)-float(y)) for x,y in zip(row[1:],expected[1:]))<1e-5
    (folder/'Excel核验.txt').write_text('通过：334天×144段；电量、日汇总及费用与未舍入计算结果逐项一致。',encoding='utf8')
    dest=m.ROOT/f'第{q}问结果交付包.zip'
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
        for f in folder.rglob('*'):
            if f.is_file() and not f.name.endswith('.inspect.ndjson') and '预览' not in f.name and f.name!='结果数据.json':z.write(f,f.relative_to(folder))
    print(dest, dest.stat().st_size)

if __name__=='__main__':
    import sys
    package(int(sys.argv[1]))
