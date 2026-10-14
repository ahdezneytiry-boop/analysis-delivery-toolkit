# -*- coding: utf-8 -*-
"""C题原始数据预处理及第一问独立求解。
依赖：numpy pandas openpyxl scipy matplotlib。
运行：python preprocess_and_q1.py
不会覆盖输入附件；严格检查失败时停止，不用虚构数值自动掩盖错误。
"""
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
if (HERE/'python_deps').exists(): sys.path.insert(0,str(HERE/'python_deps'))
import json, hashlib, datetime
import numpy as np
import pandas as pd
import openpyxl
from scipy.optimize import linprog, milp, Bounds, LinearConstraint
from scipy import sparse
from scipy.io import savemat
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ================= 学生必须检查/替换的本地路径 =================
INPUT_DATA_DIR = Path(r'C:/Users/ahdezneytiry-boop1/Desktop/附件')  # 原始附件1~4.xlsx所在文件夹
OUTPUT_DATA_DIR = HERE/'预处理数据'  # CSV、MAT、质量报告输出位置
OUTPUT_RESULT_DIR = HERE/'第一问结果'  # 求解结果与高分辨率图片输出位置
# ==============================================================
DT=1/6  # 小时，10分钟；功率kW乘此值后得到电量kWh
for p in [OUTPUT_DATA_DIR,OUTPUT_RESULT_DIR]:p.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei','DejaVu Sans'],
 'axes.unicode_minus':False,'figure.dpi':130,'savefig.dpi':300,
 'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,
 'grid.alpha':.18,'font.size':10})

def read_rows(file,sheet=0):
    w=openpyxl.load_workbook(INPUT_DATA_DIR/file,read_only=True,data_only=True)
    s=w.worksheets[sheet] if isinstance(sheet,int) else w[sheet]
    rows=list(s.values);w.close();return rows

def minute(v):
    """统一Excel时间、字符串时间和0:00+1；保留跨日含义。"""
    if isinstance(v,datetime.time):return v.hour*60+v.minute
    s=str(v).strip();add=1440 if '+1' in s else 0
    hh,mm,*_=s.replace('+1','').split(':')
    return int(hh)*60+int(mm)+add

def audit(a,name):
    """物理合法性检查+IQR统计标记。合法极值全部保留；不作削峰处理。"""
    a=np.asarray(a,float)
    missing=int(np.isnan(a).sum());nonfinite=int((~np.isfinite(a)).sum())
    if nonfinite:raise ValueError(f'{name}: 数值区存在{nonfinite}个非有限值，需核实原始数据后再运行')
    if (a<0).any():raise ValueError(f'{name}: 发现负值，需核实单位或数据来源，禁止自动置零')
    q1,q3=np.quantile(a,[.25,.75]);iqr=q3-q1
    flag=(a<q1-1.5*iqr)|(a>q3+1.5*iqr)
    return {'dataset':name,'count':a.size,'missing':missing,'min':float(a.min()),
      'max':float(a.max()),'iqr_flags_retained':int(flag.sum()),'modified_values':0}

def save_csv(df,name):
    p=OUTPUT_DATA_DIR/name;df.to_csv(p,index=False,encoding='utf-8-sig',float_format='%.10g')
    loaded=pd.read_csv(p);assert len(loaded)==len(df)
    return p

def preprocess():
    rows=read_rows('附件1.xlsx');a=np.asarray([r[1:4] for r in rows[1:]],float)
    minutes=np.array([minute(r[0]) for r in rows[1:]])
    assert np.array_equal(minutes,np.arange(10,1441,10)), '附件1时间不连续'
    labels=lambda ms:[f'{int(m)//60:02d}:{int(m)%60:02d}' for m in ms]
    q1=pd.DataFrame({'slot':np.arange(1,145),'source_time':[str(r[0]) for r in rows[1:]],
      'interval_start':labels(minutes-10),'interval_end':labels(minutes),
      'price_yuan_per_kWh':a[:,0],'load_kW':a[:,1],'pv_forecast_kW':a[:,2],
      'load_kWh':a[:,1]*DT,'pv_forecast_kWh':a[:,2]*DT,
      'net_load_kWh':(a[:,1]-a[:,2])*DT})
    checks=[audit(a[:,i],n) for i,n in enumerate(['q1_price','q1_load','q1_pv'])]
    arrays=[];dates=None
    for file,sheet,name in [('附件2.xlsx','小区负载','load'),('附件2.xlsx','光伏发电实际功率','pv'),('附件4.xlsx',0,'price')]:
        rr=read_rows(file,sheet);dd=pd.DatetimeIndex([r[0] for r in rr[1:]])
        assert dd.equals(pd.date_range('2025-01-01','2025-12-31'))
        assert np.array_equal([minute(v) for v in rr[0][1:]],minutes)
        b=np.array([r[1:] for r in rr[1:]],float);assert b.shape==(365,144)
        dates=dd;arrays.append(b);checks.append(audit(b,name))
    load,pv,price=arrays
    start=np.repeat(dates.values,144)+np.tile(np.arange(144)*np.timedelta64(10,'m'),365)
    actual=pd.DataFrame({'date':np.repeat(dates.strftime('%Y-%m-%d'),144),'slot':np.tile(np.arange(1,145),365),
      'interval_start':start,'interval_end':start+np.timedelta64(10,'m'),
      'load_kW':load.ravel(),'pv_actual_kW':pv.ravel(),'price_yuan_per_kWh':price.ravel(),
      'load_kWh':load.ravel()*DT,'pv_actual_kWh':pv.ravel()*DT,
      'net_load_kWh':(load-pv).ravel()*DT,
      'weekday':np.repeat(dates.dayofweek,144),'is_evaluation':np.repeat(dates.month>=2,144)})
    assert not actual.duplicated(['date','slot']).any()
    # 附件3的空日期是排版省略，只有此元数据允许前向填充，数值不填充。
    forecast=[];last_date=None;filled=0
    for row in read_rows('附件3.xlsx')[1:]:
        if row[0] not in (None,''): last_date=pd.Timestamp(row[0])
        else:filled+=1
        assert last_date is not None
        issue=last_date+pd.Timedelta(minutes=minute(row[1]))
        for lead,value in enumerate(row[2:26],1):
            forecast.append((issue,lead,issue+pd.Timedelta(hours=lead),value))
    forecast=pd.DataFrame(forecast,columns=['issue_time','lead_hours','valid_time','pv_forecast_kW'])
    assert len(forecast)==35040 and not forecast.duplicated(['issue_time','lead_hours']).any()
    assert forecast.groupby('issue_time').size().eq(24).all()
    checks.append(audit(forecast.pv_forecast_kW,'forecast'))
    # 不裁掉2026年的valid_time：年末发布的24小时预报合法跨年。
    quality=pd.DataFrame(checks)
    for df,name in [(q1,'q1_clean.csv'),(actual,'actual_10min.csv'),(forecast,'pv_forecast_hourly.csv'),(quality,'quality_report.csv')]:save_csv(df,name)
    savemat(OUTPUT_DATA_DIR/'clean_data.mat',{'q1_price':a[:,0],'q1_load_kW':a[:,1],
      'q1_pv_kW':a[:,2],'load_kW':load,'pv_actual_kW':pv,'price':price,
      'forecast_pv_kW':forecast.pv_forecast_kW.to_numpy().reshape(1460,24),
      'forecast_issue_unix_s':forecast.drop_duplicates('issue_time').issue_time.astype('int64').to_numpy()//10**9,
      'dt_hours':DT,'interval_end_minutes':minutes},do_compression=True)
    meta={'interval_convention':'原始时间按区间结束时刻解释，功率按前10分钟平均功率使用',
      'template_conflict':'模板标签整体晚10分钟；没有自动覆盖原模板',
      'date_metadata_forward_filled':filled,'evaluation_days':334,
      'data_numeric_imputation':0,'external_data_added':False,
      'sources':[{ 'file':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in INPUT_DATA_DIR.glob('*.xlsx')]}
    (OUTPUT_DATA_DIR/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    preview=[]
    for name,df in [('q1_clean',q1),('actual_10min',actual),('pv_forecast_hourly',forecast)]:
        preview += [f'## {name} 前10行',df.head(10).to_csv(index=False),f'## {name} 后5行',df.tail(5).to_csv(index=False)]
    (OUTPUT_DATA_DIR/'数据预览.md').write_text('\n\n'.join(preview),encoding='utf-8')
    fig,axs=plt.subplots(2,2,figsize=(12,7.5),layout='constrained')
    x=np.arange(144)/6
    axs[0,0].plot(x,a[:,1],label='原始负载',color='#246A90');axs[0,0].plot(x,a[:,2],label='原始光伏预测',color='#D99726')
    axs[0,0].set(title='处理前：附件1功率曲线',xlabel='时段开始 / h',ylabel='功率 / kW');axs[0,0].legend()
    axs[0,1].plot(x,q1.load_kWh,label='负载电量',color='#246A90');axs[0,1].plot(x,q1.pv_forecast_kWh,label='光伏电量',color='#D99726')
    axs[0,1].set(title='处理后：统一为10分钟电量',xlabel='时段开始 / h',ylabel='电量 / kWh');axs[0,1].legend()
    axs[1,0].boxplot([load.ravel(),pv.ravel()],tick_labels=['负载','光伏'],flierprops={'markersize':1,'alpha':.2})
    axs[1,0].set(title='全年功率分布：统计极值保留',ylabel='功率 / kW')
    im=axs[1,1].imshow((load-pv),aspect='auto',extent=[0,24,365,1],cmap='RdBu_r',vmin=-7000,vmax=7000)
    axs[1,1].set(title='处理后：全年净负载',xlabel='时刻 / h',ylabel='日序');fig.colorbar(im,ax=axs[1,1],label='kW')
    fig.savefig(OUTPUT_DATA_DIR/'preprocessing.png');plt.close(fig)
    print(quality.to_string(index=False));print('空日期还原',filled)
    return q1

def optimize(price,load,pv,eta=.9,cap=10800,pmax=5000,integer=False,lex=False):
    """变量q,c,d,w,E(1..144)，全用kWh；电网侧充/放电功率上限。"""
    n=144;m=5*n;A=sparse.lil_matrix((2*n+1,m));b=np.zeros(2*n+1)
    for t in range(n):
        A[t,t]=1;A[t,n+t]=-1;A[t,2*n+t]=1;A[t,3*n+t]=-1;b[t]=load[t]-pv[t]
        A[n+t,4*n+t]=1;A[n+t,n+t]=-eta;A[n+t,2*n+t]=1/eta
        if t:A[n+t,4*n+t-1]=-1
        else:b[n+t]=6000
    A[-1,-1]=1;b[-1]=6000;A=A.tocsr()
    lb=np.zeros(m);lb[4*n:]=1200
    ub=np.r_[np.full(n,np.inf),np.full(2*n,pmax*DT),pv,np.full(n,cap)]
    cost=np.r_[price,np.zeros(4*n)]
    base=linprog(cost,A_eq=A,b_eq=b,bounds=list(zip(lb,ub)),method='highs')
    if not base.success:raise RuntimeError(base.message)
    r=base
    if lex:
        turn=np.r_[np.zeros(n),np.ones(2*n),np.zeros(2*n)]
        r=linprog(turn,A_eq=A,b_eq=b,A_ub=cost.reshape(1,-1),b_ub=[base.fun+1e-7],bounds=list(zip(lb,ub)),method='highs')
        if not r.success:raise RuntimeError(r.message)
    if integer:
        # 加入144个0-1互斥变量作独立整数模型验证，而非依赖经验判断。
        AA=sparse.hstack([A,sparse.csr_matrix((A.shape[0],n))]).tocsr()
        B=sparse.lil_matrix((2*n,m+n))
        for t in range(n):
            B[t,n+t]=1;B[t,m+t]=-pmax*DT
            B[n+t,2*n+t]=1;B[n+t,m+t]=pmax*DT
        con=[LinearConstraint(AA,b,b),LinearConstraint(B.tocsr(),-np.inf,np.r_[np.zeros(n),np.full(n,pmax*DT)])]
        r=milp(np.r_[cost,np.zeros(n)],integrality=np.r_[np.zeros(m),np.ones(n)],
          bounds=Bounds(np.r_[lb,np.zeros(n)],np.r_[ub,np.ones(n)]),constraints=con,options={'mip_rel_gap':1e-9,'time_limit':60})
        if not r.success:raise RuntimeError(r.message)
    x=r.x[:m];eq=float(np.max(np.abs(A@x-b)))
    return x,base,{'cost_yuan':float(cost@x),'max_equality_residual_kWh':eq,
      'max_simultaneous_kWh':float(np.minimum(x[n:2*n],x[2*n:3*n]).max())}

def solve_q1(df):
    p=df.price_yuan_per_kWh.to_numpy();l=df.load_kWh.to_numpy();v=df.pv_forecast_kWh.to_numpy()
    x,base,check=optimize(p,l,v,lex=True);xm,_,mi=optimize(p,l,v,integer=True)
    q,c,d,w,e=x.reshape(5,144)
    # 原始LP的对偶下界：等式乘子与上下界乘子的贡献。
    # 使用求解器返回的边界残差验证之外，以相同LP的整数模型交叉核对。
    out=df.copy()
    for name,arr in [('purchase_kWh',q),('charge_ac_kWh',c),('discharge_ac_kWh',d),('curtailment_kWh',w),('soc_end_kWh',e),('cost_yuan',p*q),('marginal_load_yuan_per_kWh',base.eqlin.marginals[:144])]:out[name]=arr
    out.to_csv(OUTPUT_RESULT_DIR/'q1_dispatch.csv',index=False,encoding='utf-8-sig',float_format='%.10g')
    blocks=[]
    for k in range(6):blocks.append({'interval':f'{4*k:02d}:00-{4*(k+1):02d}:00','charge_ac_kWh':float(c[k*24:(k+1)*24].sum()),'discharge_ac_kWh':float(d[k*24:(k+1)*24].sum())})
    pd.DataFrame(blocks).to_csv(OUTPUT_RESULT_DIR/'q1_blocks.csv',index=False,encoding='utf-8-sig')
    no_battery=float(p@np.maximum(l-v,0))
    check.update({'lp_lower_bound_yuan':float(base.fun),'milp_optimum_yuan':mi['cost_yuan'],
      'certified_gap_yuan':check['cost_yuan']-float(base.fun),'purchase_kWh':float(q.sum()),
      'no_battery_cost_yuan':no_battery,'saving_percent':100*(1-check['cost_yuan']/no_battery),
      'soc_min_kWh':float(e.min()),'soc_max_kWh':float(e.max()),'soc_initial_kWh':6000,'soc_final_kWh':float(e[-1]),
      'max_charge_kW':float(c.max()/DT),'max_discharge_kW':float(d.max()/DT),
      'curtailment_kWh':float(w.sum()),'daily_energy_check_kWh':float(q.sum()+v.sum()-w.sum()-l.sum()-(1-.9)*c.sum()-(1/.9-1)*d.sum())})
    assert check['max_equality_residual_kWh']<1e-5 and check['max_simultaneous_kWh']<1e-5
    assert abs(check['cost_yuan']-mi['cost_yuan'])<1e-4
    # 针对真实口径疑点的必要敏感性，不随机反复调参。
    sensitivity=[]
    for label,eta,cap,pmax in [('基准',.9,10800,5000),('效率0.88',.88,10800,5000),('效率0.92',.92,10800,5000),('90%按往返解释',np.sqrt(.9),10800,5000),('容量上限+100',.9,10900,5000),('功率上限+100',.9,10800,5100)]:
        _,_,cc=optimize(p,l,v,eta=eta,cap=cap,pmax=pmax)
        sensitivity.append({'scenario':label,**cc})
    # 对照：将输入功率看作瞬时样本，周期补足00:00后梯形积分。
    lt=(np.r_[l[-1],l[:-1]]+l)/2;vt=(np.r_[v[-1],v[:-1]]+v)/2
    _,_,cc=optimize(p,lt,vt);sensitivity.append({'scenario':'瞬时功率梯形积分_电价仍按区间',**cc})
    pd.DataFrame(sensitivity).to_csv(OUTPUT_RESULT_DIR/'q1_sensitivity.csv',index=False,encoding='utf-8-sig')
    (OUTPUT_RESULT_DIR/'verification.json').write_text(json.dumps(check,ensure_ascii=False,indent=2),encoding='utf-8')
    data={'dispatch':out.to_dict('records'),'blocks':blocks,'verification':check}
    (OUTPUT_RESULT_DIR/'q1_export.json').write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    fig,axs=plt.subplots(3,1,figsize=(12,9),sharex=True,layout='constrained');t=np.arange(144)/6
    axs[0].plot(t,l/DT,label='负载',color='#246A90');axs[0].plot(t,v/DT,label='光伏',color='#D99726');axs[0].plot(t,q/DT,label='外网购电',color='#6A55A2',alpha=.85)
    axs[0].set(ylabel='功率 / kW',title='第一问：最小购电费用与可实施储能调度');axs[0].legend(ncol=3)
    axs[1].bar(t,c/DT,width=DT,label='充电',color='#2A9D8F');axs[1].bar(t,-d/DT,width=DT,label='放电',color='#E17C55');axs[1].set(ylabel='功率 / kW');axs[1].legend(ncol=2)
    axs[2].plot(np.arange(145)/6,np.r_[6000,e],color='#246A90',label='储电量');axs[2].axhline(1200,color='#888888',ls='--');axs[2].axhline(10800,color='#888888',ls='--');axs[2].set(ylabel='储电量 / kWh',xlabel='时刻 / h',xlim=(0,24),xticks=np.arange(0,25,2))
    ax=axs[2].twinx();ax.plot(t,p,color='#D99726',alpha=.55,label='电价');ax.set_ylabel('电价 / 元/kWh');ax.grid(False)
    fig.savefig(OUTPUT_RESULT_DIR/'q1_dispatch.png');plt.close(fig)
    print(json.dumps(check,ensure_ascii=False,indent=2));print(pd.DataFrame(blocks).to_string(index=False))

if __name__=='__main__':
    df=preprocess();solve_q1(df)
    print('预处理完成，数据输出路径：',OUTPUT_DATA_DIR)
    print('第一问完成，结果输出路径：',OUTPUT_RESULT_DIR)
