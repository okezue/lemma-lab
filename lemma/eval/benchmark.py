import json,time,os
from ..llm import LLM,MODELS,_DEFAULTS
from ..ledger import Ledger
from ..graph import ClaimGraph
from ..priors import PriorLib
from ..capsules import CapsuleManager
from ..dispatcher import Dispatcher
from ..tools.registry import ToolRegistry
from ..tools.primitives import make_primitives
from ..tools.composite import register_composites
from .metrics import score_report
from ..models import Obs

class Benchmark:
    def __init__(self,api_key=None):
        self.key=api_key;self.results=[]

    def _make(self,use_priors=True,use_caps=True,model_override=None):
        LLM.reset_models()
        if model_override:LLM.override_all(model_override)
        llm=LLM(key=self.key)
        ledger=Ledger()
        graph=ClaimGraph()
        priors=PriorLib()
        caps=CapsuleManager(llm if use_caps else None)
        tools=ToolRegistry()
        for k,v in make_primitives(llm,ledger,graph).items():
            tools.register(k,v["fn"],v["desc"])
        register_composites(tools,llm)
        d=Dispatcher(llm,ledger,graph,priors,caps,tools)
        return d,ledger,llm

    def _load(self,ledger,dataset):
        for o in dataset.get("observations",[]):
            ledger.add(Obs(src=o.get("src",""),content=o.get("content",""),
                          mod=o.get("modality","text"),meta=o.get("meta",{})))

    def run_config(self,name,dataset,max_steps=5,use_priors=True,use_caps=True,
                   model_override=None):
        print(f"\n{'='*40}\nConfig: {name} (model={model_override or 'default'})\n{'='*40}")
        d,ledger,llm=self._make(use_priors,use_caps,model_override)
        self._load(ledger,dataset)
        results=[]
        for q in dataset.get("eval_queries",[]):
            t0=time.time()
            d.init(q["q"])
            d.run(max_steps=max_steps)
            report=d.synthesize()
            report["_step_metrics"]=d.step_metrics
            dt=time.time()-t0
            u=llm.usage()
            snap_early=d.temporal_snapshot(at_step=min(2,d.step_n))
            snap_late=d.temporal_snapshot()
            results.append({"query":q["q"],"gold":q.get("gold",""),
                           "report":report,"time":dt,"steps":d.step_n,
                           "claims":len(d.graph),"priors":len(d.priors),
                           "api_calls":u["calls"],"cost":u["cost_usd"],
                           "parses_ok":u["parses_ok"],"parses_fail":u["parses_fail"],
                           "step_metrics":d.step_metrics,
                           "prior_promotions":d.prior_promotions,
                           "proof_repairs":d.proof_repairs,
                           "temporal_snapshots":{"early":snap_early,"late":snap_late}})
            print(f"  Q: {q['q'][:50]}... ({dt:.1f}s, {d.step_n}steps, "
                  f"{len(d.graph)}claims, ${u['cost_usd']:.4f})")
        self.results.append({"config":name,"results":results,
                            "model":model_override or "grok-4-fast-reasoning"})
        LLM.reset_models()
        return results

    def run_model_variants(self,dataset,max_steps=3):
        for name,model in [("all-reasoning","grok-4-fast-reasoning"),
                           ("all-mini","grok-3-mini"),
                           ("role-specialized",None)]:
            self.run_config(name,dataset,max_steps,model_override=model)

    def run_context_ablation(self,dataset,max_steps=3):
        self.run_config("flat",dataset,max_steps,use_priors=False,use_caps=False)
        self.run_config("capsules-only",dataset,max_steps,use_priors=False,use_caps=True)
        self.run_config("capsules+priors",dataset,max_steps,use_priors=True,use_caps=True)
        self.run_config("full",dataset,max_steps,use_priors=True,use_caps=True)

    def run_full(self,dataset,max_steps=3):
        self.run_context_ablation(dataset,max_steps)
        self.run_model_variants(dataset,max_steps)

    def compare(self,world):
        print(f"\n{'='*55}\nBENCHMARK COMPARISON\n{'='*55}")
        all_cfgs=[]
        for cfg in self.results:
            name=cfg["config"]
            scores=[]
            for r in cfg["results"]:
                s=score_report(r["report"],world)
                s["time"]=r["time"];s["steps"]=r["steps"]
                s["claims"]=r["claims"];s["cost"]=r["cost"]
                scores.append(s)
            if not scores:continue
            avg={k:sum(s.get(k,0) for s in scores)/len(scores) for k in scores[0]}
            all_cfgs.append({"name":name,"avg":avg,"model":cfg.get("model","")})
            print(f"\n  {name} ({cfg.get('model','default')}):")
            for k,v in sorted(avg.items()):
                if isinstance(v,float):print(f"    {k}: {v:.3f}")
                else:print(f"    {k}: {v}")
        if len(all_cfgs)>=2:
            print(f"\n  {'='*50}")
            print(f"  RANKING (by overall):")
            ranked=sorted(all_cfgs,key=lambda x:-x["avg"].get("overall",0))
            for i,c in enumerate(ranked):
                o=c["avg"].get("overall",0)
                ct=c["avg"].get("contradiction_retention",0)
                ns=c["avg"].get("narrative_evidence_sep",0)
                tb=c["avg"].get("temporal_belief",0)
                cost=c["avg"].get("cost",0)
                print(f"    {i+1}. {c['name']}: overall={o:.3f} "
                      f"(cr={ct:.2f} ns={ns:.2f} tb={tb:.2f} ${cost:.4f})")
        temporal=[]
        for cfg in self.results:
            for r in cfg["results"]:
                ts=r.get("temporal_snapshots",{})
                if ts:temporal.append({"config":cfg["config"],"query":r["query"][:40],
                                       "early":ts.get("early",{}).get("at_step",0),
                                       "late":ts.get("late",{}).get("at_step",0)})
        if temporal:
            print(f"\n  TEMPORAL BELIEF TRACKING ({len(temporal)} snapshots)")
            for t in temporal[:5]:
                print(f"    {t['config']}: {t['query']}... (early@{t['early']} -> late@{t['late']})")

    def save(self,path="benchmark_results.json"):
        with open(path,'w') as f:json.dump(self.results,f,indent=2,default=str)
        print(f"Saved to {path}")
