import json
from .base import BaseAgent
from ..models import Claim,Obs

class BreakerAgent(BaseAgent):
    def run(self,hyp,branch):
        counter_ev=self._search_counterevidence(hyp)
        source_checks=self._check_sources(branch)
        all_ev=counter_ev+source_checks
        arts=self._analyze_against(hyp,branch,all_ev)
        return arts
    def _search_counterevidence(self,hyp):
        ev=[]
        kws=self._counter_keywords(hyp)
        for kw in kws[:5]:
            if self.tools and self.tools.has("search_posts"):
                r=self.tools.call("search_posts",keyword=kw)
                if isinstance(r,list):ev.extend(r[:8])
        if self.tools:
            for mod in ["errata","replication_report","figure_desc"]:
                if self.tools.has("search_by_modality"):
                    r=self.tools.call("search_by_modality",mod=mod)
                    if isinstance(r,list):ev.extend(r[:5])
            if self.tools.has("fetch_paper_content"):
                r=self.tools.call("fetch_paper_content",paper_type="errata")
                if isinstance(r,list):ev.extend(r[:3])
            if self.tools.has("search_bots"):
                r=self.tools.call("search_bots")
                if isinstance(r,list):ev.extend(r[:5])
        return ev
    def _counter_keywords(self,hyp):
        base=["replication","failure","excluded","missing","bias",
              "inflated","cropped","misleading","error","retraction",
              "incorrect","overstate","artifact","contamination"]
        stmt_words=[w.lower().strip(".,!?") for w in hyp.stmt.split() if len(w)>4]
        return base[:6]+stmt_words[:4]
    def _check_sources(self,branch):
        checks=[]
        if not self.tools or not self.tools.has("check_source"):return checks
        sources_seen=set()
        for cid in branch.sup[:5]:
            c=self.graph.get(cid)
            if c:
                for oid in c.src_obs[:2]:
                    o=self.ledger.get(oid)
                    if o and o.src not in sources_seen:
                        sources_seen.add(o.src)
                        r=self.tools.call("check_source",src=o.src)
                        if isinstance(r,dict):checks.append(r)
        return checks
    def _analyze_against(self,hyp,branch,evidence):
        ev_text=[]
        for e in evidence[:20]:
            if isinstance(e,dict):
                c=e.get("content",e.get("preview",json.dumps(e)[:200]))
                s=e.get("src",e.get("source","unknown"))
                ev_text.append(f"[{s}] {str(c)[:200]}")
        ev_block="\n".join(ev_text) if ev_text else "(no counter-evidence found)"
        claims_ctx=self._claims_ctx()
        sys=self._sys(
            "You are a breaker agent. CHALLENGE the hypothesis using real evidence. "
            "Check existing claims to avoid duplicates and find contradictions.")
        prompt=(
            f"Hypothesis to break: {hyp.stmt}\n"
            f"Current support claims: {len(branch.sup)}\n"
            f"Falsifiers to test: {hyp.falsifiers}\n\n"
            f"Existing claims:\n{claims_ctx}\n\n"
            f"Counter-evidence ({len(evidence)} items):\n{ev_block}\n\n"
            f"What undermines this hypothesis?\n"
            f"Return JSON:\n"
            f'{{"counterevidence":[{{"content":"what was found",'
            f'"source":"who/where","damage":0.7,"reasoning":"why it hurts"}}],'
            f'"alternative_explanations":["..."],'
            f'"smuggled_assumptions":["..."],'
            f'"claims":[{{"stmt":"...","confidence":0.6,'
            f'"contradicts_claims":["existing claim IDs this contradicts"]}}]}}')
        r=self.llm.structured(f"{sys}\n\n{prompt}",{"type":"object"},role="fast")
        arts=[]
        for ce in r.get("counterevidence",[]):
            obs=Obs(src=ce.get("source","breaker"),content=ce.get("content",""),
                    meta={"role":"counterevidence","hyp":hyp.id,
                          "damage":ce.get("damage",0.5),
                          "reasoning":ce.get("reasoning","")})
            self.ledger.add(obs);arts.append(obs)
        for c in r.get("claims",[]):
            cl=Claim(stmt=c.get("stmt",""),conf=c.get("confidence",0.5))
            self.graph.add(cl);branch.con.append(cl.id);arts.append(cl)
            for cid in c.get("contradicts_claims",[]):
                if self.graph.get(cid):self.graph.link(cl.id,cid,"contradict")
        branch.assumptions=r.get("smuggled_assumptions",[])
        return arts
