import json,time,os
from .llm import LLM
from .ledger import Ledger
from .graph import ClaimGraph
from .priors import PriorLib
from .capsules import CapsuleManager
from .dispatcher import Dispatcher
from .tools.registry import ToolRegistry
from .tools.primitives import make_primitives
from .tools.composite import register_composites
from .models import Obs

class Researcher:
    def __init__(self,api_key=None,state_dir="./research_state"):
        self.dir=state_dir;os.makedirs(state_dir,exist_ok=True)
        self.llm=LLM(key=api_key)
        self.ledger=Ledger(f"{state_dir}/ledger.json")
        self.graph=ClaimGraph(f"{state_dir}/claims.json")
        self.priors=PriorLib(f"{state_dir}/priors.json")
        self.caps=CapsuleManager(self.llm)
        self.tools=ToolRegistry()
        for k,v in make_primitives(self.llm,self.ledger,self.graph).items():
            self.tools.register(k,v["fn"],v["desc"])
        register_composites(self.tools,self.llm)
        self.dispatch=Dispatcher(self.llm,self.ledger,self.graph,
                                 self.priors,self.caps,self.tools)
        self.run_history=[]
        self._load_history()

    def load_data(self,path):
        with open(path) as f:ds=json.load(f)
        ct=0
        for item in ds.get("observations",[]):
            o=Obs(src=item.get("src",""),content=item.get("content",""),
                  mod=item.get("modality","text"),meta=item.get("meta",{}))
            if "id" in item:o.id=item["id"]
            self.ledger.add(o);ct+=1
        print(f"Loaded {ct} observations")
        return ct

    def scan(self):
        mods={};srcs={};langs={};types={};days={}
        bots=0;verified=0;total=len(self.ledger)
        sample_posts=[]
        for o in list(self.ledger.obs.values())[:500]:
            mods[o.mod]=mods.get(o.mod,0)+1
            srcs[o.src]=srcs.get(o.src,0)+1
            langs[o.meta.get("lang","?")]=langs.get(o.meta.get("lang","?"),0)+1
            types[o.meta.get("type","?")]=types.get(o.meta.get("type","?"),0)+1
            days[o.meta.get("day","?")]=days.get(o.meta.get("day","?"),0)+1
            if o.meta.get("is_bot") or o.meta.get("persona")=="bot_amplifier":bots+=1
            if o.meta.get("account",{}).get("badge") in ("blue_check","org_gold"):verified+=1
            if len(sample_posts)<20 and o.mod=="x_post" and not o.meta.get("is_history"):
                sample_posts.append({"src":o.src,"lang":o.meta.get("lang","?"),
                                    "content":o.content[:150]})
        papers=self.tools.call("fetch_paper_content",paper_type="paper_abstract")
        figs=self.tools.call("fetch_figure_content",figure_id="")
        return {"total":total,"modalities":mods,
                "top_sources":dict(sorted(srcs.items(),key=lambda x:-x[1])[:15]),
                "languages":dict(sorted(langs.items(),key=lambda x:-x[1])[:20]),
                "types":types,"days":days,"bots":bots,"verified":verified,
                "papers":papers if isinstance(papers,list) else [],
                "figures":figs if isinstance(figs,list) else [],
                "sample_posts":sample_posts,
                "existing_claims":len(self.graph),
                "existing_priors":self.priors.to_context()}

    def generate_theses(self,scan_data=None,n=5):
        if not scan_data:scan_data=self.scan()
        prior_ctx=self.priors.to_context()
        history_ctx=""
        if self.run_history:
            history_ctx="\n\nPrevious research runs:\n"+"\n".join(
                f"- Run {r['run']}: \"{r['conjecture'][:60]}\" -> {r['conclusion'][:80]}"
                for r in self.run_history[-5:])
        prompt=(
            f"You are an autonomous research agent. You have access to a large corpus "
            f"of social media posts, papers, figures, and discourse data.\n\n"
            f"Corpus scan:\n"
            f"- {scan_data['total']} total observations\n"
            f"- Languages: {list(scan_data['languages'].keys())[:15]}\n"
            f"- Post types: {scan_data['types']}\n"
            f"- Bots detected: {scan_data['bots']}\n"
            f"- Papers: {len(scan_data['papers'])}\n"
            f"- Figures: {len(scan_data['figures'])}\n"
            f"- Sample posts:\n"
            +"\n".join(f"  [{p['lang']}] @{p['src']}: {p['content'][:100]}"
                       for p in scan_data['sample_posts'][:10])
            +f"\n\nPaper excerpts:\n"
            +"\n".join(f"  {p.get('content','')[:150]}" for p in scan_data['papers'][:3])
            +f"\n\nExisting priors:\n{prior_ctx}"
            +f"\n{history_ctx}\n\n"
            f"Generate {n} research conjectures. These should be:\n"
            f"1. Discoverable from the data (not just assumed)\n"
            f"2. Non-overlapping with previous research\n"
            f"3. Testable with the available evidence\n"
            f"4. Ranging from specific claims to broad patterns\n"
            f"5. Some should CROSS-TEST or BUILD ON existing priors\n\n"
            f"Return JSON:\n"
            f'{{"theses":[{{"conjecture":"the research question",'
            f'"motivation":"why this is interesting given the data",'
            f'"expected_evidence":"what you expect to find",'
            f'"builds_on":"which prior or previous finding this extends",'
            f'"priority":"high|medium|low"}}]}}')
        r=self.llm.structured(prompt,{"type":"object"},role="strong")
        theses=r.get("theses",[])
        print(f"\nGenerated {len(theses)} autonomous theses:")
        for i,t in enumerate(theses):
            print(f"  [{i+1}] ({t.get('priority','?')}) {t.get('conjecture','')[:80]}")
            if t.get("builds_on"):print(f"      builds on: {t['builds_on'][:60]}")
        return theses

    def investigate(self,conjecture,steps=4):
        print(f"\n{'='*60}")
        print(f"INVESTIGATING: {conjecture[:80]}")
        print(f"{'='*60}")
        t0=time.time()
        self.dispatch=Dispatcher(self.llm,self.ledger,self.graph,
                                 self.priors,self.caps,self.tools)
        hyps=self.dispatch.init(conjecture)
        self.dispatch.run(max_steps=steps)
        report=self.dispatch.synthesize()
        dt=time.time()-t0
        run_record={
            "run":len(self.run_history)+1,
            "conjecture":conjecture,
            "hypotheses":[{"id":h.id,"stmt":h.stmt,"status":h.status,"conf":h.conf}
                         for h in self.dispatch.hyps.values()],
            "conclusion":report.get("object_conclusion",""),
            "narrative":report.get("narrative_conclusion",""),
            "divergence":report.get("divergence",""),
            "new_priors":report.get("new_priors",[]),
            "unresolved":report.get("unresolved",[]),
            "confidence":report.get("confidence",0),
            "claims":len(self.graph),
            "priors_active":len(self.priors.active()),
            "time":round(dt,1),
            "cost":self.llm.usage()["cost_usd"],
            "step_metrics":self.dispatch.step_metrics}
        self.run_history.append(run_record)
        for np in report.get("new_priors",[]):
            if isinstance(np,str) and len(np)>20:
                self.priors.promote(np[:200],typ="domain",
                                   evidence=[conjecture[:50]])
        self._save_history()
        self.ledger.save();self.graph.save();self.priors.save()
        print(f"\n  Conclusion: {report.get('object_conclusion','')[:120]}")
        print(f"  Confidence: {report.get('confidence','?')}")
        print(f"  Claims: {len(self.graph)}, Priors: {len(self.priors.active())}")
        print(f"  Time: {dt:.0f}s, Cost: ${self.llm.usage()['cost_usd']:.4f}")
        return report

    def autonomous_run(self,n_rounds=3,theses_per_round=3,steps_per=4,budget=1.0):
        print(f"{'='*60}")
        print(f"AUTONOMOUS RESEARCH SESSION")
        print(f"Rounds: {n_rounds}, Theses/round: {theses_per_round}, Budget: ${budget}")
        print(f"{'='*60}")
        t0=time.time()
        for rnd in range(n_rounds):
            if self.llm.usage()["cost_usd"]>=budget:
                print(f"\nBudget reached at round {rnd+1}");break
            print(f"\n{'='*40}")
            print(f"ROUND {rnd+1}/{n_rounds}")
            print(f"{'='*40}")
            scan=self.scan()
            theses=self.generate_theses(scan,theses_per_round)
            high=[t for t in theses if t.get("priority")=="high"]
            med=[t for t in theses if t.get("priority")=="medium"]
            ordered=high+med+[t for t in theses if t not in high+med]
            for i,thesis in enumerate(ordered):
                if self.llm.usage()["cost_usd"]>=budget:
                    print(f"\nBudget reached");break
                conj=thesis.get("conjecture","")
                if not conj:continue
                print(f"\n  Thesis {i+1}/{len(ordered)}: {conj[:60]}...")
                self.investigate(conj,steps=steps_per)
            if rnd<n_rounds-1:
                print(f"\n  Prior editor reviewing accumulated knowledge...")
                edits=self.dispatch.agents["prior_editor"].run(
                    trigger=f"round_{rnd+1}_complete")
                for e in edits:
                    print(f"    {e.get('action','')}: {e.get('reason','')[:50]}")
        dt=time.time()-t0
        u=self.llm.usage()
        self._save_history()
        self.ledger.save();self.graph.save();self.priors.save()
        print(f"\n{'='*60}")
        print(f"AUTONOMOUS SESSION COMPLETE")
        print(f"{'='*60}")
        print(f"  Rounds: {n_rounds}")
        print(f"  Investigations: {len(self.run_history)}")
        print(f"  Claims: {len(self.graph)}")
        print(f"  Active priors: {len(self.priors.active())}")
        print(f"  Time: {dt:.0f}s ({dt/60:.1f}m)")
        print(f"  Cost: ${u['cost_usd']:.4f}")
        print(f"\n  Research history:")
        for r in self.run_history:
            print(f"    Run {r['run']}: \"{r['conjecture'][:50]}...\" "
                  f"-> conf={r['confidence']} priors={r['priors_active']}")
        print(f"\n  Active priors:")
        print(f"  {self.priors.to_context()}")
        return self.run_history

    def _save_history(self):
        with open(f"{self.dir}/run_history.json",'w') as f:
            json.dump(self.run_history,f,indent=2,default=str)
    def _load_history(self):
        p=f"{self.dir}/run_history.json"
        if os.path.exists(p):
            with open(p) as f:self.run_history=json.load(f)
