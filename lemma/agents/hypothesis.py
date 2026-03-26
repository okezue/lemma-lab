import json
from .base import BaseAgent
from ..models import Hyp

class HypAgent(BaseAgent):
    def run(self,conjecture):
        data_ctx=self._scan_available_data()
        sys=self._sys(
            "You generate research hypotheses. Given a conjecture, available data, "
            "and priors, propose 3-7 candidate hypotheses. Each needs: statement, "
            "reasoning, testable predictions, falsifiers, and tools needed. "
            "Make hypotheses specific and discriminating - each should make "
            "different predictions about what the evidence will show.")
        claims=self._claims_ctx()
        prompt=(
            f"Conjecture: {conjecture}\n\n"
            f"Available data in the system:\n{data_ctx}\n\n"
            f"Existing claims:\n{claims}\n\n"
            f"Available tools: {self._tool_list()}\n\n"
            f"Propose 3-7 hypotheses as JSON:\n"
            f'{{"hypotheses":[{{"stmt":"specific testable statement",'
            f'"why":"reasoning for why this might be true",'
            f'"preds":["prediction 1","prediction 2"],'
            f'"falsifiers":["what would disprove this"],'
            f'"tools":["tools to use"]}}]}}')
        r=self.llm.structured(f"{sys}\n\n{prompt}",
                              {"type":"object"},role="strong")
        hs=r.get("hypotheses",r if isinstance(r,list) else [r])
        if not isinstance(hs,list):hs=[hs]
        hyps=[]
        for h in hs:
            hyp=Hyp(stmt=h.get("stmt",""),why=h.get("why",""),
                    preds=h.get("preds",[]),falsifiers=h.get("falsifiers",[]),
                    tools=h.get("tools",[]))
            hyps.append(hyp)
        return hyps

    def _scan_available_data(self):
        parts=[]
        if self.ledger:
            n=len(self.ledger)
            if n>0:
                mods={}
                srcs={}
                for o in list(self.ledger.obs.values())[:200]:
                    mods[o.mod]=mods.get(o.mod,0)+1
                    srcs[o.src]=srcs.get(o.src,0)+1
                parts.append(f"Observations: {n}")
                parts.append(f"  Modalities: {dict(sorted(mods.items(),key=lambda x:-x[1])[:10])}")
                parts.append(f"  Top sources: {dict(sorted(srcs.items(),key=lambda x:-x[1])[:10])}")
                samples=list(self.ledger.obs.values())[:5]
                for s in samples:
                    parts.append(f"  Sample [{s.src}] ({s.mod}): {s.content[:100]}...")
        if self.graph and len(self.graph)>0:
            parts.append(f"Claims: {len(self.graph)}")
        return "\n".join(parts) if parts else "(no data loaded yet)"

    def _tool_list(self):
        if not self.tools:return "none"
        return ", ".join(self.tools.list_tools())
