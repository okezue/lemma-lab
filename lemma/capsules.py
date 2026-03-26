import time
from .models import BCap,ACap

class CapsuleManager:
    def __init__(self,llm=None):
        self.branches={};self.agenda=ACap();self.llm=llm
        self.dep_graph={}
    def create_branch(self,hyp_id):
        b=BCap(hyp_id=hyp_id)
        self.branches[b.id]=b;return b
    def get_branch(self,id):return self.branches.get(id)
    def update_branch(self,id,**kw):
        b=self.get_branch(id)
        if not b:return None
        for k,v in kw.items():
            if hasattr(b,k):setattr(b,k,v)
        return b
    def add_dep(self,branch_id,depends_on_branch):
        b=self.get_branch(branch_id)
        if b and depends_on_branch not in b.branch_deps:
            b.branch_deps.append(depends_on_branch)
        self.dep_graph.setdefault(depends_on_branch,[]).append(branch_id)
    def add_prior_dep(self,branch_id,prior_id):
        b=self.get_branch(branch_id)
        if b and prior_id not in b.depends_on_priors:
            b.depends_on_priors.append(prior_id)
    def record_belief(self,branch_id,step,conf,evidence_summary):
        b=self.get_branch(branch_id)
        if b:b.temporal_beliefs.append(
            {"step":step,"time":time.time(),"conf":conf,"evidence":evidence_summary})
    def proof_repair(self,demoted_prior_id):
        affected=[]
        for b in self.branches.values():
            if demoted_prior_id in b.depends_on_priors:
                b.conf=max(0.1,b.conf*0.5)
                b.pending.append(f"Re-evaluate: prior {demoted_prior_id} was demoted")
                b.assumptions.append(f"STALE: depended on demoted prior {demoted_prior_id}")
                affected.append(b.id)
        downstream=self.dep_graph.get(demoted_prior_id,[])
        for bid in downstream:
            b=self.get_branch(bid)
            if b:
                b.conf=max(0.1,b.conf*0.6)
                b.pending.append(f"Upstream dependency invalidated")
                if bid not in affected:affected.append(bid)
        return affected
    def branches_depending_on(self,prior_id):
        return [b for b in self.branches.values() if prior_id in b.depends_on_priors]
    def compress(self,branch_id,graph=None,ledger=None):
        b=self.get_branch(branch_id)
        if not b or not self.llm:return b
        sup_detail=""
        if graph:
            for cid in b.sup[-5:]:
                c=graph.get(cid)
                if not c:continue
                sup_detail+=f"\n  [{cid}] {c.stmt} (conf={c.conf:.2f})"
                if ledger:
                    for oid in c.src_obs[:2]:
                        o=ledger.get(oid)
                        if o:sup_detail+=f"\n    evidence: [{o.src}] {o.content[:150]}"
        con_detail=""
        if graph:
            for cid in b.con[-5:]:
                c=graph.get(cid)
                if not c:continue
                con_detail+=f"\n  [{cid}] {c.stmt} (conf={c.conf:.2f})"
                if ledger:
                    for oid in c.src_obs[:2]:
                        o=ledger.get(oid)
                        if o:con_detail+=f"\n    evidence: [{o.src}] {o.content[:150]}"
        ctx=(f"Hypothesis: {b.hyp_id}\n"
             f"Confidence: {b.conf:.2f}\n"
             f"Supporting claims ({len(b.sup)}):{sup_detail}\n"
             f"Contradicting ({len(b.con)}):{con_detail}\n"
             f"Assumptions: {b.assumptions}\n"
             f"Pending: {b.pending}\n"
             f"Prior deps: {b.depends_on_priors}\n"
             f"Branch deps: {b.branch_deps}\n"
             f"Belief trajectory: {[(t['step'],t['conf']) for t in b.temporal_beliefs[-5:]]}")
        r=self.llm.ask(
            f"Compress this research branch. PRESERVE:\n"
            f"- Key evidence sources and what they said\n"
            f"- Open questions and unresolved tensions\n"
            f"- Dependencies on priors/branches that might change\n"
            f"- What should happen next to discriminate\n\n{ctx}",role="fast")
        b.next_act=r[:800]
        return b
    def refresh_agenda(self,hyps=None):
        active=[b.id for b in self.branches.values() if b.conf>0.2]
        stalled=[b.id for b in self.branches.values()
                 if not b.pending and b.conf<0.5]
        tensions=[]
        for b in self.branches.values():
            if b.sup and b.con:
                tensions.append((b.id,f"{len(b.sup)}sup/{len(b.con)}con"))
        stale_deps=[]
        for b in self.branches.values():
            if any("STALE" in a for a in b.assumptions):
                stale_deps.append(b.id)
        self.agenda=ACap(active=active,stalled=stalled,tensions=tensions,
                        next_exp=stale_deps)
        return self.agenda
    def get_context(self,branch_id=None):
        if branch_id:
            b=self.get_branch(branch_id)
            if b:return b.to_dict()
        return self.agenda.to_dict()
    def all_branches(self):return list(self.branches.values())
    def summary(self):
        return (f"Branches: {len(self.branches)}, "
                f"Active: {len(self.agenda.active)}, "
                f"Stalled: {len(self.agenda.stalled)}")
