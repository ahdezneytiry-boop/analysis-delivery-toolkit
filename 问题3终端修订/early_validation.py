"""提前完成短验证，使所选参数的无更新对照与全年敏感性并行。"""
import solve as m,revise
import numpy as np,json
from concurrent.futures import ProcessPoolExecutor
def short(alpha):
    r=m.run(3,S=1,alpha=alpha,end=31,name=f'jan_{alpha:.2f}',save=True)['records']
    return alpha,float(r[14:31,:,16:19].sum())
if __name__=='__main__':
    with ProcessPoolExecutor(max_workers=2) as p:vals=list(p.map(short,[.6,.65]))
    for a in revise.ALPHAS:
        if a in [.6,.65]:continue
        r=np.load(m.OUT/f'a{a:.2f}_all.npz')['records'];vals.append((a,float(r[14:31,:,16:19].sum())))
    best=min(vals,key=lambda x:(x[1],x[0]))[0]
    (m.OUT/'early_selection.json').write_text(json.dumps({'values':vals,'best':best}))
    print('EARLY SELECTED',best,flush=True);revise.worker(best,());print('BASELINE DONE',flush=True)
