import json,re
from .base import BaseAgent
from ..models import Claim,Obs

class BreakerAgent(BaseAgent):
    def run(self,hyp,branch):
        session=self._repl()
        session.env["hypothesis"]=hyp.stmt
        session.env["falsifiers"]=hyp.falsifiers
        session.env["branch_sup"]=len(branch.sup)
        session.env["branch_con"]=len(branch.con)
        session.env["assumptions"]=branch.assumptions
        role=(
            "You are a BREAKER agent with a REPL sandbox. Your goal is to "
            "CHALLENGE and FALSIFY the hypothesis in `hypothesis`.\n\n"
            "Falsifiers to test: check `falsifiers` variable.\n\n"
            "Write Python code to:\n"
            "1. Search for counterevidence (search('replication'), search('failure'), search('excluded'), etc)\n"
            "2. Check source credibility of supporting claims\n"
            "3. Look for bot amplification: get_bots()\n"
            "4. Search for errata, replication reports: search_mod('errata'), papers('replication_report')\n"
            "5. Analyze figure misreadings: figures()\n"
            "6. Store findings: store('counter_evidence', [...]) \n"
            "7. Create counterevidence claims: add_claim(stmt, conf)\n"
            "8. Link contradictions: link_claims(new_id, existing_id, 'contradict')\n"
            "9. FINAL({'smuggled_assumptions': [...], 'alternative_explanations': [...]})\n\n"
            "Look for: alternative explanations, source credibility issues, "
            "sarcasm misreads, chronology problems, smuggled assumptions.")
        result=session.run(f"Break this hypothesis: {hyp.stmt}",role=role,max_steps=8)
        arts=[]
        for entry in session.history:
            if entry.get("type")=="exec" and "add_claim" in entry.get("code",""):
                obs=Obs(src="breaker_rlm",content=entry.get("output","")[:300],
                        meta={"role":"counterevidence","hyp":hyp.id})
                self.ledger.add(obs);arts.append(obs)
        new_claims=[c for c in self.graph.all_claims() if c.id not in
                    {cid for cid in branch.sup+branch.con}]
        for c in new_claims[-5:]:
            branch.con.append(c.id);arts.append(c)
        if isinstance(result,dict):
            branch.assumptions=result.get("smuggled_assumptions",branch.assumptions)
        elif isinstance(result,str):
            try:
                d=json.loads(result)
                branch.assumptions=d.get("smuggled_assumptions",branch.assumptions)
            except:pass
        return arts
