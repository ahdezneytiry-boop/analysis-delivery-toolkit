"""1月选择参数后固定参数，全年独立策略回测；每条SOC轨迹内部串行。"""
import solve,json
from concurrent.futures import ProcessPoolExecutor,as_completed

def job(cfg):
    q,S,term,updates,fee,name=cfg
    solve.run(q,S,updates,fee,terminal_scale=term,name=name)
    return name

if __name__=='__main__':
    val=json.loads((solve.OUT/'validation.json').read_text(encoding='utf-8'));a=val['best']['2'];b=val['best']['3']
    cfgs=[(2,a['S'],a['terminal'],(),-.5,'q2_main')]
    for name,up,fee in [('q3_none',(),-.5),('q3_6',(36,),-.5),('q3_6_12',(36,72),-.5),('q3_main',(36,72,108),-.5),('q3_penalty',(36,72,108),.5)]:
        cfgs.append((3,b['S'],b['terminal'],up,fee,name))
    (solve.OUT/'run_config.json').write_text(json.dumps(cfgs,ensure_ascii=False,indent=2),encoding='utf-8')
    with ProcessPoolExecutor(max_workers=3) as pool:
        for f in as_completed([pool.submit(job,c) for c in cfgs]):print('FINISHED',f.result(),flush=True)
