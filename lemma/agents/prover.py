import json
from .base import BaseAgent
from ..models import Claim,Obs

class ProverAgent(BaseAgent):
    def run(self,hyp,branch):
        plan=self._plan_searches(hyp)
        evidence=[]
        for action in plan:
            results=self._execute_search(action)
            evidence.extend(results)
        arts=self._analyze_evidence(hyp,branch,evidence)
        return arts
    def _plan_searches(self,hyp):
        kws=self._extract_keywords(hyp.stmt+" "+hyp.why)
        plan=[]
        for kw in kws[:5]:
            plan.append({"tool":"search_posts","args":{"keyword":kw}})
        plan.append({"tool":"search_by_modality","args":{"mod":"paper_abstract"}})
        plan.append({"tool":"search_by_modality","args":{"mod":"paper_appendix"}})
        plan.append({"tool":"search_by_modality","args":{"mod":"replication_report"}})
        plan.append({"tool":"fetch_paper_content","args":{"paper_type":"paper_abstract"}})
        plan.append({"tool":"fetch_figure_content","args":{"figure_id":""}})
        return plan
    def _extract_keywords(self,text):
        stops={"the","a","an","is","was","are","were","be","been","being",
               "have","has","had","do","does","did","will","would","could",
               "should","may","might","can","shall","to","of","in","for",
               "on","with","at","by","from","as","into","about","between",
               "through","after","before","during","that","this","it","its",
               "and","or","but","not","no","nor","if","then","than","so",
               "very","just","more","most","also","only","both","each",
               "other","some","such","own","same","all","any","few"}
        words=[w.strip(".,!?\"'()[]{}").lower() for w in text.split()]
        return [w for w in words if len(w)>3 and w not in stops][:8]
    def _execute_search(self,action):
        if not self.tools or not self.tools.has(action["tool"]):return []
        try:
            r=self.tools.call(action["tool"],**action["args"])
            if isinstance(r,list):return r[:10]
            if isinstance(r,dict) and "error" not in r:return [r]
        except:pass
        return []
    def _analyze_evidence(self,hyp,branch,evidence):
        if not evidence:return self._fallback_reason(hyp,branch)
        ev_text=[]
        for e in evidence[:15]:
            if isinstance(e,dict):
                c=e.get("content",e.get("preview",e.get("data",json.dumps(e)[:200])))
                s=e.get("src","unknown")
                ev_text.append(f"[{s}] {str(c)[:200]}")
        ev_block="\n".join(ev_text)
        claims_ctx=self._claims_ctx()
        sys=self._sys(
            "You are a prover agent. Analyze REAL evidence from the dataset "
            "to support the hypothesis. Only cite evidence that actually exists. "
            "Check existing claims to avoid duplicates.")
        prompt=(
            f"Hypothesis: {hyp.stmt}\n\n"
            f"Existing claims in graph:\n{claims_ctx}\n\n"
            f"Evidence found ({len(evidence)} items):\n{ev_block}\n\n"
            f"Which items support the hypothesis? Avoid duplicating existing claims.\n"
            f"Return JSON:\n"
            f'{{"supporting_evidence":[{{"observation":"what was found",'
            f'"source":"who said it","how_it_supports":"reasoning",'
            f'"confidence":0.7}}],'
            f'"claims":[{{"stmt":"normalized claim","confidence":0.7,'
            f'"supports_claims":["existing claim IDs this supports"],'
            f'"contradicts_claims":["existing claim IDs this contradicts"]}}],'
            f'"next_actions":["what else to search"]}}')
        r=self.llm.structured(f"{sys}\n\n{prompt}",{"type":"object"},role="fast")
        arts=[]
        for se in r.get("supporting_evidence",[]):
            obs=Obs(src=se.get("source","prover"),content=se.get("observation",""),
                    meta={"role":"supporting_evidence","hyp":hyp.id,
                          "confidence":se.get("confidence",0.5),
                          "reasoning":se.get("how_it_supports","")})
            self.ledger.add(obs);arts.append(obs)
        for c in r.get("claims",[]):
            cl=Claim(stmt=c.get("stmt",""),conf=c.get("confidence",0.5),
                     src_obs=[a.id for a in arts if isinstance(a,Obs)])
            self.graph.add(cl);branch.sup.append(cl.id);arts.append(cl)
            for sid in c.get("supports_claims",[]):
                if self.graph.get(sid):self.graph.link(cl.id,sid,"support")
            for cid in c.get("contradicts_claims",[]):
                if self.graph.get(cid):self.graph.link(cl.id,cid,"contradict")
        branch.pending=r.get("next_actions",[])[:3]
        return arts
    def _fallback_reason(self,hyp,branch):
        sys=self._sys("You are a prover. No dataset evidence found. "
                      "Reason about what WOULD support this hypothesis.")
        prompt=(f"Hypothesis: {hyp.stmt}\n"
                f"Existing claims:\n{self._claims_ctx()}\n"
                f"No direct evidence found. What claims can be inferred?\n"
                f'Return JSON: {{"claims":[{{"stmt":"...","confidence":0.3}}]}}')
        r=self.llm.structured(f"{sys}\n\n{prompt}",{"type":"object"},role="fast")
        arts=[]
        for c in r.get("claims",[]):
            cl=Claim(stmt=c.get("stmt",""),conf=min(c.get("confidence",0.3),0.4))
            self.graph.add(cl);branch.sup.append(cl.id);arts.append(cl)
        return arts
