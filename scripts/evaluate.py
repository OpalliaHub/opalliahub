"""Reproducible synthetic ranking evaluation and scalability benchmark."""
import json
import platform
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jobcompass.config import ROOT
from jobcompass.resume import parse_resume
from jobcompass.matching import rank_jobs

def main():
    text=(ROOT/'data/demo_resume.txt').read_text(encoding='utf-8')
    profile=parse_resume(text)
    jobs=json.loads((ROOT/'data/demo_jobs.json').read_text(encoding='utf-8'))
    for i,j in enumerate(jobs):j['id']=str(i)
    relevant={'Python 开发实习生','数据分析实习生','Junior Data Analyst','QA Automation Intern'}
    ranked=rank_jobs(text,profile,jobs,{'location':'香港, Hong Kong, 深圳','experience_years':0})
    p4=sum(j['title'] in relevant for j in ranked[:4])/4
    expanded=[dict(j,id='{}_{}'.format(i,j['id'])) for i in range(100) for j in jobs]
    begin=time.perf_counter();rank_jobs(text,profile,expanded);elapsed=time.perf_counter()-begin
    report={'python':platform.python_version(),'fixture':'12 author-labelled synthetic jobs; not a real hiring evaluation',
            'precision_at_4':p4,'relevant_labels':sorted(relevant),'top_4':[{'title':j['title'],'score':j['score']} for j in ranked[:4]],
            'benchmark_jobs':len(expanded),'benchmark_seconds':round(elapsed,4),'limitations':'Synthetic labels and handcrafted cases only. No evidence of calibrated probability or real-world fairness/accuracy.'}
    (ROOT/'docs/evaluation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
