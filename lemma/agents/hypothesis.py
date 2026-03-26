import json
from .base import BaseAgent
from ..models import Hyp

class HypAgent(BaseAgent):
    def run(self,conjecture):
        session=self._repl()
        session.env["conjecture"]=conjecture
        role=(
            "You are a HYPOTHESIS GENERATOR with a REPL sandbox.\n\n"
            "The conjecture is in `conjecture`. Write Python code to:\n"
            "1. Explore the data: obs_count(), search('relevant keyword'), search_mod('x_post')\n"
            "2. Check existing knowledge: priors(), claims(), match_priors(conjecture)\n"
            "3. Look at what's available: tool_list(), papers(), figures()\n"
            "4. Sample posts to understand the discourse\n"
            "5. Generate 3-7 hypotheses based on what you ACTUALLY found\n\n"
            "When ready, call FINAL with a list of hypothesis dicts:\n"
            "FINAL([{'stmt':'specific testable statement','why':'reasoning',"
            "'preds':['prediction'],'falsifiers':['what would disprove'],"
            "'tools':['tools to use']}])\n\n"
            "Each hypothesis must make DIFFERENT predictions. "
            "Ground them in real data patterns you observed.")
        result=session.run(f"Generate hypotheses for: {conjecture}",role=role,max_steps=8)
        hyps=[]
        if isinstance(result,str):
            try:result=json.loads(result)
            except:pass
        if isinstance(result,dict):result=result.get("hypotheses",result.get("theses",[result]))
        if not isinstance(result,list):result=[result]
        for h in result:
            if not isinstance(h,dict):continue
            hyps.append(Hyp(stmt=h.get("stmt",""),why=h.get("why",""),
                           preds=h.get("preds",[]),falsifiers=h.get("falsifiers",[]),
                           tools=h.get("tools",[])))
        if not hyps:
            hyps=[Hyp(stmt=conjecture,why="fallback")]
        return hyps
