import sys,os,json,argparse
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))

def main():
    p=argparse.ArgumentParser(description="LEMMA Lab")
    p.add_argument("--key",default=os.getenv("XAI_API_KEY"),help="xAI API key")
    p.add_argument("--dir",default="./lemma_state",help="State directory")
    p.add_argument("--mode",choices=["repl","generate","benchmark","ask","synth","test","swarm","research"],default="repl")
    p.add_argument("--query",default="",help="Query for ask mode")
    p.add_argument("--steps",type=int,default=5,help="Max dispatch steps")
    p.add_argument("--dataset",default="",help="Dataset JSON path")
    p.add_argument("--n-accounts",type=int,default=100,help="Synthetic accounts to generate")
    p.add_argument("--posts-per-day",type=int,default=15,help="Synthetic posts per day")
    p.add_argument("--single-posts",type=int,default=50,help="Individual diverse posts")
    p.add_argument("--budget",type=float,default=5.0,help="Max $ for swarm session")
    p.add_argument("--seed-agents",type=int,default=10,help="Seed agents for swarm")
    p.add_argument("--max-ticks",type=int,default=200,help="Max swarm ticks")
    args=p.parse_args()
    if args.mode=="repl":
        from lemma.repl import LemmaREPL
        repl=LemmaREPL(api_key=args.key,data_dir=args.dir)
        if args.dataset:repl.do_load_dataset(args.dataset)
        repl.cmdloop()
    elif args.mode=="generate":
        from lemma.llm import LLM
        from lemma.dataset.world import WORLD
        from lemma.dataset.generator import generate_dataset
        llm=LLM(key=args.key)
        generate_dataset(llm,WORLD)
        print(f"API usage: {llm.usage()}")
    elif args.mode=="synth":
        from lemma.llm import LLM
        from lemma.dataset.synthetic import run_full_synthetic
        llm=LLM(key=args.key)
        run_full_synthetic(llm,n_accounts=args.n_accounts,
                          posts_per_day=args.posts_per_day,
                          single_posts=args.single_posts)
    elif args.mode=="swarm":
        from lemma.dataset.swarm import run_swarm
        run_swarm(args.key,budget=args.budget,n_seed=args.seed_agents,
                  max_ticks=args.max_ticks)
    elif args.mode=="research":
        from lemma.researcher import Researcher
        r=Researcher(api_key=args.key,state_dir=args.dir)
        if args.dataset:r.load_data(args.dataset)
        if args.query:
            r.investigate(args.query,steps=args.steps)
        else:
            r.autonomous_run(n_rounds=3,theses_per_round=3,
                            steps_per=args.steps,budget=args.budget)
    elif args.mode=="test":
        _run_agent_test(args)
    elif args.mode=="benchmark":
        from lemma.eval.benchmark import Benchmark
        from lemma.dataset.world import WORLD
        bm=Benchmark(api_key=args.key)
        dp=args.dataset or "./dataset_data/polyglot_crisis.json"
        if not os.path.exists(dp):
            print(f"Dataset not found: {dp}. Run --mode generate first.");return
        with open(dp) as f:ds=json.load(f)
        bm.run_config("flat",ds,args.steps,use_priors=False,use_caps=False)
        bm.run_config("capsules_only",ds,args.steps,use_priors=False)
        bm.run_config("capsules+priors",ds,args.steps)
        bm.run_config("full",ds,args.steps)
        bm.compare(WORLD)
        bm.save()
    elif args.mode=="ask":
        if not args.query:print("Provide --query");return
        from lemma.repl import LemmaREPL
        repl=LemmaREPL(api_key=args.key,data_dir=args.dir)
        if args.dataset:repl.do_load_dataset(args.dataset)
        repl.do_ask(args.query)
        repl.do_run(str(args.steps))
        repl.do_report("")
        repl.do_save("")

def _run_agent_test(args):
    print("="*60)
    print("LEMMA Lab — Full Agent Assessment")
    print("="*60)
    from lemma.llm import LLM
    from lemma.ledger import Ledger
    from lemma.graph import ClaimGraph
    from lemma.priors import PriorLib
    from lemma.capsules import CapsuleManager
    from lemma.dispatcher import Dispatcher
    from lemma.tools.registry import ToolRegistry
    from lemma.tools.primitives import make_primitives
    from lemma.tools.composite import register_composites
    from lemma.models import Obs
    import time
    dp=args.dataset or "./dataset_data/polyglot_crisis.json"
    if not os.path.exists(dp):
        print(f"Dataset not found: {dp}");return
    with open(dp) as f:ds=json.load(f)
    llm=LLM(key=args.key)
    sd=args.dir+"/test"
    os.makedirs(sd,exist_ok=True)
    ledger=Ledger(f"{sd}/ledger.json")
    graph=ClaimGraph(f"{sd}/claims.json")
    priors=PriorLib(f"{sd}/priors.json")
    caps=CapsuleManager(llm)
    tools=ToolRegistry()
    for k,v in make_primitives(llm,ledger,graph).items():
        tools.register(k,v["fn"],v["desc"])
    register_composites(tools,llm)
    print(f"\n[1/8] Loading dataset: {dp}")
    ct=0
    for item in ds.get("observations",[]):
        o=Obs(src=item.get("src",""),content=item.get("content",""),
              mod=item.get("modality","text"),meta=item.get("meta",{}))
        if "id" in item:o.id=item["id"]
        ledger.add(o);ct+=1
    print(f"  Loaded {ct} observations")
    print(f"  Modalities: {_count_field(ledger,'mod')}")
    print(f"\n[2/8] Testing tools...")
    t_results={}
    for tn in ["search_posts","search_by_modality","timeline",
               "check_source","get_figures","search_bots",
               "claim_graph_summary","search_by_day"]:
        try:
            if tn=="search_posts":r=tools.call(tn,keyword="Arbor")
            elif tn=="search_by_modality":r=tools.call(tn,mod="x_post",limit=5)
            elif tn=="timeline":r=tools.call(tn,keyword="replication")
            elif tn=="check_source":r=tools.call(tn,src="marco_rossi")
            elif tn=="search_by_day":r=tools.call(tn,day=6)
            else:r=tools.call(tn)
            t_results[tn]="OK" if r else "EMPTY"
        except Exception as e:
            t_results[tn]=f"FAIL:{str(e)[:40]}"
    for k,v in t_results.items():
        print(f"  {k}: {v}")
    d=Dispatcher(llm,ledger,graph,priors,caps,tools)
    print(f"\n[3/8] Hypothesis generation...")
    t0=time.time()
    hyps=d.init("Were Arbor-13B's multilingual gains real or a metric artifact amplified on X?")
    print(f"  Generated {len(hyps)} hypotheses in {time.time()-t0:.1f}s")
    for h in hyps:
        print(f"    [{h.id}] {h.stmt[:80]}...")
    print(f"\n[4/8] Running {args.steps} dispatch steps (prover→breaker→auditor)...")
    t0=time.time()
    def cb(step,r):
        if r:
            hyp=d.hyps.get(r.get("hyp",""))
            status=hyp.status if hyp else "?"
            print(f"    Step {step}: {r['hyp']} ({status}) via {r['branch']}")
    d.run(max_steps=args.steps,callback=cb)
    dt=time.time()-t0
    print(f"  Completed in {dt:.1f}s")
    print(f"\n[5/8] Checking claim graph & evidence...")
    print(f"  Claims: {len(graph)}")
    print(f"  Claim status: {graph.summary()}")
    print(f"  Observations: {len(ledger)}")
    agent_obs=[o for o in ledger.obs.values()
               if o.meta.get("role") in ("supporting_evidence","counterevidence")]
    print(f"  Agent-generated evidence: {len(agent_obs)}")
    print(f"\n[6/8] Checking capsules & priors...")
    branches=caps.all_branches()
    print(f"  Branches: {len(branches)}")
    for b in branches:
        h=d.hyps.get(b.hyp_id)
        hs=h.status if h else "?"
        print(f"    [{b.id}] hyp={b.hyp_id} status={hs} "
              f"sup={len(b.sup)} con={len(b.con)} conf={b.conf:.2f}")
    proved=[h for h in d.hyps.values() if h.status=="proved"]
    broken=[h for h in d.hyps.values() if h.status=="broken"]
    open_h=[h for h in d.hyps.values() if h.status in ("open","proving")]
    print(f"  Proved: {len(proved)}, Broken: {len(broken)}, Open: {len(open_h)}")
    for h in proved:
        p=d.promote_prior(h.id)
        if p:print(f"  Promoted prior: [{p.id}] {p.stmt[:60]}")
    print(f"  Active priors: {len(priors.active())}")
    print(f"\n[7/8] Synthesis report...")
    t0=time.time()
    report=d.synthesize()
    print(f"  Generated in {time.time()-t0:.1f}s")
    for k in ["object_conclusion","narrative_conclusion","divergence","confidence"]:
        v=report.get(k,"")
        if isinstance(v,list):v="; ".join(str(x) for x in v)
        print(f"  {k}: {str(v)[:120]}")
    for k in ["top_support","top_counter","unresolved","new_priors"]:
        items=report.get(k,[])
        if items:
            print(f"  {k}:")
            for i in items[:3]:print(f"    - {str(i)[:100]}")
    print(f"\n[8/8] Persistence & memory test...")
    ledger.save();graph.save();priors.save()
    l2=Ledger(f"{sd}/ledger.json")
    g2=ClaimGraph(f"{sd}/claims.json")
    p2=PriorLib(f"{sd}/priors.json")
    print(f"  Reloaded: ledger={len(l2)}, claims={len(g2)}, priors={len(p2)}")
    assert len(l2)==len(ledger),f"Ledger mismatch: {len(l2)} vs {len(ledger)}"
    assert len(g2)==len(graph),f"Graph mismatch: {len(g2)} vs {len(graph)}"
    assert len(p2)==len(priors),f"Priors mismatch: {len(p2)} vs {len(priors)}"
    print(f"  Persistence: OK (all data round-trips)")
    u=llm.usage()
    print(f"\n{'='*60}")
    print(f"ASSESSMENT SUMMARY")
    print(f"{'='*60}")
    print(f"  Dataset loaded:     {ct} observations")
    print(f"  Tools working:      {sum(1 for v in t_results.values() if v=='OK')}/{len(t_results)}")
    print(f"  Hypotheses:         {len(d.hyps)} (proved={len(proved)}, broken={len(broken)}, open={len(open_h)})")
    print(f"  Claims generated:   {len(graph)}")
    print(f"  Evidence artifacts: {len(agent_obs)}")
    print(f"  Priors promoted:    {len(priors.active())}")
    print(f"  Branches:           {len(branches)}")
    print(f"  Persistence:        OK")
    print(f"  Report confidence:  {report.get('confidence','?')}")
    print(f"  API calls:          {u['calls']}")
    print(f"  Tokens:             {u['tok_in']:,} in / {u['tok_out']:,} out")
    print(f"  Parse success:      {u['parses_ok']} ok / {u['parses_fail']} fail")
    print(f"  Est. cost:          ${u['cost_usd']:.4f}")
    print(f"{'='*60}")

def _count_field(ledger,field):
    c={}
    for o in ledger.obs.values():
        v=getattr(o,field,"?")
        c[v]=c.get(v,0)+1
    return dict(sorted(c.items(),key=lambda x:-x[1])[:8])

if __name__=="__main__":
    main()
