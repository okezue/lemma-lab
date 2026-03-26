import json
from .base import BaseAgent
from ..models import Obs,Claim

class ScoutAgent(BaseAgent):
    def run(self,artifact,artifact_type="image"):
        sys=self._sys(
            "You are a multimodal scout. Inspect this artifact WITHOUT surrounding "
            "narrative. Report what you observe: entities, text, data, axes, claims, "
            "uncertainties, potential misreadings. Use your prior knowledge to identify "
            "known patterns but don't let priors bias your raw observation.")
        schema=('Return JSON: {"entities":[],"text_extracted":"","likely_claim":"",'
                '"uncertainty":"","potential_misreadings":[],"axes_labels":[],'
                '"data_values":{},"conflicts_with_priors":[]}')
        if artifact_type=="image" and self.llm:
            try:
                r=self.llm.vision(f"{sys}\n\n{schema}",[artifact])
                d=json.loads(r)
            except:
                d={"text_extracted":"[vision parse failed]","uncertainty":"high",
                   "entities":[],"potential_misreadings":[]}
        else:
            r=self.llm.ask(f"{sys}\n\nArtifact:\n{artifact}\n\n{schema}",role="fast")
            try:d=json.loads(r)
            except:d={"text_extracted":str(r)[:500],"uncertainty":"high",
                       "entities":[],"potential_misreadings":[]}
        obs=Obs(src="scout",content=json.dumps(d,ensure_ascii=False)[:500],
                mod=artifact_type,meta=d)
        self.ledger.add(obs)
        results=[obs]
        if d.get("likely_claim"):
            cl=Claim(stmt=d["likely_claim"],conf=0.4,src_obs=[obs.id])
            self.graph.add(cl)
            results.append(cl)
        for mr in d.get("potential_misreadings",[]):
            if isinstance(mr,str) and len(mr)>10:
                cl=Claim(stmt=f"Potential misreading: {mr}",conf=0.3,src_obs=[obs.id])
                self.graph.add(cl)
                results.append(cl)
        return results
