import time,json
from .models import Hyp,BCap
from .agents.hypothesis import HypAgent
from .agents.prover import ProverAgent
from .agents.breaker import BreakerAgent
from .agents.scout import ScoutAgent
from .agents.auditor import AuditorAgent
from .agents.toolsmith import ToolsmithAgent
from .agents.synthesizer import SynthAgent
from .agents.prior_editor import PriorEditorAgent
from .agents.analyst import AnalystAgent

class Dispatcher:
    def __init__(self,llm,ledger,graph,priors,capsules,tools):
        self.llm=llm;self.ledger=ledger;self.graph=graph
        self.priors=priors;self.caps=capsules;self.tools=tools
        self.hyps={};self.conjecture="";self.step_n=0;self.log=[]
        self.step_metrics=[]
        self.prior_promotions=[]
        self.proof_repairs=[]
        kw=dict(llm=llm,ledger=ledger,graph=graph,priors=priors,
                capsules=capsules,tools=tools)
        self.agents={
            "hyp":HypAgent(**kw),"prover":ProverAgent(**kw),
            "breaker":BreakerAgent(**kw),"scout":ScoutAgent(**kw),
            "auditor":AuditorAgent(**kw),"toolsmith":ToolsmithAgent(**kw),
            "synth":SynthAgent(**kw),
            "prior_editor":PriorEditorAgent(**kw),
            "analyst":AnalystAgent(**kw)}

    def init(self,conjecture):
        self.conjecture=conjecture;self.step_n=0
        self._log(f"Conjecture: {conjecture}")
        hyps=self.agents["hyp"].run(conjecture)
        for i,h in enumerate(hyps):
            self.hyps[h.id]=h
            b=self.caps.create_branch(h.id)
            for prior in self.priors.match(h.stmt,3):
                self.caps.add_prior_dep(b.id,prior.id)
                h.prior_deps.append(prior.id)
            for j,h2 in enumerate(hyps[:i]):
                shared=set(h.stmt.lower().split())&set(h2.stmt.lower().split())
                if len(shared)>5:
                    b2=[x for x in self.caps.all_branches() if x.hyp_id==h2.id]
                    if b2:self.caps.add_dep(b.id,b2[0].id)
            self._log(f"  {h.id}: {h.stmt[:80]} -> {b.id}")
        return hyps

    def score_branches(self):
        scores={}
        for b in self.caps.all_branches():
            h=self.hyps.get(b.hyp_id)
            if not h or h.status in ("proved","broken"):continue
            ig=len(b.pending)*0.3+abs(0.5-b.conf)*0.5
            dc=len(b.sup)+len(b.con)
            stale_boost=1.5 if any("STALE" in a for a in b.assumptions) else 1.0
            dep_penalty=0.9**len(b.branch_deps)
            scores[b.id]=ig*(1+dc*0.1)*stale_boost*dep_penalty
        return dict(sorted(scores.items(),key=lambda x:-x[1]))

    def step(self):
        self.step_n+=1
        t0=time.time()
        scores=self.score_branches()
        if not scores:
            self._log("No active branches");return None
        bid=next(iter(scores))
        branch=self.caps.get_branch(bid)
        hyp=self.hyps.get(branch.hyp_id)
        if not hyp:return None
        self._log(f"Step {self.step_n}: {bid} (hyp={hyp.id}, score={scores[bid]:.2f})")
        hyp.status="proving"
        pa=self.agents["prover"].run(hyp,branch)
        self._log(f"  Prover: {len(pa)} artifacts")
        ba=self.agents["breaker"].run(hyp,branch)
        self._log(f"  Breaker: {len(ba)} artifacts")
        figs=self.tools.call("get_figures") if self.tools else []
        if isinstance(figs,list) and figs and self.step_n<=2:
            for fig in figs[:2]:
                fc=fig.get("content","")
                if fc:
                    arts=self.agents["scout"].run(fc,"figure_desc")
                    self._log(f"  Scout: {len(arts)} artifacts from figure")
        self.graph.update_conf()
        ns,nc=len(branch.sup),len(branch.con)
        branch.conf=ns/(ns+nc) if ns+nc>0 else 0.5
        evidence_sum=f"sup={ns},con={nc},claims={len(self.graph)}"
        self.caps.record_belief(bid,self.step_n,branch.conf,evidence_sum)
        note=self.agents["auditor"].run(branch,hyp)
        self._log(f"  Audit: {note.verdict} ({len(note.issues)} issues)")
        if note.verdict=="pass" and branch.conf>0.7:
            hyp.status="proved";hyp.conf=branch.conf
            self._log(f"  PROVED: {hyp.stmt[:60]}")
            p=self.promote_prior(hyp.id)
            if p:self._log(f"  Auto-promoted prior: {p.id}")
        elif note.verdict=="fail" or branch.conf<0.2:
            hyp.status="broken";hyp.conf=branch.conf
            self._log(f"  BROKEN: {hyp.stmt[:60]}")
        self.caps.compress(bid,self.graph,self.ledger)
        self.caps.refresh_agenda()
        if self.step_n%2==0:
            traces=self.tools.get_traces() if self.tools else []
            if traces:
                recipes=self.agents["toolsmith"].run(traces)
                for r in recipes:
                    self._log(f"  Toolsmith: {r.name}")
                    self.agents["toolsmith"].make_executable(r,self.tools)
        if self.step_n%3==0:
            edits=self.agents["prior_editor"].run(trigger=f"step_{self.step_n}")
            for e in edits:
                self._log(f"  Prior edit: {e.get('action','')} {e.get('prior','')[:20]} — {e.get('reason','')[:40]}")
                if e.get("action")=="demoted":
                    self.demote_prior(e["prior"])
        dt=time.time()-t0
        sm={"step":self.step_n,"branch":bid,"hyp":hyp.id,
            "hyp_status":hyp.status,"branch_conf":branch.conf,
            "sup":ns,"con":nc,"claims":len(self.graph),
            "priors":len(self.priors),"observations":len(self.ledger),
            "audit_verdict":note.verdict,"audit_issues":len(note.issues),
            "artifacts_found":len(pa)+len(ba),
            "time":round(dt,2),"cost":self.llm.usage()["cost_usd"]}
        self.step_metrics.append(sm)
        return sm

    def run(self,max_steps=10,callback=None):
        for _ in range(max_steps):
            r=self.step()
            if callback:callback(self.step_n,r)
            if not r:break
            active=[h for h in self.hyps.values() if h.status in ("open","proving")]
            if not active:break
        return self.status()

    def synthesize(self):
        return self.agents["synth"].run(
            self.conjecture,list(self.hyps.values()),self.caps.all_branches())

    def promote_prior(self,hyp_id):
        h=self.hyps.get(hyp_id)
        if not h:return None
        p=self.priors.promote(h.stmt,evidence=h.sup)
        self.prior_promotions.append({"hyp":hyp_id,"prior":p.id,"step":self.step_n})
        branches=self.caps.all_branches()
        for b in branches:
            if b.hyp_id!=hyp_id and h.stmt[:30].lower() in " ".join(
                    [self.hyps.get(b.hyp_id,Hyp()).stmt.lower()]):
                self.caps.add_prior_dep(b.id,p.id)
        return p

    def demote_prior(self,prior_id):
        ok=self.priors.demote(prior_id)
        if not ok:return []
        stale_claims=self.graph.stale_from(prior_id)
        affected_branches=self.caps.proof_repair(prior_id)
        self.proof_repairs.append({"prior":prior_id,"step":self.step_n,
                                   "stale_claims":len(stale_claims),
                                   "affected_branches":affected_branches})
        self._log(f"  PROOF REPAIR: demoted {prior_id}, "
                  f"{len(stale_claims)} stale claims, "
                  f"{len(affected_branches)} branches reopened")
        return affected_branches

    def spawn(self,stmt):
        h=Hyp(stmt=stmt)
        self.hyps[h.id]=h
        b=self.caps.create_branch(h.id)
        for prior in self.priors.match(stmt,3):
            self.caps.add_prior_dep(b.id,prior.id)
        self._log(f"Spawned {h.id}: {stmt[:60]}")
        return h,b

    def challenge(self,hyp_id):
        h=self.hyps.get(hyp_id)
        if not h:return None
        bs=[b for b in self.caps.all_branches() if b.hyp_id==hyp_id]
        if not bs:return None
        return self.agents["breaker"].run(h,bs[0])

    def temporal_snapshot(self,at_step=None):
        if at_step is None:at_step=self.step_n
        beliefs={}
        for b in self.caps.all_branches():
            h=self.hyps.get(b.hyp_id)
            if not h:continue
            tb=[t for t in b.temporal_beliefs if t["step"]<=at_step]
            beliefs[h.id]={"stmt":h.stmt[:80],
                          "status":h.status if at_step>=self.step_n else "in_progress",
                          "conf_at_step":tb[-1]["conf"] if tb else 0.5,
                          "evidence_at_step":tb[-1]["evidence"] if tb else "",
                          "belief_trajectory":[{"step":t["step"],"conf":t["conf"]}
                                               for t in tb]}
        return {"at_step":at_step,"beliefs":beliefs,
                "claims_at_step":len([c for c in self.graph.all_claims()]),
                "priors_at_step":len(self.priors.active())}

    def status(self):
        hs={h.id:{"stmt":h.stmt[:80],"status":h.status,"conf":h.conf}
            for h in self.hyps.values()}
        bs={b.id:{"hyp":b.hyp_id,"sup":len(b.sup),"con":len(b.con),
                  "conf":b.conf,"deps":b.branch_deps,"prior_deps":b.depends_on_priors,
                  "beliefs":len(b.temporal_beliefs)}
            for b in self.caps.all_branches()}
        return {"step":self.step_n,"hypotheses":hs,"branches":bs,
                "claims":len(self.graph),"priors":len(self.priors),
                "observations":len(self.ledger),
                "step_metrics":self.step_metrics,
                "prior_promotions":self.prior_promotions,
                "proof_repairs":self.proof_repairs}

    def _log(self,msg):
        self.log.append({"t":time.time(),"step":self.step_n,"msg":msg})
        print(f"[LEMMA] {msg}")
