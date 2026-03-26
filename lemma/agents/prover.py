import json,re
from .base import BaseAgent
from ..models import Claim,Obs

class ProverAgent(BaseAgent):
    def run(self,hyp,branch):
        session=self._repl()
        session.env["hypothesis"]=hyp.stmt
        session.env["hyp_why"]=hyp.why
        session.env["hyp_preds"]=hyp.preds
        session.env["branch_sup"]=len(branch.sup)
        session.env["branch_con"]=len(branch.con)
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
        result=session.run(f"Find evidence supporting: {hyp.stmt}",role=role,max_steps=8)
        arts=[]
        for entry in session.history:
            if entry.get("type")=="exec" and "add_claim" in entry.get("code",""):
                obs=Obs(src="prover_rlm",content=entry.get("output","")[:300],
                        meta={"role":"supporting_evidence","hyp":hyp.id})
                self.ledger.add(obs);arts.append(obs)
        new_claims=[c for c in self.graph.all_claims() if c.id not in
                    {cid for cid in branch.sup+branch.con}]
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
