import json,re
from .base import BaseAgent
from ..models import Claim,Obs

class ProverAgent(BaseAgent):
    def run(self,hyp,branch):
        session=self._repl()
        session.locals["hypothesis"]=hyp.stmt
        session.locals["hyp_why"]=hyp.why
        session.locals["hyp_preds"]=hyp.preds
        session.locals["branch_sup"]=len(branch.sup)
        session.locals["branch_con"]=len(branch.con)
        role=(
            "You are a PROVER agent with a REPL sandbox. Your goal is to find "
            "evidence SUPPORTING the hypothesis stored in `hypothesis`.\n\n"
            "You have the full research API. Write Python code to:\n"
            "1. Search the corpus for relevant evidence (search, search_mod, timeline, papers, figures)\n"
            "2. Store interesting findings: store('key', value)\n"
            "3. Analyze what you find with llm_ask() or llm_json()\n"
            "4. Create claims from real evidence: add_claim(stmt, conf, [obs_ids])\n"
            "5. Link claims: link_claims(new_id, existing_id, 'support')\n"
            "6. When done, call FINAL({'claims': [...], 'next_actions': [...]})\n\n"
            "IMPORTANT: Only cite evidence that exists in the data. "
            "Check existing claims() to avoid duplicates. "
            "Keep your root context small — offload search results to variables.")
        pre_claims=set(c.id for c in self.graph.all_claims())
        result=session.run(f"Find evidence supporting: {hyp.stmt}",role=role,max_steps=8)
        arts=[]
        for it in session.iterations:
            for cb in it.code_blocks:
                if cb.result and cb.result.stdout:
                    obs=Obs(src="prover_rlm",content=cb.result.stdout[:300],
                            meta={"role":"supporting_evidence","hyp":hyp.id,
                                  "code":cb.code[:200]})
                    self.ledger.add(obs);arts.append(obs)
        new_claims=[c for c in self.graph.all_claims() if c.id not in pre_claims
                    and c.id not in {cid for cid in branch.sup+branch.con}]
        for c in new_claims[-5:]:
            branch.sup.append(c.id);arts.append(c)
        if isinstance(result,dict):
            branch.pending=result.get("next_actions",[])[:3]
        elif isinstance(result,str):
            try:
                d=json.loads(result)
                branch.pending=d.get("next_actions",[])[:3]
            except:pass
        return arts
