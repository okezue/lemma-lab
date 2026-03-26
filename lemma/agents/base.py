from abc import ABC,abstractmethod

class BaseAgent(ABC):
    def __init__(self,llm,ledger,graph,priors,capsules,tools=None):
        self.llm=llm;self.ledger=ledger;self.graph=graph
        self.priors=priors;self.caps=capsules;self.tools=tools
    @abstractmethod
    def run(self,*a,**kw):pass
    def _sys(self,role_desc):
        pc=self.priors.to_context() if self.priors else "(no priors)"
        return f"{role_desc}\n\nActive priors:\n{pc}"
    def _claims_ctx(self,n=15):
        return self.graph.to_context(n) if self.graph else "(no claims)"
    def _tool_list(self):
        if not self.tools:return "(no tools)"
        return "\n".join(f"- {t}" for t in self.tools.list_tools())
    def _obs_sample(self,n=5):
        if not self.ledger or not self.ledger.obs:return "(no observations)"
        sample=list(self.ledger.obs.values())[-n:]
        return "\n".join(f"[{o.src}] ({o.mod}) {o.content[:80]}" for o in sample)
