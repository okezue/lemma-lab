import json
from .base import BaseAgent
from ..models import Prior,APrior

class PriorEditorAgent(BaseAgent):
    def run(self,trigger="periodic"):
        active=self.priors.active()
        claims_ctx=self._claims_ctx(20)
        recent_obs=self._obs_sample(10)
        prior_text="\n".join(f"[{p.id}] ({p.type}) stmt={p.stmt} "
                            f"scope={p.scope} xfer={p.xfer} "
                            f"evidence={p.evidence[:3]} cex={p.cex[:3]}"
                            for p in active) if active else "(no priors)"
        anti_text="\n".join(f"[{a.id}] {a.stmt} why={a.why}"
                           for a in self.priors.anti.values()) if self.priors.anti else "(none)"
        sys=self._sys(
            "You are a prior editor. You review the system's accumulated priors "
            "(reusable research beliefs) against current evidence. You can: "
            "STRENGTHEN priors with new evidence, WEAKEN priors that have counterexamples, "
            "CREATE new priors from stable patterns, DEMOTE priors that are wrong, "
            "and CREATE anti-priors (warnings about cognitive traps).")
        prompt=(
            f"Trigger: {trigger}\n\n"
            f"Active priors:\n{prior_text}\n\n"
            f"Anti-priors:\n{anti_text}\n\n"
            f"Current claim graph:\n{claims_ctx}\n\n"
            f"Recent observations:\n{recent_obs}\n\n"
            f"Review the priors. Return JSON:\n"
            f'{{"actions":[{{"type":"strengthen|weaken|create|demote|anti_prior",'
            f'"prior_id":"existing id or empty for create",'
            f'"stmt":"statement for create/anti_prior",'
            f'"reason":"why this action",'
            f'"evidence":["claim or observation IDs supporting this"],'
            f'"new_xfer":0.7,'
            f'"scope":"when this applies"}}]}}')
        r=self.llm.structured(f"{sys}\n\n{prompt}",{"type":"object"},role="strong")
        results=[]
        for a in r.get("actions",[]):
            act=a.get("type","")
            pid=a.get("prior_id","")
            if act=="strengthen" and pid:
                p=self.priors.get(pid)
                if p:
                    p.xfer=min(1.0,p.xfer+0.1)
                    new_ev=a.get("evidence",[])
                    p.evidence.extend(new_ev)
                    results.append({"action":"strengthened","prior":pid,
                                   "new_xfer":p.xfer,"reason":a.get("reason","")})
            elif act=="weaken" and pid:
                p=self.priors.get(pid)
                if p:
                    p.xfer=max(0.1,p.xfer-0.15)
                    p.cex.append(a.get("reason",""))
                    results.append({"action":"weakened","prior":pid,
                                   "new_xfer":p.xfer,"reason":a.get("reason","")})
            elif act=="create":
                stmt=a.get("stmt","")
                if stmt:
                    p=self.priors.promote(stmt,
                        typ=a.get("prior_type","domain"),
                        scope=a.get("scope",""),
                        evidence=a.get("evidence",[]))
                    p.xfer=a.get("new_xfer",0.5)
                    results.append({"action":"created","prior":p.id,
                                   "stmt":stmt,"reason":a.get("reason","")})
            elif act=="demote" and pid:
                self.priors.demote(pid)
                results.append({"action":"demoted","prior":pid,
                               "reason":a.get("reason","")})
            elif act=="anti_prior":
                stmt=a.get("stmt","")
                if stmt:
                    ap=APrior(stmt=stmt,why=a.get("reason",""),
                             trap=a.get("scope",""))
                    self.priors.add_anti(ap)
                    results.append({"action":"anti_prior","id":ap.id,
                                   "stmt":stmt,"reason":a.get("reason","")})
        return results
