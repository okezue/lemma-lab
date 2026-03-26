import json,traceback,re,io,contextlib,time,dataclasses,sys,os,tempfile

@dataclasses.dataclass
class REPLResult:
    stdout:str=""
    stderr:str=""
    locals_snapshot:dict=dataclasses.field(default_factory=dict)
    exec_time:float=0.0
    final_answer:str=None
    sub_calls:list=dataclasses.field(default_factory=list)

@dataclasses.dataclass
class CodeBlock:
    code:str=""
    result:REPLResult=None

@dataclasses.dataclass
class RLMIteration:
    prompt:str=""
    response:str=""
    code_blocks:list=dataclasses.field(default_factory=list)
    final_answer:str=None
    iteration_time:float=0.0

_SAFE_BUILTINS={k:v for k,v in __builtins__.items() if isinstance(__builtins__,dict)} if isinstance(__builtins__,dict) else {k:getattr(__builtins__,k) for k in dir(__builtins__)}
for blocked in ["eval","exec","compile","input","globals","locals","breakpoint","exit","quit"]:
    _SAFE_BUILTINS[blocked]=None

class RLMSession:
    def __init__(self,ledger,graph,priors,caps,tools,llm,
                 depth=0,max_depth=2,max_iterations=15,
                 max_errors=5,compaction_pct=0.85,parent=None):
        self.ledger=ledger;self.graph=graph;self.priors=priors
        self.caps=caps;self.tools=tools;self.llm=llm
        self.depth=depth;self.max_depth=max_depth
        self.max_iterations=max_iterations;self.max_errors=max_errors
        self.compaction_pct=compaction_pct;self.parent=parent
        self.globals={"__builtins__":_SAFE_BUILTINS}
        self.locals={}
        self.iterations=[]
        self.consecutive_errors=0
        self._final_answer=None
        self._done=False
        self._prints=[]
        self._sub_calls=[]
        self._inject_apis()

    def _inject_apis(self):
        apis={}
        apis["search"]=lambda kw="",src=None,n=20:[
            {"id":o.id,"src":o.src,"content":o.content[:200],
             "mod":o.mod,"day":o.meta.get("day","?"),"lang":o.meta.get("lang","?")}
            for o in self.ledger.query(kw=kw,src=src)[:n]]
        apis["search_mod"]=lambda mod,n=30:[
            {"id":o.id,"src":o.src,"content":o.content[:200],"mod":o.mod}
            for o in self.ledger.query(mod=mod)[:n]]
        apis["search_day"]=lambda day:[
            {"id":o.id,"src":o.src,"content":o.content[:150]}
            for o in self.ledger.obs.values() if o.meta.get("day")==day]
        apis["search_persona"]=lambda p:[
            {"id":o.id,"src":o.src,"content":o.content[:150]}
            for o in self.ledger.obs.values() if o.meta.get("persona")==p]
        apis["get_obs"]=lambda id:self._obs_dict(self.ledger.get(id))
        apis["obs_count"]=lambda:len(self.ledger)
        apis["get_thread"]=lambda tid:[
            {"id":o.id,"src":o.src,"content":o.content[:150],"pos":o.meta.get("thread_pos",0)}
            for o in sorted((o for o in self.ledger.obs.values() if o.meta.get("thread_id")==tid),
                           key=lambda o:o.meta.get("thread_pos",0))]
        apis["get_replies"]=lambda pid:[
            {"id":o.id,"src":o.src,"content":o.content[:150]}
            for o in self.ledger.obs.values()
            if o.meta.get("reply_to")==pid or o.meta.get("quote_of")==pid]
        apis["get_quote_chain"]=lambda pid:self._quote_chain(pid)
        apis["get_bots"]=lambda:[
            {"id":o.id,"src":o.src,"content":o.content[:100],"lang":o.meta.get("lang","?")}
            for o in self.ledger.obs.values()
            if o.meta.get("is_bot") or o.meta.get("persona")=="bot_amplifier"]
        apis["timeline"]=lambda kw:[
            {"day":o.meta.get("day","?"),"src":o.src,"content":o.content[:100],"id":o.id}
            for o in self.ledger.query(kw=kw)]
        apis["figures"]=lambda:[self._obs_dict(o) for o in self.ledger.query(mod="figure_desc")]
        apis["papers"]=lambda mod="paper_abstract":[self._obs_dict(o) for o in self.ledger.query(mod=mod)]
        apis["claims"]=lambda n=20:[
            {"id":c.id,"stmt":c.stmt,"conf":c.conf,"status":c.status,
             "sup":len(c.sup),"con":len(c.con)}
            for c in sorted(self.graph.all_claims(),key=lambda c:-c.conf)[:n]]
        apis["get_claim"]=lambda id:self._claim_dict(self.graph.get(id))
        apis["claim_supporters"]=lambda id:[
            {"id":c.id,"stmt":c.stmt[:80]} for c in self.graph.supporters(id)]
        apis["claim_contradictors"]=lambda id:[
            {"id":c.id,"stmt":c.stmt[:80]} for c in self.graph.contradictors(id)]
        apis["add_claim"]=lambda stmt,conf=0.5,obs_ids=None:self._add_claim(stmt,conf,obs_ids)
        apis["link_claims"]=lambda src,tgt,rel="support":self.graph.link(src,tgt,rel)
        apis["priors"]=lambda:[
            {"id":p.id,"stmt":p.stmt,"xfer":p.xfer,"type":p.type}
            for p in self.priors.active()]
        apis["match_priors"]=lambda q,n=5:[
            {"id":p.id,"stmt":p.stmt} for p in self.priors.match(q,n)]
        apis["add_prior"]=lambda stmt,typ="domain",scope="":self._add_prior(stmt,typ,scope)
        apis["tool"]=lambda name,**kw:self.tools.call(name,**kw) if self.tools and self.tools.has(name) else {"error":f"unknown tool: {name}"}
        apis["tool_list"]=lambda:self.tools.list_tools() if self.tools else []
        apis["llm_query"]=lambda prompt,sys="You are a research assistant.":self.llm.ask(prompt,sys=sys,role="fast")
        apis["llm_query_batched"]=lambda prompts:[self.llm.ask(p,role="fast") for p in prompts]
        if self.depth<self.max_depth:
            apis["rlm_query"]=lambda prompt:self._sub_rlm(prompt)
            apis["rlm_query_batched"]=lambda prompts:[self._sub_rlm(p) for p in prompts]
        else:
            apis["rlm_query"]=lambda prompt:self.llm.ask(prompt,role="fast")
            apis["rlm_query_batched"]=lambda prompts:[self.llm.ask(p,role="fast") for p in prompts]
        apis["FINAL"]=lambda answer:self._set_final(answer)
        apis["FINAL_VAR"]=lambda varname:self._final_var(varname)
        apis["SHOW_VARS"]=lambda:self._show_vars()
        apis["store"]=lambda k,v:self._store(k,v)
        apis["recall"]=lambda k:self.locals.get(k)
        apis["print"]=lambda *a,**kw:self._print(*a,**kw)
        apis["json"]=json;apis["re"]=re
        apis["len"]=len;apis["sorted"]=sorted;apis["list"]=list
        apis["dict"]=dict;apis["set"]=set;apis["min"]=min;apis["max"]=max
        apis["sum"]=sum;apis["enumerate"]=enumerate;apis["zip"]=zip
        apis["any"]=any;apis["all"]=all;apis["isinstance"]=isinstance
        apis["str"]=str;apis["int"]=int;apis["float"]=float
        apis["range"]=range;apis["type"]=type;apis["tuple"]=tuple
        apis["round"]=round;apis["abs"]=abs;apis["map"]=map
        apis["filter"]=filter;apis["hasattr"]=hasattr;apis["getattr"]=getattr
        self.globals.update(apis)

    def _obs_dict(self,o):
        if not o:return None
        return {"id":o.id,"src":o.src,"content":o.content,"mod":o.mod,
                "meta":o.meta,"ts":o.ts}
    def _claim_dict(self,c):
        if not c:return None
        return {"id":c.id,"stmt":c.stmt,"conf":c.conf,"status":c.status,
                "sup":c.sup,"con":c.con,"deps":c.deps,"src_obs":c.src_obs}
    def _add_claim(self,stmt,conf=0.5,obs_ids=None):
        from .models import Claim
        try:conf=float(conf)
        except:conf=0.5
        c=Claim(stmt=str(stmt)[:500],conf=min(max(conf,0.0),1.0),src_obs=obs_ids or [])
        self.graph.add(c);return c.id
    def _add_prior(self,stmt,typ="domain",scope=""):
        p=self.priors.promote(stmt,typ=typ,scope=scope)
        return p.id
    def _quote_chain(self,pid):
        chain=[];seen=set()
        def trace(id):
            if id in seen:return
            seen.add(id)
            for o in self.ledger.obs.values():
                if o.meta.get("quote_of")==id:
                    chain.append({"id":o.id,"src":o.src,"content":o.content[:100],
                                  "lang":o.meta.get("lang","?")})
                    trace(o.id)
        trace(pid);return chain
    def _sub_rlm(self,prompt):
        child=RLMSession(self.ledger,self.graph,self.priors,self.caps,
                         self.tools,self.llm,depth=self.depth+1,
                         max_depth=self.max_depth,max_iterations=8,parent=self)
        result=child.run(prompt,max_steps=8)
        self._sub_calls.append({"prompt":prompt[:100],"result":str(result)[:200],
                                "depth":self.depth+1})
        return result
    def _set_final(self,answer):
        self._final_answer=answer;self._done=True;return answer
    def _final_var(self,varname):
        varname=str(varname).strip("'\"")
        combined={**self.globals,**self.locals}
        if varname in combined:
            val=combined[varname]
            self._final_answer=val;self._done=True
            return str(val)
        avail=[k for k in self.locals.keys() if not k.startswith("_")]
        return f"Variable '{varname}' not found. Available: {avail}"
    def _show_vars(self):
        return {k:type(v).__name__ for k,v in self.locals.items() if not k.startswith("_")}
    def _store(self,k,v):
        self.locals[k]=v;return v
    def _print(self,*a,**kw):
        s=io.StringIO()
        with contextlib.redirect_stdout(s):__builtins__["print"](*a,**kw) if isinstance(__builtins__,dict) else print(*a,**kw,file=s)
        self._prints.append(s.getvalue().strip())

    def exec_code(self,code):
        t0=time.time()
        stdout_cap=io.StringIO()
        stderr_cap=io.StringIO()
        self._prints=[]
        combined={**self.globals,**self.locals}
        try:
            old_stdout,old_stderr=sys.stdout,sys.stderr
            sys.stdout=stdout_cap;sys.stderr=stderr_cap
            try:exec(code,combined,combined)
            finally:sys.stdout=old_stdout;sys.stderr=old_stderr
            new_locals={k:v for k,v in combined.items()
                       if k not in self.globals and not k.startswith("__")}
            self.locals.update(new_locals)
            for reserved in ["search","search_mod","search_day","get_obs","claims",
                            "priors","FINAL","FINAL_VAR","SHOW_VARS","llm_query",
                            "rlm_query","tool","store","recall","print",
                            "add_claim","link_claims","add_prior"]:
                if reserved in self.globals:
                    combined[reserved]=self.globals[reserved]
            self.consecutive_errors=0
            out=stdout_cap.getvalue()
            if self._prints:out+=" ".join(self._prints)
            return REPLResult(stdout=out.strip(),stderr="",
                             locals_snapshot={k:type(v).__name__ for k,v in new_locals.items()},
                             exec_time=time.time()-t0,
                             final_answer=self._final_answer,
                             sub_calls=list(self._sub_calls))
        except Exception as e:
            self.consecutive_errors+=1
            tb=traceback.format_exc()
            sys.stdout=old_stdout;sys.stderr=old_stderr
            return REPLResult(stdout="",stderr=f"{type(e).__name__}: {e}",
                             exec_time=time.time()-t0)

    def run(self,query,role=None,max_steps=None):
        if max_steps:self.max_iterations=max_steps
        sys_prompt=role or self._default_sys_prompt()
        msgs=[{"role":"system","content":sys_prompt},
              {"role":"user","content":f"Research question: {query}\n\nExplore the data. Write ```repl code blocks."}]
        for step in range(self.max_iterations):
            if self._done:break
            if self.consecutive_errors>=self.max_errors:
                self._final_answer="(stopped: too many consecutive errors)";break
            iter_t0=time.time()
            r=self.llm.chat(msgs,role="fast")
            if not r:break
            msgs.append({"role":"assistant","content":r})
            blocks=re.findall(r'```(?:repl|python)\s*(.*?)```',r,re.DOTALL)
            if not blocks:
                fa=self._parse_final_from_text(r)
                if fa is not None:
                    self._final_answer=fa;self._done=True
                    self.iterations.append(RLMIteration(response=r[:300],
                        final_answer=str(fa)[:200],iteration_time=time.time()-iter_t0))
                    break
                msgs.append({"role":"user","content":
                    "Write a ```repl code block to execute. Use the APIs. "
                    "Call SHOW_VARS() to see your variables. "
                    "Call FINAL(answer) or FINAL_VAR(varname) when done."})
                continue
            code_results=[]
            all_output=""
            for code in blocks:
                result=self.exec_code(code)
                code_results.append(CodeBlock(code=code[:500],result=result))
                out=result.stdout or result.stderr or "(no output)"
                all_output+=out+"\n"
                if self._done:break
            self.iterations.append(RLMIteration(
                response=r[:300],code_blocks=code_results,
                final_answer=str(self._final_answer)[:200] if self._final_answer else None,
                iteration_time=time.time()-iter_t0))
            if self._done:break
            vars_info=self._show_vars()
            feedback=(f"Output:\n```\n{all_output[:2000]}\n```\n\n"
                     f"Variables: {vars_info}\n\n"
                     f"Continue exploring, call rlm_query() for deep dives, "
                     f"or FINAL(answer)/FINAL_VAR(varname) when done.")
            msgs.append({"role":"user","content":feedback})
        if self._final_answer is None:
            self._final_answer="(investigation incomplete)"
        return self._final_answer

    def _parse_final_from_text(self,text):
        m=re.search(r'FINAL\((.*)\)',text,re.DOTALL)
        if m:return m.group(1)
        m=re.search(r'FINAL_VAR\((.*?)\)',text)
        if m:return self._final_var(m.group(1))
        return None

    def _default_sys_prompt(self):
        depth_note=""
        if self.depth>0:depth_note=f"\nYou are at recursion depth {self.depth}/{self.max_depth}. Be concise."
        return (
            f"You are a recursive LM research agent (depth={self.depth}) with a REPL sandbox.{depth_note}\n\n"
            "Write ```repl code blocks to execute Python. Variables persist between blocks.\n\n"
            "AVAILABLE APIS:\n"
            "  DATA: search(kw,src,n), search_mod(mod,n), search_day(day), search_persona(p)\n"
            "        get_obs(id), obs_count(), get_thread(tid), get_replies(pid)\n"
            "        get_quote_chain(pid), get_bots(), timeline(kw), figures(), papers(mod)\n"
            "  CLAIMS: claims(n), get_claim(id), claim_supporters(id), claim_contradictors(id)\n"
            "          add_claim(stmt,conf,obs_ids), link_claims(src,tgt,rel)\n"
            "  PRIORS: priors(), match_priors(query,n), add_prior(stmt,type,scope)\n"
            "  LLM: llm_query(prompt,sys), llm_query_batched(prompts)\n"
            "  RLM: rlm_query(prompt) [spawns recursive sub-investigation]\n"
            "       rlm_query_batched(prompts) [parallel sub-investigations]\n"
            "  TOOLS: tool(name,**kw), tool_list()\n"
            "  SESSION: store(key,val), recall(key), SHOW_VARS(), print()\n"
            "  FINISH: FINAL(answer) or FINAL_VAR(variable_name)\n\n"
            "WORKFLOW:\n"
            "1. Explore data with search/query APIs. Store results: store('evidence', data)\n"
            "2. Analyze with llm_query() or Python. Keep root context small.\n"
            "3. For deep sub-questions, spawn rlm_query('sub-question') — gets its own REPL\n"
            "4. Create claims from evidence: add_claim('statement', 0.8, ['obs_id'])\n"
            "5. When satisfied, call FINAL(your_answer) or FINAL_VAR('my_result')\n\n"
            "You control your context. Offload data to variables. Don't ask me to search — do it yourself.")

    def get_trajectory(self):
        return {"depth":self.depth,"iterations":[
            {"step":i,"response":it.response[:200],
             "code_blocks":[{"code":cb.code[:200],
                            "stdout":cb.result.stdout[:200] if cb.result else "",
                            "stderr":cb.result.stderr[:100] if cb.result else "",
                            "exec_time":cb.result.exec_time if cb.result else 0,
                            "locals":cb.result.locals_snapshot if cb.result else {}}
                           for cb in it.code_blocks],
             "final":it.final_answer,"time":it.iteration_time}
            for i,it in enumerate(self.iterations)],
                "final_answer":str(self._final_answer)[:500] if self._final_answer else None,
                "sub_calls":self._sub_calls}


class RLMAgent:
    def __init__(self,llm,ledger,graph,priors,caps,tools=None):
        self.llm=llm;self.ledger=ledger;self.graph=graph
        self.priors=priors;self.caps=caps;self.tools=tools
    def investigate(self,query,max_steps=12,max_depth=2):
        session=RLMSession(self.ledger,self.graph,self.priors,
                           self.caps,self.tools,self.llm,
                           max_depth=max_depth,max_iterations=max_steps)
        result=session.run(query)
        return {"result":result,
                "trajectory":session.get_trajectory(),
                "claims":len(self.graph),
                "priors":len(self.priors.active())}
