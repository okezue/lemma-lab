import cmd,json,os
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

class LemmaREPL(cmd.Cmd):
    prompt="lemma> "
    intro=("\n  LEMMA Lab - Theorem-prover-style research system\n"
           "  Type 'help' for commands.\n")

    def __init__(self,api_key=None,data_dir="./lemma_state"):
        super().__init__()
        self.dir=data_dir;os.makedirs(data_dir,exist_ok=True)
        self.llm=LLM(key=api_key)
        self.ledger=Ledger(f"{data_dir}/ledger.json")
        self.graph=ClaimGraph(f"{data_dir}/claims.json")
        self.priors=PriorLib(f"{data_dir}/priors.json")
        self.caps=CapsuleManager(self.llm)
        self.tools=ToolRegistry()
        for k,v in make_primitives(self.llm,self.ledger,self.graph).items():
            self.tools.register(k,v["fn"],v["desc"])
        register_composites(self.tools,self.llm)
        self.dispatch=Dispatcher(self.llm,self.ledger,self.graph,
                                 self.priors,self.caps,self.tools)

    def do_ask(self,arg):
        """ask <conjecture> - Start investigation"""
        if not arg:print("Usage: ask <conjecture>");return
        hyps=self.dispatch.init(arg)
        print(f"\nGenerated {len(hyps)} hypotheses:")
        for h in hyps:print(f"  [{h.id}] {h.stmt}")

    def do_run(self,arg):
        """run [N] - Run N dispatch steps (default 5)"""
        n=int(arg) if arg.strip() else 5
        def cb(step,r):
            if r:print(f"  step {step}: {r.get('hyp','')} via {r.get('branch','')}")
        self.dispatch.run(max_steps=n,callback=cb)

    def do_step(self,_):
        """step - Run one dispatch cycle"""
        r=self.dispatch.step()
        if r:print(json.dumps(r,indent=2))
        else:print("No active branches")

    def do_agenda(self,_):
        """agenda - Show current investigation status"""
        print(json.dumps(self.dispatch.status(),indent=2))

    def do_spawn(self,arg):
        """spawn <stmt> - Add a new hypothesis"""
        if not arg:print("Usage: spawn <hypothesis>");return
        h,b=self.dispatch.spawn(arg)
        print(f"Created {h.id} -> branch {b.id}")

    def do_challenge(self,arg):
        """challenge <hyp_id> - Run breaker against hypothesis"""
        if not arg:print("Usage: challenge <hyp_id>");return
        r=self.dispatch.challenge(arg.strip())
        if r:print(f"Breaker found {len(r)} artifacts")
        else:print("Not found")

    def do_inspect(self,arg):
        """inspect <id> - Inspect any object by ID"""
        if not arg:print("Usage: inspect <id>");return
        id=arg.strip().split()[0]
        for store,getter in [(self.dispatch.hyps,lambda:self.dispatch.hyps.get(id)),
                             (None,lambda:self.caps.get_branch(id)),
                             (None,lambda:self.graph.get(id)),
                             (None,lambda:self.ledger.get(id))]:
            obj=getter()
            if obj:
                d=obj.to_dict() if hasattr(obj,'to_dict') else obj
                print(json.dumps(d,indent=2,default=str));return
        print(f"Not found: {id}")

    def do_promote(self,arg):
        """promote <hyp_id> - Promote hypothesis to prior"""
        if not arg:print("Usage: promote <hyp_id>");return
        p=self.dispatch.promote_prior(arg.strip())
        if p:print(f"Prior {p.id}: {p.stmt}")
        else:print("Not found")

    def do_priors(self,_):
        """priors - List active priors"""
        print(self.priors.to_context())

    def do_claims(self,arg):
        """claims [N] - Show top N claims"""
        n=int(arg) if arg.strip() else 20
        print(self.graph.to_context(n))

    def do_tools(self,_):
        """tools - List available tools"""
        for t in self.tools.list_tools():print(f"  {t}")

    def do_report(self,_):
        """report - Generate synthesis report"""
        r=self.dispatch.synthesize()
        print("\n{'='*40}\nSYNTHESIS REPORT\n{'='*40}")
        for k,v in r.items():
            print(f"\n{k}:")
            if isinstance(v,list):
                for i in v:print(f"  - {i}")
            else:print(f"  {v}")

    def do_save(self,_):
        """save - Persist state to disk"""
        self.ledger.save();self.graph.save();self.priors.save()
        print("Saved")

    def do_load_dataset(self,arg):
        """load_dataset <path> - Load observations from JSON"""
        if not arg:print("Usage: load_dataset <path>");return
        p=arg.strip()
        if not os.path.exists(p):print(f"Not found: {p}");return
        with open(p) as f:data=json.load(f)
        ct=0
        for item in data.get("observations",[]):
            o=Obs(src=item.get("src",""),content=item.get("content",""),
                  mod=item.get("modality","text"),meta=item.get("meta",{}))
            if "id" in item:o.id=item["id"]
            self.ledger.add(o)
            ct+=1
        print(f"Loaded {ct} observations")
        if "stats" in data:
            s=data["stats"]
            print(f"  Posts: {s.get('total_posts',0)}, "
                  f"Threads: {s.get('threads',0)}, "
                  f"Authors: {s.get('unique_authors',0)}, "
                  f"Languages: {s.get('languages',[])}")

    def do_log(self,arg):
        """log [N] - Show last N log entries"""
        n=int(arg) if arg.strip() else 10
        for e in self.dispatch.log[-n:]:
            print(f"  [{e['step']}] {e['msg']}")

    def do_toolize(self,_):
        """toolize - Analyze traces and propose composite tools"""
        traces=self.tools.get_traces()
        if not traces:print("No traces");return
        recipes=self.dispatch.agents["toolsmith"].run(traces)
        for r in recipes:
            print(f"  Proposed: {r.name} - {r.desc}")
            self.tools.register(r.name,lambda **kw:{"recipe":r.steps,"args":kw},r.desc)

    def do_tool(self,arg):
        """tool <name> [json_args] - Call a tool directly"""
        parts=arg.strip().split(None,1)
        if not parts:print("Usage: tool <name> [json_args]");return
        name=parts[0]
        kw=json.loads(parts[1]) if len(parts)>1 else {}
        r=self.tools.call(name,**kw)
        print(json.dumps(r,indent=2,default=str))

    def do_usage(self,_):
        """usage - Show API token usage and estimated cost"""
        u=self.llm.usage()
        print(f"  API calls: {u['calls']}")
        print(f"  Tokens in: {u['tok_in']:,}")
        print(f"  Tokens out: {u['tok_out']:,}")
        print(f"  Est. cost: ${u['cost_usd']:.4f}")

    def do_stats(self,_):
        """stats - Show dataset and system stats"""
        mods={};srcs={};langs={};bots=0
        for o in self.ledger.obs.values():
            mods[o.mod]=mods.get(o.mod,0)+1
            srcs[o.src]=srcs.get(o.src,0)+1
            langs[o.meta.get("lang","?")]=langs.get(o.meta.get("lang","?"),0)+1
            if o.meta.get("is_bot"):bots+=1
        print(f"  Observations: {len(self.ledger)}")
        print(f"  Claims: {len(self.graph)}")
        print(f"  Priors: {len(self.priors)}")
        print(f"  Modalities: {dict(sorted(mods.items(),key=lambda x:-x[1]))}")
        print(f"  Top sources: {dict(sorted(srcs.items(),key=lambda x:-x[1])[:10])}")
        print(f"  Languages: {dict(sorted(langs.items(),key=lambda x:-x[1]))}")
        print(f"  Bot posts: {bots}")

    def do_scout(self,arg):
        """scout <artifact_text_or_id> - Run multimodal scout on artifact"""
        if not arg:print("Usage: scout <text or obs_id>");return
        o=self.ledger.get(arg.strip())
        if o:
            arts=self.dispatch.agents["scout"].run(o.content,o.mod)
        else:
            arts=self.dispatch.agents["scout"].run(arg.strip(),"text")
        for a in arts:
            d=a.to_dict() if hasattr(a,'to_dict') else a
            print(json.dumps(d,indent=2,default=str))

    def do_analyze(self,arg):
        """analyze [focus] - Run analyst agent on dataset"""
        focus=arg.strip() if arg.strip() else "full"
        r=self.dispatch.agents["analyst"].run(focus)
        print("\n=== ANALYSIS ===")
        a=r.get("analysis",{})
        for k in ["summary","temporal_pattern","language_dynamics","credibility_distribution"]:
            if k in a:print(f"\n{k}:\n  {a[k]}")
        if "patterns" in a:
            print("\nPatterns:")
            for p in a["patterns"]:print(f"  - {p}")
        if "anomalies" in a:
            print("\nAnomalies:")
            for an in a["anomalies"]:print(f"  - {an}")
        graphs=r.get("graphs",{}).get("graphs",[])
        if graphs:
            print(f"\n=== PROPOSED GRAPHS ({len(graphs)}) ===")
            for g in graphs:
                print(f"\n  {g.get('title','')} ({g.get('type','')})")
                print(f"    Insight: {g.get('insight','')}")
                if g.get("matplotlib_code"):
                    print(f"    Code: {g['matplotlib_code'][:100]}...")
        checks=r.get("checks",{})
        if checks.get("checks"):
            print(f"\n=== CLAIM CHECKS ({len(checks['checks'])}) ===")
            for c in checks["checks"]:
                print(f"  [{c.get('claim_id','')}] {c.get('verdict','')}: {c.get('claim','')[:60]}")
        if checks.get("summary"):
            print(f"\n  Summary: {checks['summary']}")

    def do_edit_priors(self,arg):
        """edit_priors [trigger] - Run prior editor agent"""
        trigger=arg.strip() if arg.strip() else "manual"
        r=self.dispatch.agents["prior_editor"].run(trigger)
        if not r:print("No changes");return
        for e in r:
            print(f"  {e.get('action','')}: {e.get('prior',e.get('id',''))} — {e.get('reason','')[:60]}")

    def do_demote(self,arg):
        """demote <prior_id> - Demote a prior and trigger proof repair"""
        if not arg:print("Usage: demote <prior_id>");return
        affected=self.dispatch.demote_prior(arg.strip())
        if affected:
            print(f"Demoted. Affected branches: {affected}")
            print("Run 'step' or 'run' to re-evaluate stale branches.")
        else:print("Prior not found or already inactive")

    def do_snapshot(self,arg):
        """snapshot [step] - Show temporal belief snapshot"""
        step=int(arg) if arg.strip() else None
        s=self.dispatch.temporal_snapshot(step)
        print(json.dumps(s,indent=2,default=str))

    def do_metrics(self,_):
        """metrics - Show per-step metrics"""
        for sm in self.dispatch.step_metrics:
            print(f"  Step {sm['step']}: hyp={sm['hyp'][:8]} "
                  f"status={sm['hyp_status']} conf={sm['branch_conf']:.2f} "
                  f"sup={sm['sup']} con={sm['con']} "
                  f"audit={sm['audit_verdict']} "
                  f"artifacts={sm['artifacts_found']} "
                  f"time={sm['time']:.1f}s cost=${sm['cost']:.4f}")

    def do_repairs(self,_):
        """repairs - Show proof repair history"""
        if not self.dispatch.proof_repairs:
            print("No proof repairs");return
        for r in self.dispatch.proof_repairs:
            print(f"  Step {r['step']}: prior={r['prior']} "
                  f"stale_claims={r['stale_claims']} "
                  f"branches={r['affected_branches']}")

    def do_fetch(self,arg):
        """fetch <paper_type|figure_id> - Fetch paper/figure content"""
        if not arg:print("Usage: fetch <paper_abstract|paper_appendix|errata|fig3_full|...>");return
        a=arg.strip()
        if "fig" in a.lower():
            r=self.tools.call("fetch_figure_content",figure_id=a)
        else:
            r=self.tools.call("fetch_paper_content",paper_type=a)
        print(json.dumps(r,indent=2,default=str))

    def do_quit(self,_):
        """quit - Save and exit"""
        self.do_save("")
        print("Goodbye");return True
    do_exit=do_quit
    do_EOF=do_quit
