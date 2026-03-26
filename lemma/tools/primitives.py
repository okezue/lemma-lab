import json

def make_primitives(llm,ledger,graph):
    tools={}
    def search_posts(keyword="",src=None,limit=20):
        return [o.to_dict() for o in ledger.query(kw=keyword,src=src)[:limit]]
    tools["search_posts"]={"fn":search_posts,
        "desc":"Search observations by keyword and/or source"}
    def get_thread(thread_id=""):
        results=[]
        for o in ledger.obs.values():
            if o.meta.get("thread_id")==thread_id:
                results.append(o.to_dict())
        results.sort(key=lambda x:x.get("meta",{}).get("thread_pos",0))
        return results
    tools["get_thread"]={"fn":get_thread,
        "desc":"Get all posts in a thread by thread_id"}
    def get_replies(post_id=""):
        results=[]
        for o in ledger.obs.values():
            if o.meta.get("reply_to")==post_id or o.meta.get("quote_of")==post_id:
                results.append(o.to_dict())
        return results
    tools["get_replies"]={"fn":get_replies,
        "desc":"Get replies and quotes to a specific post"}
    def extract_claims(text=""):
        r=llm.structured(
            f"Extract factual claims from this text. Return JSON: "
            f'{{\"claims\":[{{\"stmt\":\"...\",\"confidence\":0.8}}]}}\n\n'
            f"Text: {text}",{"type":"object"},role="fast")
        return r.get("claims",[])
    tools["extract_claims"]={"fn":extract_claims,
        "desc":"Extract normalized claims from text via LLM"}
    def timeline(keyword=""):
        obs=ledger.query(kw=keyword)
        return [{"ts":o.ts,"src":o.src,"day":o.meta.get("day","?"),
                 "preview":o.content[:100],"id":o.id,
                 "persona":o.meta.get("persona",""),
                 "type":o.meta.get("type","")} for o in obs]
    tools["timeline"]={"fn":timeline,
        "desc":"Build chronological timeline for a keyword"}
    def check_source(src=""):
        obs=ledger.query(src=src)
        persona=""
        lang=""
        is_bot=False
        if obs:
            persona=obs[0].meta.get("persona","")
            lang=obs[0].meta.get("lang","")
            is_bot=obs[0].meta.get("is_bot",False)
        return {"source":src,"count":len(obs),"persona":persona,
                "lang":lang,"is_bot":is_bot,
                "first_day":obs[0].meta.get("day") if obs else None,
                "last_day":obs[-1].meta.get("day") if obs else None}
    tools["check_source"]={"fn":check_source,
        "desc":"Check source credibility: post count, persona, bot status"}
    def find_contradictions(claim_id=""):
        c=graph.get(claim_id)
        if not c:return {"error":"not found"}
        cons=graph.contradictors(claim_id)
        return [{"id":x.id,"stmt":x.stmt,"conf":x.conf} for x in cons]
    tools["find_contradictions"]={"fn":find_contradictions,
        "desc":"Find claims contradicting a given claim"}
    def compare_claims(id1="",id2=""):
        c1,c2=graph.get(id1),graph.get(id2)
        if not c1 or not c2:return {"error":"claim not found"}
        r=llm.ask(f"Compare these two claims for tension/agreement:\n"
                  f"1. {c1.stmt}\n2. {c2.stmt}\n\nBrief analysis.",role="fast")
        return {"c1":c1.stmt,"c2":c2.stmt,"analysis":r}
    tools["compare_claims"]={"fn":compare_claims,
        "desc":"Compare two claims for tension or agreement"}
    def search_by_modality(mod="x_post",limit=50):
        return [o.to_dict() for o in ledger.query(mod=mod)[:limit]]
    tools["search_by_modality"]={"fn":search_by_modality,
        "desc":"Search observations by modality (x_post, paper_abstract, figure_desc, etc)"}
    def claim_graph_summary():
        return {"total":len(graph),"by_status":graph.summary(),
                "top_claims":graph.to_context(10)}
    tools["claim_graph_summary"]={"fn":claim_graph_summary,
        "desc":"Get summary of current claim graph"}
    def search_by_day(day=0,limit=30):
        results=[]
        for o in ledger.obs.values():
            if o.meta.get("day")==day:results.append(o.to_dict())
        return sorted(results,key=lambda x:x.get("id",""))[:limit]
    tools["search_by_day"]={"fn":search_by_day,
        "desc":"Get all observations from a specific day"}
    def get_figures():
        return [o.to_dict() for o in ledger.query(mod="figure_desc")]
    tools["get_figures"]={"fn":get_figures,
        "desc":"Get all figure/chart descriptions"}
    def search_bots():
        bots=[]
        for o in ledger.obs.values():
            if o.meta.get("is_bot") or o.meta.get("persona")=="bot_amplifier":
                bots.append(o.to_dict())
        return bots
    tools["search_bots"]={"fn":search_bots,
        "desc":"Find all bot-generated posts"}
    def get_quote_chain(post_id=""):
        chain=[]
        seen=set()
        def trace(pid):
            if pid in seen:return
            seen.add(pid)
            for o in ledger.obs.values():
                if o.meta.get("quote_of")==pid:
                    chain.append({"quoter":o.src,"content":o.content[:150],
                                  "id":o.id,"day":o.meta.get("day"),
                                  "lang":o.meta.get("lang","?")})
                    trace(o.id)
        trace(post_id)
        return chain
    tools["get_quote_chain"]={"fn":get_quote_chain,
        "desc":"Trace how a post was quoted and requoted"}
    def fetch_paper_content(paper_type="paper_abstract"):
        results=ledger.query(mod=paper_type)
        if not results:
            for mod in ["paper_abstract","paper_methods","paper_appendix","errata","replication_report"]:
                results=ledger.query(mod=mod)
                if results:break
        if not results:return {"error":"no papers found"}
        return [{"content":o.content,"title":o.meta.get("title",""),
                 "type":o.mod,"id":o.id} for o in results]
    tools["fetch_paper_content"]={"fn":fetch_paper_content,
        "desc":"Fetch full paper/appendix/errata content by type"}
    def fetch_figure_content(figure_id=""):
        figs=ledger.query(mod="figure_desc")
        if figure_id:
            figs=[f for f in figs if figure_id in json.dumps(f.meta)]
        if not figs:return {"error":"no figures found"}
        out=[]
        for f in figs:
            try:d=json.loads(f.content)
            except:d={"raw":f.content}
            out.append({"id":f.id,"data":d.get("data",{}),
                        "type":d.get("type","unknown"),
                        "title":d.get("title",""),
                        "axes":d.get("axes",{}),
                        "misread":d.get("misread",""),
                        "note":d.get("note",""),
                        "excluded":d.get("excluded",[])})
        return out
    tools["fetch_figure_content"]={"fn":fetch_figure_content,
        "desc":"Fetch full figure data including axes, values, misread potential, excluded items"}
    def search_by_persona(persona="",limit=20):
        results=[]
        for o in ledger.obs.values():
            if o.meta.get("persona","")==persona:results.append(o.to_dict())
        return sorted(results,key=lambda x:x.get("meta",{}).get("day",0))[:limit]
    tools["search_by_persona"]={"fn":search_by_persona,
        "desc":"Search posts by persona type (lead_author, ml_influencer, bot_amplifier, etc)"}
    def get_repost_tree(post_id=""):
        reposts=[]
        for o in ledger.obs.values():
            if o.meta.get("repost_of")==post_id or o.meta.get("retweet_of")==post_id:
                reposts.append({"src":o.src,"id":o.id,"day":o.meta.get("day"),
                               "lang":o.meta.get("lang","?")})
        return {"original_id":post_id,"reposts":reposts,"count":len(reposts)}
    tools["get_repost_tree"]={"fn":get_repost_tree,
        "desc":"Get all reposts/retweets of a specific post"}
    def temporal_snapshot(day=0):
        before=[o.to_dict() for o in ledger.obs.values() if o.meta.get("day",99)<=day]
        by_mod={}
        for o in before:
            m=o.get("modality","?");by_mod[m]=by_mod.get(m,0)+1
        by_persona={}
        for o in before:
            p=o.get("meta",{}).get("persona","?");by_persona[p]=by_persona.get(p,0)+1
        return {"day":day,"total":len(before),"by_modality":by_mod,
                "by_persona":by_persona,
                "sample":[o.get("content","")[:80] for o in before[-5:]]}
    tools["temporal_snapshot"]={"fn":temporal_snapshot,
        "desc":"Get snapshot of all evidence available at a specific day"}
    return tools
