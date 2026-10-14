"""独立的物理反例、结算恒等式和因果性检验。"""
import solve as m
import numpy as np,json

def tests():
    reports=[]
    # 空电池、无光伏、计划不足：紧急购电必须正向供应负荷。
    r=m.opt(np.array([[100.]]),np.zeros((1,1)),np.array([1.]),1200,fixed=np.array([0.]))
    assert abs(r['g'][0,0]-100)<1e-7;reports.append('紧急购电供给侧反例通过')
    # 满电池、夜间买多：弃光必须0，未消纳购电单列，账单仍按全部计划。
    r=m.opt(np.array([[100.]]),np.zeros((1,1)),np.array([1.]),10800,fixed=np.array([200.]),terminal=1)
    assert abs(r['w'][0,0])<1e-7 and abs(r['z'][0,0]-100)<1e-7;reports.append('夜间多购不得伪装成弃光通过')
    # 终端目标需要紧急电能充电，必须遵守效率。
    r=m.opt(np.zeros((1,1)),np.zeros((1,1)),np.array([1.]),5250,fixed=np.array([0.]),target=6000)
    assert abs(r['c'][0]-750/.9)<1e-6 and abs(r['E'][0]-6000)<1e-6;reports.append('终端补库与效率通过')
    # 两种计费口径的手算例，不得混用。
    q=np.array([100.,100.]);a=np.array([80.,120.]);dm=np.maximum(q-a,0);dp=np.maximum(a-q,0)
    refund=q-.5*dm+1.5*dp;penalty=q+.5*dm+1.5*dp
    assert np.allclose(refund,[90,130]) and np.allclose(penalty,[110,130])
    assert np.allclose(refund,a+.5*abs(a-q));reports.append('上调下调两口径手算通过')
    dates,L,V,p,base,F=m.data();fc=m.Forecast(L,V,base,F)
    L2=L.copy();V2=V.copy();F2=F.copy();d=45;t=36
    L2[d,t:]*=7;V2[d,t:]*=3;L2[d+1:]*=2;V2[d+1:]*=5;F2[d,2:]*=8;F2[d+1:]*=4
    f2=m.Forecast(L2,V2,base,F2)
    for q in [2,3]:
        x=fc.predict(d,t,q,36 if q==3 else 0);y=f2.predict(d,t,q,36 if q==3 else 0)
        assert all(np.allclose(a,b) for a,b in zip(x,y))
    reports.append('篡改未来实测和未来发布预报不改变当前预测通过')
    m.OUT.mkdir(exist_ok=True);(m.OUT/'单元验证.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8');print(reports)

if __name__=='__main__':tests()
