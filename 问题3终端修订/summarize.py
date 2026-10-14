"""不依赖目标值，逐条复算约束、费用和参数敏感性指标。"""
import solve as m,analyze as a
import numpy as np,json,shutil
import matplotlib.pyplot as plt
from revise import ALPHAS
def check(z):
    r=z['records'].reshape(-1,19)
    errors={'balance':abs(r[:,6]+r[:,3]-r[:,10]-r[:,11]+r[:,8]+r[:,9]-r[:,2]-r[:,7]).max(),
    'soc':abs(r[:,13]-r[:,12]-.9*r[:,7]+r[:,8]/.9).max(),
    'overlap':np.minimum(r[:,7],r[:,8]).max(),
    'fee':abs(r[:,4]*(r[:,5]-.5*r[:,14]+1.5*r[:,15]+5*r[:,9])-r[:,16:19].sum(1)).max(),
    'continuity':abs(r[1:,12]-r[:-1,13]).max(),
    'bounds':max(0,1200-r[:,12:14].min(),r[:,12:14].max()-10800,r[:,7:9].max()-m.M),
    'spill':max(0,(r[:,10]-r[:,3]).max(),(r[:,11]-r[:,6]).max()),
    'negative':max(0,-r[:,5:12].min()),
    'deviation':max(abs(r[:,14]-np.maximum(r[:,5]-r[:,6],0)).max(),abs(r[:,15]-np.maximum(r[:,6]-r[:,5],0)).max())}
    assert max(errors.values())<1e-5,errors
    assert r[-1,13]>=6000-1e-5
    return {k:float(v) for k,v in errors.items()}
def main():
    selection=json.loads((m.OUT/'selection.json').read_text());best=selection['selected_alpha'];folder=m.ROOT/'问题3结果';folder.mkdir(exist_ok=True)
    rows=[];days=[];audits={};price_median=float(np.median(m.data()[3]))
    for alpha in ALPHAS:
        z=np.load(m.OUT/f'a{alpha:.2f}_all.npz');audits[str(alpha)]=check(z);r=z['records'][31:];E=r[:,:,13]
        rows.append([alpha,alpha*price_median,float(z['records'][14:31,:,16:19].sum()),float(r[:,:,16:19].sum()),float(E.mean()),float((E>=10799.999).mean()),float(E[:,-1].mean()),float(r[:,:,10].sum()),float(r[:,:,11].sum()),float(r[:,:,9].sum()),float(E[-1,-1])])
        for d,day in enumerate(r):days.append([alpha,str(z['dates'][d+31]),day[:,16:19].sum(),day[-1,13],(day[:,13]>=10799.999).mean(),day[:,10].sum(),day[:,11].sum()])
    head=['alpha','lambda_CNY_kWh','Jan15_31_cost','Feb_Dec_cost','mean_end_slot_SOC','full_SOC_fraction','mean_daily_end_SOC','pv_curtail_kWh','unused_grid_kWh','emergency_kWh','year_end_SOC']
    a.csvwrite(folder/'终端系数敏感性.csv',head,rows);a.csvwrite(folder/'逐日敏感性.csv',['alpha','date','cost','daily_end_SOC','full_SOC_fraction','pv_curtail_kWh','unused_grid_kWh'],days)
    shutil.copy2(m.OUT/f'a{best:.2f}_all.npz',m.OUT/'q3_main.npz');payload=a.report('q3_main',3)
    none=np.load(m.OUT/f'a{best:.2f}_none.npz');audits['none']=check(none);rn=none['records'][31:];ra=np.load(m.OUT/'q3_main.npz')['records'][31:]
    diff=rn[:,:,16:19].sum((1,2))-ra[:,:,16:19].sum((1,2));rng=np.random.default_rng(20260911)
    samples=[diff[((rng.integers(0,334,48)[:,None]+np.arange(7))%334).ravel()[:334]].mean() for _ in range(2000)]
    compare={'alpha':best,'none_cost':float(rn[:,:,16:19].sum()),'all_cost':float(ra[:,:,16:19].sum()),'saving':float(diff.sum()),'daily_saving_95CI':np.quantile(samples,[.025,.975]).tolist(),'jan_start_SOC':6000,'feb_start_SOC_none':float(rn[0,0,12]),'feb_start_SOC_all':float(ra[0,0,12])}
    paired=[]
    for coefficient in sorted(set([.3,.5,.7,.9,1.1,best])):
        zn=np.load(m.OUT/f'a{coefficient:.2f}_none.npz');za=np.load(m.OUT/f'a{coefficient:.2f}_all.npz');audits[f'none_{coefficient}']=check(zn)
        cn=float(zn['records'][31:,:,16:19].sum());ca=float(za['records'][31:,:,16:19].sum());paired.append([coefficient,cn,ca,cn-ca,(cn-ca)/cn])
    a.csvwrite(folder/'统一边界的信息价值.csv',['alpha','only_0h_cost','all_forecasts_cost','saving','saving_fraction'],paired)
    (folder/'信息价值.json').write_text(json.dumps(compare,ensure_ascii=False,indent=2),encoding='utf8')
    (folder/'全部轨迹核验.json').write_text(json.dumps(audits,indent=2),encoding='utf8');shutil.copy2(m.OUT/'selection.json',folder/'参数选择.json')
    arr=np.array(rows);transitions=[]
    for lo,hi in zip(arr[:-1],arr[1:]):transitions.append([lo[0],hi[0],hi[3]-lo[3],hi[6]-lo[6],hi[5]-lo[5]])
    a.csvwrite(folder/'相邻系数变化.csv',['alpha_low','alpha_high','cost_difference','mean_daily_end_SOC_difference','full_fraction_difference'],transitions)
    transition=max(transitions,key=lambda r:abs(r[3]))
    fig,axs=plt.subplots(2,2,figsize=(10,7),layout='constrained')
    for ax,j,label in zip(axs.flat,[3,6,5,7],['2—12月费用 / 元','日末SOC均值 / kWh','满电时段比例','弃光 / kWh']):
        ax.plot(arr[:,0],arr[:,j],'-o',ms=4);ax.set(xlabel='α',ylabel=label);ax.axvline(best,c='gray',ls='--');ax.grid(alpha=.2)
    fig.savefig(folder/'终端系数敏感性.png');plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,4),layout='constrained');ax.plot(arr[:,0],arr[:,2],'-o');ax.set(xlabel='α',ylabel='1月15—31日费用 / 元',title='固定S为1的历史验证');fig.savefig(folder/'历史验证.png');plt.close(fig)
    (folder/'汇总.json').write_text(json.dumps({'selection':selection,'rows':rows,'comparison':compare,'paired_information_value':paired,'largest_daily_SOC_change_interval':transition,'results':payload['totals']},ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(compare),flush=True)
if __name__=='__main__':main()
