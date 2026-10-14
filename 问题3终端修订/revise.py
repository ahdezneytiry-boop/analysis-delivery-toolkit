"""固定S=1；复用未改变的前364天，末日重算；新系数完整因果回测。"""
import solve as m
import numpy as np,json,io,zipfile
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
SOURCE=m.ROOT.parent/'重新核验'
ARCHIVE='D:/weixing/xwechat_files/wxid_jtqt6ar7kbkt12_b5f7/msg/file/2026-09/第3问结果交付包_λ敏感性版_v2.zip'
ALPHAS=[.3,.5,.51,.52,.55,.60,.65,.7,.9,1.1]
def worker(alpha,updates=(36,72,108)):
    label='all' if updates else 'none';name=f'a{alpha:.2f}_{label}'
    dest=m.OUT/(name+'.npz')
    if dest.exists():return name
    if alpha in [.3,.5,.7,.9,1.1] and Path(ARCHIVE).is_file():
        with zipfile.ZipFile(ARCHIVE) as z:
            suffix=f'lambda_{alpha:.1f}_q3_'+('all_forecasts' if updates else 'none')+'.npz'
            n=next(n for n in z.namelist() if n.endswith(suffix));old=dict(np.load(io.BytesIO(z.read(n))))
        tail=m.run(3,S=1,updates=updates,alpha=alpha,begin=364,initial_soc=old['records'][363,-1,13],name=name,save=False)
        joined={}
        for k in ['records','daily','plans','versions','dates']:joined[k]=np.concatenate([old[k][:364],tail[k]])
        perday=145+len(updates);joined['solves']=np.concatenate([old['solves'][:364*perday],tail['solves']])
        m.OUT.mkdir(exist_ok=True);np.savez_compressed(dest,**joined)
    else:m.run(3,S=1,updates=updates,alpha=alpha,name=name)
    return name
def main():
    m.OUT.mkdir(exist_ok=True)
    with ProcessPoolExecutor(max_workers=3) as pool:
        fs=[pool.submit(worker,a) for a in ALPHAS]
        for f in as_completed(fs):print('DONE',f.result(),flush=True)
    vals=[]
    for a in ALPHAS:
        r=np.load(m.OUT/f'a{a:.2f}_all.npz')['records'];vals.append({'alpha':a,'jan_validation':float(r[14:31,:,16:19].sum()),'test_cost':float(r[31:,:,16:19].sum())})
    best=min(vals,key=lambda x:(x['jan_validation'],x['alpha']))['alpha']
    worker(best,());(m.OUT/'selection.json').write_text(json.dumps({'candidates':vals,'selected_alpha':best,'criterion':'Jan15-31 only; S=1 fixed; revised candidate set is post hoc'},indent=2),encoding='utf8')
    print('SELECTED',best,flush=True)
if __name__=='__main__':main()
