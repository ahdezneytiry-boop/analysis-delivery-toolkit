"""与求解器独立重算全部约束、结算、统计比较和论文图表。"""
import solve as m
import numpy as np,json,csv,hashlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.sans-serif':['Microsoft YaHei','SimHei'],'axes.unicode_minus':False,'figure.dpi':130,'savefig.dpi':300,'axes.spines.top':False,'axes.spines.right':False})
HEADER=['day_index','slot','load_kWh','pv_kWh','price_CNY_kWh','q0_kWh','a_kWh','charge_kWh','discharge_kWh','emergency_kWh','pv_curtail_kWh','unused_grid_kWh','SOC_start_kWh','SOC_end_kWh','down_kWh','up_kWh','plan_cost_CNY','adjust_cost_CNY','emergency_cost_CNY']
SPEC=['2025-03-20','2025-06-21','2025-09-23','2025-12-21']

def csvwrite(path,header,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(header);w.writerows(rows)

def timepoint(t):return '24:00' if t==144 else f'{t//6:02d}:{t%6*10:02d}'
def interval(a,b):return timepoint(a)+'-'+timepoint(b)

def report(name,q,fee=-.5):
    z=np.load(m.OUT/(name+'.npz'));rr=z['records'];r=rr[31:].reshape(-1,19);dates=z['dates'][31:];daily=z['daily'][31:];solves=z['solves']
    assert len(dates)==334 and dates[0]=='2025-02-01' and dates[-1]=='2025-12-31'
    eq=r[:,6]+r[:,3]-r[:,10]-r[:,11]+r[:,8]+r[:,9]-r[:,2]-r[:,7]
    soc=r[:,13]-r[:,12]-.9*r[:,7]+r[:,8]/.9
    target_cost=r[:,4]*(r[:,5]+fee*np.maximum(r[:,5]-r[:,6],0)+1.5*np.maximum(r[:,6]-r[:,5],0)+5*r[:,9])
    if q==2:target_cost=r[:,4]*(r[:,5]+5*r[:,9])
    checks={'energy_balance_max':float(abs(eq).max()),'soc_recursion_max':float(abs(soc).max()),'charge_discharge_overlap':float(np.minimum(r[:,7],r[:,8]).max()),'soc_min':float(r[:,12:14].min()),'soc_max':float(r[:,12:14].max()),'pv_curtail_upper_violation':float(np.maximum(r[:,10]-r[:,3],0).max()),'unused_grid_upper_violation':float(np.maximum(r[:,11]-r[:,6],0).max()),'cost_reconciliation_max':float(abs(target_cost-r[:,16:19].sum(1)).max()),'power_upper_violation':float(np.maximum(r[:,7:9]-m.M,0).max()),'continuity_max':float(abs(rr.reshape(-1,19)[1:,12]-rr.reshape(-1,19)[:-1,13]).max()),'lp_or_mip_solves':len(solves),'mip_solves':int(solves[:,5].sum()),'absolute_optimality_gap_max_CNY':float(solves[:,4].max()),'year_end_SOC':float(r[-1,13]),'feb_start_SOC':float(r[0,12])}
    for key in ['energy_balance_max','soc_recursion_max','charge_discharge_overlap','pv_curtail_upper_violation','unused_grid_upper_violation','cost_reconciliation_max','power_upper_violation','continuity_max']:assert checks[key]<1e-5,(key,checks[key])
    assert checks['soc_min']>=1200-1e-6 and checks['soc_max']<=10800+1e-6 and checks['year_end_SOC']>=6000-1e-6
    if 'versions' in z:
        vv=z['versions'][31:]
        for d,day in enumerate(rr[31:]):
            cur=day[:,5].copy()
            for h in [0,36,72,108]:
                if np.isfinite(vv[d,h//36,h]):cur[h:]=vv[d,h//36,h:]
                assert np.allclose(cur[h:h+36],day[h:h+36,6],atol=1e-5)
        checks['version_splice']='passed'
    totals={'plan_cost':float(r[:,16].sum()),'adjust_cost':float(r[:,17].sum()),'emergency_cost':float(r[:,18].sum()),'total_cost':float(target_cost.sum()),'q0_kWh':float(r[:,5].sum()),'a_kWh':float(r[:,6].sum()),'emergency_kWh':float(r[:,9].sum()),'pv_curtail_kWh':float(r[:,10].sum()),'unused_grid_kWh':float(r[:,11].sum())}
    folder=m.ROOT/f'问题{q}结果';folder.mkdir(exist_ok=True)
    csvwrite(folder/'逐时段审计数据.csv',['date','time']+HEADER,([str(dates[i]),interval(t,t+1)]+list(rr[i+31,t]) for i in range(334) for t in range(144)))
    csvwrite(folder/'逐日费用与储能.csv',['日期','计划费用','调整费用','紧急费用','总费用','计划电量','执行电量','紧急电量','弃光','未消纳购电','日初SOC','日末SOC'],[[str(dates[i]),*daily[i,1:4],sum(daily[i,1:4]),rr[i+31,:,5].sum(),*daily[i,4:]] for i in range(334)])
    csvwrite(folder/'求解最优性日志.csv',['horizon_slots','scenarios','objective','dual_bound','absolute_gap_CNY','used_MILP'],solves)
    storage=[];emergency=[];plan=[];adjust=[];specrows=[];specstorage=[]
    for i,date in enumerate(dates):
        day=rr[i+31]; plan.append([str(date),*day[:,5],day[:,5].sum(),day[:,16].sum()]);adjust.append([str(date),*day[:,6],day[:,6].sum(),day[:,16:19].sum()])
        for b in range(6):
            storage.append([str(date) if b==0 else '',interval(b*24,(b+1)*24),day[b*24:(b+1)*24,7].sum(),day[b*24:(b+1)*24,8].sum(),'0:00' if b==0 else ('24:00' if b==1 else ''),day[0,12] if b==0 else (day[-1,13] if b==1 else None)])
            if date in SPEC:specstorage.append([str(date),interval(b*24,(b+1)*24),*day[b*24:(b+1)*24,7:9].sum(0),day[0,12],day[-1,13]])
        mask=day[:,9]>1e-6;start=None
        for t in range(145):
            if t<144 and mask[t] and start is None:start=t
            if start is not None and (t==144 or not mask[t]):emergency.append([str(date),interval(start,t),float(day[start:t,9].sum())]);start=None
        if date in SPEC:
            for t in [60,72,84,96,108,120]:specrows.append([str(date),interval(t,t+1),day[t,5],day[t,6],day[t,9],day[:,5].sum(),day[:,6].sum(),day[:,16].sum(),day[:,17].sum(),day[:,18].sum(),day[:,16:19].sum()])
    csvwrite(folder/'指定日期表1.csv',['日期','时段','原计划购电量','调整执行购电量','紧急购电量','全天计划电量','全天执行电量','计划费用','调整费用','紧急费用','总费用'],specrows)
    csvwrite(folder/'指定日期表2.csv',['日期','时段','充电量','放电量','日初SOC','日末SOC'],specstorage)
    spece=[x for x in emergency if x[0] in SPEC]
    for date in SPEC:
        if not any(x[0]==date for x in spece):spece.append([date,'无紧急购电',0.])
    csvwrite(folder/'指定日期表3.csv',['日期','时间段','紧急购电量'],spece)
    payload=dict(q=q,plan=plan,adjust=adjust,storage=storage,emergency=emergency,checks=checks,totals=totals)
    (folder/'结果数据.json').write_text(json.dumps(payload,ensure_ascii=False,indent=None),encoding='utf-8')
    (folder/'验证报告.json').write_text(json.dumps(dict(checks=checks,totals=totals),ensure_ascii=False,indent=2),encoding='utf-8')
    # 4个指定日期：真实电量、购电与SOC，全部来自实际回测。
    fig,axs=plt.subplots(4,2,figsize=(12,10),layout='constrained')
    for i,date in enumerate(SPEC):
        d=list(z['dates']).index(date);day=rr[d];x=np.arange(144)/6
        axs[i,0].plot(x,day[:,2],label='负荷',lw=1);axs[i,0].plot(x,day[:,3],label='光伏',lw=1);axs[i,0].plot(x,day[:,6],label='执行购电',lw=.9);axs[i,0].plot(x,day[:,9],label='紧急购电',lw=.8)
        axs[i,0].set(title=date,ylabel='kWh / 10分钟',xlim=(0,24));axs[i,1].plot(np.arange(145)/6,np.r_[day[0,12],day[:,13]],color='#335C81');axs[i,1].axhline(1200,c='gray',ls='--',lw=.8);axs[i,1].axhline(10800,c='gray',ls='--',lw=.8);axs[i,1].set(title=date+' 储能',ylabel='kWh',ylim=(0,12000),xlim=(0,24))
    axs[0,0].legend(ncol=4,fontsize=8);axs[-1,0].set_xlabel('小时');axs[-1,1].set_xlabel('小时');fig.savefig(folder/'指定日期运行图.png');plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,4),layout='constrained');im=ax.imshow(rr[31:,:,9],aspect='auto',cmap='YlOrRd',extent=(0,24,334,0));ax.set(xlabel='小时',ylabel='2月1日起日序',title='紧急购电量时段分布');fig.colorbar(im,ax=ax,label='kWh / 10分钟');fig.savefig(folder/'紧急购电热力图.png');plt.close(fig)
    return payload

def compare():
    names=['q3_none','q3_6','q3_6_12','q3_main','q3_penalty'];labels=['仅0时预报','增加6时','增加6时与12时','全部预报','全部预报 另收违约金']
    rows=[];costs=[]
    for name,label in zip(names,labels):
        r=np.load(m.OUT/(name+'.npz'))['records'][31:];c=r[:,:,16:19].sum((1,2));costs.append(c);rows.append([label,float(c.sum()),float(r[:,:,9].sum()),float(r[-1,-1,13])])
    # 7天移动块bootstrap，保留周内相关性，固定随机种子。
    rng=np.random.default_rng(20260911);cis=[]
    for i in range(1,4):
        diff=costs[i-1]-costs[i];samples=[]
        for k in range(2000):
            starts=rng.integers(0,334,48);ix=((starts[:,None]+np.arange(7))%334).ravel()[:334];samples.append(diff[ix].mean())
        lo,hi=np.quantile(samples,[.025,.975]);cis.append([labels[i],float(diff.sum()),float(diff.mean()),float(lo),float(hi)])
    folder=m.ROOT/'问题3结果';csvwrite(folder/'信息价值策略比较.csv',['策略','334天总费用','紧急电量','年末SOC'],rows);csvwrite(folder/'信息价值置信区间.csv',['新增预报策略','总节约费用','日均节约','95%下限','95%上限'],cis)
    strat=[]
    r=np.load(m.OUT/'q3_main.npz');dates=r['dates'][31:];pv=r['records'][31:,:,3].sum(1);bins=np.quantile(pv,[1/3,2/3])
    for label,mask in [(s,np.array([int(d[5:7]) in months for d in dates])) for s,months in [('春',[3,4,5]),('夏',[6,7,8]),('秋',[9,10,11]),('冬',[12,1,2])]]+[(s,(pv<=bins[0]) if j==0 else ((pv>bins[1]) if j==2 else ((pv>bins[0])&(pv<=bins[1])))) for j,s in enumerate(['低光伏出力','中光伏出力','高光伏出力'])]:
        diff=costs[0]-costs[3];strat.append([label,int(mask.sum()),float(diff[mask].sum()),float(diff[mask].mean())])
    csvwrite(folder/'季节与出力分层.csv',['组别','天数','相对仅0时的节约','日均节约'],strat)
    fig,ax=plt.subplots(figsize=(9,4),layout='constrained');ax.bar(labels[:4],np.array([r[1] for r in rows[:4]])/1e6,color=['#9AA7B1','#6A8CAF','#466C92','#284C70']);ax.set_ylabel('总费用 / 百万元');ax.set_title('滚动预报信息价值比较');fig.savefig(folder/'信息价值比较.png');plt.close(fig)
    (folder/'比较摘要.json').write_text(json.dumps(dict(rows=rows,cis=cis,strata=strat),ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':
    for q in [2,3]:print(q,report(f'q{q}_main',q)['totals'],flush=True)
    compare()
