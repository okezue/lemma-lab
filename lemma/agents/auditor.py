import json
from .base import BaseAgent
from ..models import ANote

class AuditorAgent(BaseAgent):
    def run(self,branch,hyp):
        sup_detail=self._get_claim_details(branch.sup)
        con_detail=self._get_claim_details(branch.con)
        source_analysis=self._audit_sources(branch)
        sys=self._sys(
            "You are an auditor. Check whether a research branch actually "
            "earned its conclusion based on REAL evidence. Check: "
            "citation quality, evidence strength, ignored contradictions, "
            "source credibility, logical gaps, overstatement.")
        prompt=(
            f"Branch {branch.id} for hypothesis: {hyp.stmt}\n\n"
            f"Supporting claims ({len(branch.sup)}):\n{sup_detail}\n\n"
            f"Contradicting claims ({len(branch.con)}):\n{con_detail}\n\n"
            f"Source credibility checks:\n{source_analysis}\n\n"
            f"Assumptions identified: {branch.assumptions}\n"
            f"Confidence: {branch.conf}\n\n"
            f"Audit this branch rigorously. Return JSON:\n"
            f'{{"verdict":"pass|warn|fail",'
            f'"issues":["specific issue 1","specific issue 2"],'
            f'"overstatements":["where evidence is overstated"],'
            f'"ignored_contradictions":["contradictions not addressed"],'
            f'"recommendation":"what should happen next"}}')
        r=self.llm.structured(f"{sys}\n\n{prompt}",{"type":"object"},role="fast")
        v=r.get("verdict","warn")
        if v not in ("pass","warn","fail"):v="warn"
        issues=r.get("issues",[])+r.get("overstatements",[])
        return ANote(target=branch.id,verdict=v,issues=issues)

    def _get_claim_details(self,claim_ids):
        details=[]
        for cid in claim_ids[:10]:
            c=self.graph.get(cid)
            if c:
                obs_preview=""
                for oid in c.src_obs[:2]:
                    o=self.ledger.get(oid)
                    if o:obs_preview+=f" [from {o.src}: {o.content[:80]}]"
                try:cf=float(c.conf)
                except:cf=0.5
                details.append(f"  [{c.id}] (conf={cf:.2f}) {c.stmt}{obs_preview}")
        return "\n".join(details) if details else "(none)"

    def _audit_sources(self,branch):
        if not self.tools:return "(no tools available)"
        sources=set()
        for cid in branch.sup+branch.con:
            c=self.graph.get(cid)
            if c:
                for oid in c.src_obs[:2]:
                    o=self.ledger.get(oid)
                    if o:sources.add(o.src)
        checks=[]
        for src in list(sources)[:8]:
            r=self.tools.call("check_source",src=src)
            if isinstance(r,dict):
                checks.append(f"  {src}: {r.get('count',0)} observations")
        return "\n".join(checks) if checks else "(no sources to check)"
