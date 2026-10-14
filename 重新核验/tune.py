import solve
import numpy as np,json
from concurrent.futures import ProcessPoolExecutor

def job(cfg):
    q,S,term=cfg
    name=f'validation_q{q}_S{S}_v{term}'
    r=solve.run(q,S,end=31,terminal_scale=term,name=name)
    x=r['daily'][14:];return dict(q=q,S=S,terminal=term,cost=float(x[:,1:4].sum()),name=name)

if __name__=='__main__':
    candidates=[(q,S,term) for q in [2,3] for S,term in [(1,1.),(10,1.),(20,1.),(10,.5),(10,1.5)]]
    with ProcessPoolExecutor(max_workers=2) as pool:results=list(pool.map(job,candidates))
    best={str(q):min([r for r in results if r['q']==q],key=lambda r:r['cost']) for q in [2,3]}
    (solve.OUT/'validation.json').write_text(json.dumps(dict(candidates=results,best=best),ensure_ascii=False,indent=2),encoding='utf-8')
    print('BEST',best,flush=True)
