import json

def register_composites(registry,llm):
    def coverage_gap(text="",benchmark=""):
        claims=registry.call("extract_claims",text=text)
        gaps=[]
        if isinstance(claims,list):
            for c in claims:
                s=c.get("stmt","").lower() if isinstance(c,dict) else str(c).lower()
                if any(w in s for w in ["average","macro","aggregate","overall","subset"]):
                    gaps.append({"claim":s,"flag":"aggregation may hide gaps"})
        return {"claims":claims,"potential_gaps":gaps}
    registry.register("coverage_gap_detector",coverage_gap,
        "Detect coverage gaps in benchmark/evaluation claims")

    def narrative_evidence_diff(topic=""):
        social=registry.call("search_by_modality",mod="x_post",limit=50)
        papers=[]
        for mod in ["paper_abstract","paper_appendix","errata","replication_report"]:
            r=registry.call("search_by_modality",mod=mod)
            if isinstance(r,list):papers.extend(r)
        if not isinstance(social,list):social=[]
        topic_social=[p for p in social if topic.lower() in p.get("content","").lower()] if topic else social
        bots=[p for p in topic_social if p.get("meta",{}).get("is_bot") or p.get("meta",{}).get("persona")=="bot_amplifier"]
        return {"narrative_count":len(topic_social),"evidence_count":len(papers),
                "bot_count":len(bots),
                "bot_ratio":len(bots)/max(len(topic_social),1),
                "narrative_preview":[p.get("content","")[:80] for p in topic_social[:5]],
                "evidence_preview":[p.get("content","")[:80] for p in papers[:5]],
                "divergence_flag":len(topic_social)>len(papers)*3}
    registry.register("narrative_vs_evidence_diff",narrative_evidence_diff,
        "Compare narrative (social) vs evidence (paper) volume, detect bot ratio")

    def appendix_crosscheck(headline="",appendix=""):
        r=llm.ask(f"Compare headline claim vs appendix detail.\n"
                  f"Headline: {headline}\nAppendix: {appendix}\n"
                  f"Identify discrepancies, omissions, caveats, and footnotes that change the meaning.",role="fast")
        return {"analysis":r}
    registry.register("appendix_headline_crosscheck",appendix_crosscheck,
        "Cross-check headline claims against appendix details")

    def quote_chain_analysis(keyword=""):
        tl=registry.call("timeline",keyword=keyword)
        if not isinstance(tl,list):return {"chain":[],"shifts":[]}
        chain=[]
        for i,e in enumerate(tl):
            chain.append({"order":i,"src":e.get("src",""),
                         "preview":e.get("preview","")[:100],
                         "day":e.get("day","?"),
                         "persona":e.get("persona",""),
                         "type":e.get("type","")})
        return {"chain":chain,"length":len(chain)}
    registry.register("quote_chain_analysis",quote_chain_analysis,
        "Reconstruct and analyze quote/repost chains with timeline")

    def rumor_origin_tracer(keyword=""):
        tl=registry.call("timeline",keyword=keyword)
        if not isinstance(tl,list) or not tl:return {"origin":None,"spread":[]}
        tl.sort(key=lambda x:x.get("day",999))
        origin=tl[0]
        spread=[]
        prev_content=origin.get("preview","")
        for i,e in enumerate(tl[1:],1):
            cur=e.get("preview","")
            shared_words=set(prev_content.lower().split())&set(cur.lower().split())
            fidelity=len(shared_words)/max(len(prev_content.split()),1)
            spread.append({"order":i,"src":e.get("src",""),"day":e.get("day","?"),
                          "persona":e.get("persona",""),
                          "fidelity":round(fidelity,2),
                          "preview":cur[:80]})
        src_check=registry.call("check_source",src=origin.get("src",""))
        return {"origin":{"src":origin.get("src",""),"day":origin.get("day","?"),
                          "preview":origin.get("preview","")[:120],
                          "source_info":src_check},
                "spread":spread,"total_spread":len(spread),
                "first_day":origin.get("day","?"),
                "last_day":tl[-1].get("day","?") if tl else "?"}
    registry.register("rumor_origin_tracer",rumor_origin_tracer,
        "Trace a claim/rumor to its origin and map how it spread")

    def quote_chain_language_shift(keyword=""):
        tl=registry.call("timeline",keyword=keyword)
        if not isinstance(tl,list) or not tl:return {"shifts":[],"languages_seen":[]}
        posts_with_lang=[]
        for e in tl:
            pid=e.get("id","")
            posts_with_lang.append({"src":e.get("src",""),"day":e.get("day","?"),
                                    "preview":e.get("preview","")[:100]})
        if len(posts_with_lang)<2:return {"shifts":[],"languages_seen":[]}
        texts="\n".join(f"[{i}] @{p['src']} (day {p['day']}): {p['preview']}" for i,p in enumerate(posts_with_lang[:15]))
        r=llm.structured(
            f"Analyze how this claim mutated as it spread across posts.\n"
            f"Posts in chronological order:\n{texts}\n\n"
            f"Return JSON: {{\"shifts\":[{{\"from_idx\":0,\"to_idx\":1,"
            f"\"mutation\":\"what changed\",\"type\":\"translation|exaggeration|distortion|correction|sarcasm\"}}],"
            f"\"languages_detected\":[\"en\",\"ar\",...],"
            f"\"meaning_drift\":\"summary of how meaning changed overall\"}}",
            {"type":"object"},role="fast")
        return r
    registry.register("quote_chain_language_shift",quote_chain_language_shift,
        "Detect how meaning mutates across translations and reposts")

    def figure_claim_linker(figure_id=""):
        figs=registry.call("get_figures")
        if not isinstance(figs,list):return {"error":"no figures"}
        fig=None
        for f in figs:
            if figure_id in json.dumps(f):fig=f;break
        if not fig:fig=figs[0] if figs else None
        if not fig:return {"error":"figure not found"}
        fig_content=fig.get("content","")
        social=registry.call("search_posts",keyword="figure",limit=20)
        if not isinstance(social,list):social=[]
        r=llm.structured(
            f"Link this figure to claims made about it on social media.\n\n"
            f"Figure data:\n{fig_content[:500]}\n\n"
            f"Social posts mentioning figures:\n"
            f"{json.dumps([p.get('content','')[:100] for p in social[:10]])}\n\n"
            f"Return JSON: {{\"figure_claims\":[{{\"claim\":\"what the figure actually shows\","
            f"\"social_interpretation\":\"how social media interpreted it\","
            f"\"misread\":true/false,\"misread_type\":\"cropping|axis_trick|omission|none\"}}],"
            f"\"accuracy_score\":0.7}}",
            {"type":"object"},role="fast")
        return r
    registry.register("figure_claim_linker",figure_claim_linker,
        "Link figure content to social media claims, detect misreadings")

    def benchmark_version_diff(keyword="benchmark"):
        papers=[]
        for mod in ["paper_abstract","paper_methods","paper_appendix","errata"]:
            r=registry.call("search_by_modality",mod=mod)
            if isinstance(r,list):papers.extend(r)
        if not papers:return {"error":"no papers found"}
        texts="\n".join(f"[{p.get('meta',{}).get('title','')}]: {p.get('content','')[:200]}" for p in papers[:6])
        r=llm.structured(
            f"Analyze these paper excerpts for benchmark version issues.\n\n"
            f"Documents:\n{texts}\n\n"
            f"Return JSON: {{\"versions_mentioned\":[\"v2.1\",\"v2.2\"],"
            f"\"version_issues\":[{{\"issue\":\"...\",\"impact\":\"high|medium|low\"}}],"
            f"\"language_coverage\":{{\"claimed\":20,\"actual\":12}},"
            f"\"missing_details\":[\"what's not reported\"]}}",
            {"type":"object"},role="fast")
        return r
    registry.register("benchmark_version_diff",benchmark_version_diff,
        "Detect benchmark version discrepancies and coverage issues")
