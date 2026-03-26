import json
from .base import BaseAgent
from ..models import TRecipe

class ToolsmithAgent(BaseAgent):
    def run(self,traces):
        sys=self._sys(
            "You are a toolsmith. Analyze repeated multi-step reasoning patterns "
            "and propose reusable composite tools. Consider existing priors when "
            "identifying useful patterns.")
        existing=self._tool_list()
        prompt=(
            f"Recent tool traces:\n{json.dumps(traces,indent=1)}\n\n"
            f"Existing tools:\n{existing}\n\n"
            f"Identify repeated patterns that could become reusable tools.\n"
            f"Each tool should chain EXISTING primitive tools.\n"
            f"Return JSON: {{\"tools\":[{{\"name\":\"snake_case_name\","
            f"\"desc\":\"what it does\","
            f"\"steps\":[{{\"tool\":\"existing_tool_name\",\"args\":{{\"keyword\":\"example\"}}}}],"
            f"\"trigger\":\"when to use\"}}]}}")
        r=self.llm.structured(f"{sys}\n\n{prompt}",{"type":"object"},role="fast")
        recipes=[]
        for t in r.get("tools",[]):
            tr=TRecipe(name=t.get("name",""),desc=t.get("desc",""),
                       steps=t.get("steps",[]))
            recipes.append(tr)
        return recipes
    def make_executable(self,recipe,registry):
        steps=recipe.steps
        def composite(**kw):
            results=[]
            for s in steps:
                if not isinstance(s,dict):continue
                tn=s.get("tool","")
                args=dict(s.get("args",{}))
                for k,v in kw.items():
                    if isinstance(v,str):args.setdefault(k,v)
                if registry.has(tn):
                    r=registry.call(tn,**args)
                    results.append({"tool":tn,"result":r})
            return results
        registry.register(recipe.name,composite,recipe.desc)
