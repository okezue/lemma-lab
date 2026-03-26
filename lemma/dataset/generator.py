import json,os,random,hashlib,time,math

def _uid():return hashlib.md5(str(time.time()+random.random()).encode()).hexdigest()[:8]

def generate_dataset(llm,world,output_dir="./dataset_data"):
    os.makedirs(output_dir,exist_ok=True)
    ppl={p["id"]:p for p in world["personas"]}
    posts=[]
    post_idx={}
    threads_out=[]
    for tspec in world["threads"]:
        tposts=_gen_thread(llm,tspec,ppl,world)
        for i,tp in enumerate(tposts):
            tp["meta"]["thread_id"]=tspec["id"]
            tp["meta"]["thread_pos"]=i
            if i>0:tp["meta"]["reply_to"]=tposts[i-1]["id"]
            tp["meta"]["type"]="thread"
            post_idx[tp["id"]]=tp
        posts.extend(tposts)
        threads_out.append({"id":tspec["id"],"author":tspec["author"],
                           "post_ids":[p["id"] for p in tposts]})
    for day_block in world["timeline"]:
        day=day_block["day"]
        for evt in day_block["events"]:
            if "thread" in evt:continue
            for aid in evt["actors"]:
                actor=ppl.get(aid)
                if not actor:continue
                if actor["role"]=="bot_amplifier":
                    bp=_gen_bot_post(actor,evt,day,posts)
                    post_idx[bp["id"]]=bp;posts.append(bp)
                    continue
                if actor["role"]=="trending":
                    tp=_gen_trending_card(evt,day,world)
                    posts.append(tp);continue
                if actor["role"]=="x_news_tab":
                    np=_gen_news_entry(evt,day,world)
                    posts.append(np);continue
                if actor["role"]=="meme_account":
                    mp=_gen_meme_post(actor,evt,day)
                    post_idx[mp["id"]]=mp;posts.append(mp)
                    continue
                p=_gen_standalone(llm,actor,evt,day,world)
                _attach_media(p,actor,evt,day)
                post_idx[p["id"]]=p;posts.append(p)
    quotes=_gen_quote_posts(llm,posts,ppl,world)
    posts.extend(quotes)
    reposts=_gen_reposts(posts,ppl)
    posts.extend(reposts)
    bot_amp=_gen_bot_waves(posts,ppl,world)
    posts.extend(bot_amp)
    replies=_gen_comment_replies(llm,posts,ppl,world)
    posts.extend(replies)
    for fig_id,fig in world["figures"].items():
        posts.append({"id":f"F{_uid()}","content":json.dumps(fig),
                      "src":"figure","modality":"figure_desc",
                      "meta":{"fig_id":fig_id,"type":"figure","day":0,
                              "title":fig.get("title",""),
                              "misread":fig.get("misread",""),
                              "data":fig.get("data",{}),
                              "media":[{"type":"image","desc":fig.get("note",""),
                                        "alt":fig.get("title","")}]}})
    for pid,paper in world["papers"].items():
        posts.append({"id":f"P{_uid()}","content":paper["content"],
                      "src":"paper","modality":paper["type"],
                      "meta":{"paper_id":pid,"title":paper["title"],
                              "type":paper["type"],"day":0,
                              "media":[{"type":"pdf","title":paper["title"],
                                        "pages":random.randint(8,32)}]}})
    for ne in world.get("news_tab",[]):
        posts.append({"id":f"N{_uid()}","content":ne["headline"]+". "+ne["snippet"],
                      "src":ne["source"],"modality":"x_news",
                      "meta":{"type":"news_tab","day":ne["day"],
                              "headline":ne["headline"],"snippet":ne["snippet"],
                              "category":ne["category"],
                              "trending_rank":ne["trending_rank"],
                              "engagement":ne["engagement"]}})
    for tt in world.get("trending",[]):
        posts.append({"id":f"TR{_uid()}","content":f"Trending: {tt['topic']}",
                      "src":"x_platform","modality":"trending_topic",
                      "meta":{"type":"trending","day":tt["day"],
                              "topic":tt["topic"],"post_count":tt["posts"],
                              "category":tt["category"],
                              "context":tt.get("context","")}})
    _assign_metrics(posts,ppl)
    _attach_account_info(posts,ppl)
    posts.sort(key=lambda p:(p.get("meta",{}).get("day",0),p.get("id","")))
    out={"world_title":world["title"],
         "observations":posts,
         "threads":threads_out,
         "figures":list(world["figures"].keys()),
         "papers":list(world["papers"].keys()),
         "accounts":{p["id"]:_account_card(p) for p in world["personas"]},
         "eval_queries":world.get("eval_queries",[]),
         "stats":_compute_stats(posts)}
    path=f"{output_dir}/polyglot_crisis.json"
    with open(path,'w') as f:json.dump(out,f,indent=2)
    s=out["stats"]
    print(f"Generated {s['total_posts']} total items -> {path}")
    print(f"  Threads: {s['threads']}, Quotes: {s['by_type'].get('quote',0)}, "
          f"Reposts: {s['by_type'].get('repost',0)}, Replies: {s['by_type'].get('reply',0)}")
    print(f"  Bot posts: {s['bot_posts']}, Media posts: {s['media_posts']}")
    print(f"  Authors: {s['unique_authors']}, Languages: {s['languages']}")
    print(f"  News tab: {s['by_modality'].get('x_news',0)}, "
          f"Trending: {s['by_modality'].get('trending_topic',0)}")
    return out

def _compute_stats(posts):
    mods={};types={};langs=set();authors=set();bots=0;media=0
    for p in posts:
        m=p.get("modality","?");mods[m]=mods.get(m,0)+1
        t=p.get("meta",{}).get("type","?");types[t]=types.get(t,0)+1
        langs.add(p.get("meta",{}).get("lang","en"))
        authors.add(p.get("src",""))
        if p.get("meta",{}).get("is_bot"):bots+=1
        if p.get("meta",{}).get("media"):media+=1
    return {"total_posts":len(posts),"threads":types.get("thread",0),
            "unique_authors":len(authors),"languages":sorted(langs),
            "days":max((p.get("meta",{}).get("day",0) for p in posts),default=0)+1,
            "bot_posts":bots,"media_posts":media,
            "by_modality":mods,"by_type":types}

def _account_card(persona):
    p=persona["profile"]
    badge="none"
    if persona.get("org_verified"):badge="org_gold"
    elif persona.get("verified"):badge="blue_check"
    elif persona.get("legacy_verified"):badge="legacy_blue"
    return {"id":persona["id"],"name":persona["name"],
            "handle":f"@{persona['id']}",
            "badge":badge,
            "followers":persona.get("followers",0),
            "following":persona.get("following",0),
            "account_type":persona.get("account_type","personal"),
            "bio":p.get("bio",""),
            "location":p.get("location",""),
            "joined":p.get("joined",""),
            "website":p.get("website",""),
            "header_desc":p.get("header",""),
            "pfp_desc":p.get("pfp",""),
            "lang":persona.get("lang","en"),
            "langs":persona.get("langs",[persona.get("lang","en")]),
            "country":p.get("country",""),
            "connected_via":p.get("connected_via",""),
            "username_changes":p.get("username_changes",[]),
            "prev_usernames":p.get("prev_usernames",[]),
            "posts_count":p.get("posts_count",0),
            "lists":p.get("lists",0)}

def _gen_thread(llm,tspec,ppl,world):
    author=ppl.get(tspec["author"],{})
    beats="\n".join(f"  {b}" for b in tspec["beats"])
    gt_ctx=_get_gt_for_role(author.get("role",""),world)
    media_hints=_thread_media_hints(tspec,author)
    prompt=(
        f"Generate a {tspec['n_posts']}-post thread for X (Twitter).\n\n"
        f"Author: {author.get('name','')} (@{tspec['author']})\n"
        f"Role: {author.get('role','')}, Style: {author.get('style','')}\n"
        f"Language: {author.get('lang','en')}\n"
        f"Day: {tspec['day']}, Topic: {tspec['topic']}\n\n"
        f"Beat sheet:\n{beats}\n\n"
        f"Context they know: {gt_ctx}\n"
        f"Media notes: {media_hints}\n\n"
        f"Rules:\n- Each post max 280 chars\n- Include thread numbering\n"
        f"- Match persona style\n- If lang != en, write in that language\n"
        f"- Reference attached media where relevant\n\n"
        f'Return JSON: {{"posts":["post1","post2",...]}}')
    try:
        r=llm.structured(prompt,{"type":"object"},role="fast")
        txts=r.get("posts",[])
    except:
        txts=[f"[{author.get('name','')}] {b}" for b in tspec["beats"]]
    out=[]
    for i,txt in enumerate(txts[:tspec["n_posts"]]):
        media=_thread_post_media(tspec,i,author)
        out.append({"id":f"X{_uid()}","content":txt,"src":tspec["author"],
                    "modality":"x_post",
                    "meta":{"day":tspec["day"],"persona":author.get("role",""),
                            "name":author.get("name",""),"lang":author.get("lang","en"),
                            "type":"thread","thread_id":tspec["id"],"thread_pos":i,
                            "media":media,
                            "metrics":{"likes":0,"reposts":0,"replies":0,
                                       "views":0,"bookmarks":0,"quote_count":0}}})
    return out

def _thread_media_hints(tspec,author):
    hints=[]
    tid=tspec["id"]
    if tid=="T02":hints.append("Post 5 includes cropped Figure 3 screenshot (image)")
    if tid=="T05":hints.append("Post 2-4 include recalculated tables (images)")
    if tid=="T07":hints.append("Post 1 links to PDF replication report")
    if tid=="T10":hints.append("Post 4 links to Wired article (URL preview)")
    if author.get("role")=="ml_influencer":hints.append("Uses screenshot images of other posts")
    return "; ".join(hints) if hints else "no special media"

def _thread_post_media(tspec,pos,author):
    media=[]
    tid=tspec["id"]
    if tid=="T02" and pos==4:
        media.append({"type":"image","desc":"Cropped Figure 3 screenshot showing only EN, ZH, ES, FR, DE bars. Y-axis starts at 4%.",
                      "alt":"Bar chart of Arbor-13B gains (cropped)"})
    if tid=="T05" and pos in (1,2,3):
        media.append({"type":"image","desc":"Recalculated results table showing excluded languages",
                      "alt":"Table comparing reported vs actual language coverage"})
    if tid=="T07" and pos==0:
        media.append({"type":"pdf","desc":"Full replication report PDF, 12 pages",
                      "title":"Arbor-13B Independent Replication Results","pages":12})
    if tid=="T10" and pos==3:
        media.append({"type":"link_preview","url":"wired.com/story/arbor-13b-truth",
                      "title":"Inside the Arbor-13B Controversy",
                      "desc":"Exclusive investigation by Sam Zhang"})
    return media

def _gen_standalone(llm,actor,evt,day,world):
    gt_ctx=_get_gt_for_role(actor["role"],world)
    prompt=(
        f"Generate ONE X post (max 280 chars).\n\n"
        f"Author: {actor['name']} (@{actor['id']})\n"
        f"Style: {actor.get('style','neutral')}\n"
        f"Language: {actor.get('lang','en')}\n"
        f"Event: {evt['event']} (day {day})\n"
        f"What they know: {gt_ctx}\n\n"
        f'Return JSON: {{"content":"the post text"}}')
    try:
        r=llm.structured(prompt,{"type":"object"},role="fast")
        txt=r.get("content",f"[{actor['name']}] {evt['event']}")
    except:
        txt=f"[{actor['name']}] {evt['event']}"
    return {"id":f"X{_uid()}","content":txt,"src":actor["id"],
            "modality":"x_post",
            "meta":{"day":day,"persona":actor["role"],"name":actor["name"],
                    "lang":actor.get("lang","en"),"type":"post","media":[],
                    "metrics":{"likes":0,"reposts":0,"replies":0,
                               "views":0,"bookmarks":0,"quote_count":0}}}

def _attach_media(post,actor,evt,day):
    media=post["meta"].get("media",[])
    role=actor["role"]
    evtxt=evt["event"].lower()
    if "screenshot" in evtxt or "cropped" in evtxt:
        media.append({"type":"image","desc":f"Screenshot: {evt['event']}",
                      "alt":"Screenshot shared on X"})
    if "paper" in evtxt or "arxiv" in evtxt:
        media.append({"type":"link_preview","url":"arxiv.org/abs/2411.XXXXX",
                      "title":"Arbor-13B paper","desc":"arXiv preprint"})
    if "pdf" in evtxt.lower():
        media.append({"type":"pdf","desc":"Attached PDF document","pages":8})
    if role=="benchmark_auto":
        media.append({"type":"image","desc":"Auto-generated leaderboard update card",
                      "alt":"BabelBench leaderboard showing Arbor-13B entry"})
    if "deployment" in evtxt or "real-world" in evtxt:
        media.append({"type":"image","desc":"Grafana dashboard screenshot showing model latency/accuracy",
                      "alt":"Production metrics dashboard"})
    if role in ("tech_reporter","mainstream_media","tech_outlet") and "article" in evtxt:
        media.append({"type":"link_preview","url":"example.com/article",
                      "title":evt["event"][:60],"desc":"Full article"})
    post["meta"]["media"]=media

def _gen_meme_post(actor,evt,day):
    meme_types=[
        {"format":"drake_meme","panels":["Reading the abstract: 11.2% gain","Reading the appendix: 8 languages excluded"],
         "media_type":"image"},
        {"format":"expanding_brain","panels":["Trusting the headline","Reading the paper","Reading the appendix","Checking the benchmark version"],
         "media_type":"image"},
        {"format":"reaction_gif","desc":"Leonardo DiCaprio pointing at TV meme with text 'Me when I find the footnote'",
         "media_type":"gif"},
        {"format":"two_buttons","panels":["Believe the 11.2%","Read the errata"],
         "media_type":"image"},
        {"format":"distracted_boyfriend","panels":["ML Twitter looking at: FRAUD","Walking past: nuanced methodology critique","Girlfriend: actual paper"],
         "media_type":"image"},
        {"format":"is_this_meme","desc":"Butterfly meme: 'Is this a multilingual breakthrough?' (looking at a cropped bar chart)",
         "media_type":"image"},
        {"format":"galaxy_brain","panels":["The gains are real","The gains are fake","The gains are real but smaller","It depends on the decoding settings"],
         "media_type":"image"},
        {"format":"reaction_gif","desc":"Confused math lady meme with BabelBench numbers floating around",
         "media_type":"gif"},
    ]
    meme=random.choice(meme_types)
    if meme["format"]=="reaction_gif":
        content=f"[GIF] {meme['desc']} #Arbor13B #MLTwitter"
        media=[{"type":"gif","desc":meme["desc"],"alt":meme["desc"]}]
    else:
        panels=meme.get("panels",[])
        content=f"[{meme['format'].upper()}]\n"+"\n".join(f"  → {p}" for p in panels)+"\n#Arbor13B #MLMemes"
        media=[{"type":"image","format":meme["format"],
                "desc":f"{meme['format']} meme about Arbor-13B",
                "panels":panels,"alt":"AI meme about Arbor-13B controversy"}]
    return {"id":f"X{_uid()}","content":content,"src":actor["id"],
            "modality":"x_post",
            "meta":{"day":day,"persona":"meme_account","name":actor["name"],
                    "lang":"en","type":"post","media":media,
                    "metrics":{"likes":0,"reposts":0,"replies":0,
                               "views":0,"bookmarks":0,"quote_count":0}}}

def _gen_trending_card(evt,day,world):
    topics=[t for t in world.get("trending",[]) if t["day"]==day]
    if not topics:
        content=f"Trending in Technology: Arbor-13B ({day})"
        meta_extra={}
    else:
        t=topics[0]
        content=f"Trending in {t['category']}: {t['topic']} · {t['posts']:,} posts"
        meta_extra={"topic":t["topic"],"post_count":t["posts"],
                    "context":t.get("context","")}
    return {"id":f"TR{_uid()}","content":content,
            "src":"x_platform","modality":"trending_topic",
            "meta":{"day":day,"type":"trending","lang":"en",**meta_extra}}

def _gen_news_entry(evt,day,world):
    entries=[n for n in world.get("news_tab",[]) if n["day"]==day]
    if entries:
        ne=entries[0]
        content=f"{ne['headline']}. {ne['snippet']}"
        meta_extra={"headline":ne["headline"],"snippet":ne["snippet"],
                    "category":ne["category"],"trending_rank":ne["trending_rank"],
                    "engagement":ne["engagement"]}
    else:
        content=evt["event"]
        meta_extra={"category":"Technology"}
    return {"id":f"N{_uid()}","content":content,
            "src":"x_news_ai","modality":"x_news",
            "meta":{"day":day,"type":"news_tab","lang":"en",
                    "media":[{"type":"link_preview","desc":"X News article card"}],
                    **meta_extra}}

def _gen_bot_post(actor,evt,day,existing):
    templates=[
        "🚀 {hashtags} {broken}!!",
        "BREAKING!! {topic} is HUGE! #AI #ML {hashtags}",
        "{translated} 🔥🔥🔥 #AIBreakthrough",
        "RT if you agree: {topic} changes everything!! {hashtags}",
        "Everyone talking about {topic}! Don't miss!! {hashtags}",
        "📢 {topic} - this is the future!! {hashtags} {broken}",
    ]
    hashtags=random.choice(["#Arbor13B #AI #ML","#MultilingualAI #NLP",
                            "#AIBreakthrough #Arbor","#ML #AI #Arbor13B"])
    topic=random.choice(["Arbor-13B","multilingual AI","AI breakthrough"])
    broken_phrases=["very impressive result yes","much good model",
                    "top performance achieve","best multilingual ever seen"]
    translated_phrases={
        "hi":"आर्बोर-13B बहुत अच्छा मॉडल है! बहुभाषी AI क्रांति!",
        "pt":"Arbor-13B é incrível! Revolução na IA multilíngue!",
        "de":"Arbor-13B ist unglaublich! Mehrsprachige KI-Revolution!",
        "ar":"أربور-13B نموذج مذهل! ثورة الذكاء الاصطناعي!",
        "ja":"Arbor-13Bは素晴らしい！多言語AI革命！",
        "zh":"Arbor-13B太厉害了！多语言AI革命！",
        "ko":"Arbor-13B 대단해! 다국어 AI 혁명!",
    }
    lang=actor.get("lang","en")
    txt=random.choice(templates).format(
        hashtags=hashtags,topic=topic,
        broken=random.choice(broken_phrases),
        translated=translated_phrases.get(lang,topic))
    return {"id":f"X{_uid()}","content":txt,"src":actor["id"],
            "modality":"x_post",
            "meta":{"day":day,"persona":"bot_amplifier","name":actor["name"],
                    "lang":lang,"type":"post","is_bot":True,"media":[],
                    "metrics":{"likes":random.randint(0,5),"reposts":random.randint(0,3),
                               "replies":0,"views":random.randint(10,200),
                               "bookmarks":0,"quote_count":0}}}

def _gen_quote_posts(llm,posts,ppl,world):
    quotable=[p for p in posts if p.get("meta",{}).get("type") in ("thread","post")
              and p.get("meta",{}).get("persona") not in ("bot_amplifier","trending","x_news_tab")]
    if not quotable:return []
    selected=random.sample(quotable,min(30,len(quotable)))
    quotes=[]
    responders=[p for p in world["personas"]
                if p["role"] not in ("bot_amplifier","meme_account","parody_account","trending","x_news_tab")]
    for orig in selected:
        quoter=random.choice(responders)
        if quoter["id"]==orig["src"]:continue
        gt_ctx=_get_gt_for_role(quoter["role"],world)
        prompt=(
            f"Generate a quote-post (max 200 chars) responding to:\n"
            f"Original by @{orig['src']}: \"{orig['content'][:200]}\"\n\n"
            f"Your persona: {quoter['name']} ({quoter['role']})\n"
            f"Style: {quoter.get('style','')}\n"
            f"What you know: {gt_ctx}\n\n"
            f'Return JSON: {{"content":"your quote-post text"}}')
        try:
            r=llm.structured(prompt,{"type":"object"},role="fast")
            txt=r.get("content","")
        except:
            txt=f"Interesting take from @{orig['src']}"
        if txt:
            quotes.append({"id":f"X{_uid()}","content":txt,"src":quoter["id"],
                          "modality":"x_post",
                          "meta":{"day":orig.get("meta",{}).get("day",0),
                                  "persona":quoter["role"],"name":quoter["name"],
                                  "lang":quoter.get("lang","en"),
                                  "type":"quote","quote_of":orig["id"],
                                  "quoted_text":orig["content"][:100],
                                  "quoted_author":orig["src"],"media":[],
                                  "metrics":{"likes":0,"reposts":0,"replies":0,
                                             "views":0,"bookmarks":0,"quote_count":0}}})
    return quotes

def _gen_reposts(posts,ppl):
    viral=[p for p in posts if p.get("meta",{}).get("persona") in
           ("ml_influencer","hot_take_influencer","lead_author","tech_reporter")]
    reposts=[]
    reposters=[p for p in ppl.values() if p["role"] in
               ("bot_amplifier","ml_influencer","edu_influencer","startup_founder",
                "corporate_blog","tech_outlet")]
    for orig in viral:
        n=random.randint(2,8)
        for _ in range(n):
            rp=random.choice(list(reposters))
            if rp["id"]==orig["src"]:continue
            reposts.append({
                "id":f"X{_uid()}",
                "content":f"RT @{orig['src']}: {orig['content'][:100]}",
                "src":rp["id"],"modality":"x_post",
                "meta":{"day":orig.get("meta",{}).get("day",0)+random.choice([0,1]),
                        "persona":rp["role"],"name":rp["name"],
                        "lang":rp.get("lang","en"),
                        "type":"repost","repost_of":orig["id"],"media":[],
                        "metrics":{"likes":0,"reposts":0,"replies":0,
                                   "views":0,"bookmarks":0,"quote_count":0}}})
    return reposts

def _gen_bot_waves(posts,ppl,world):
    bots=[p for p in world["personas"] if p["role"]=="bot_amplifier"]
    viral=[p for p in posts if p.get("meta",{}).get("persona") in
           ("ml_influencer","lead_author","anonymous_leaker","satire_account")]
    waves=[]
    for day in [3,6,11]:
        targets=[p for p in viral if p.get("meta",{}).get("day",99)<=day]
        if not targets:continue
        for bot in bots:
            n=random.randint(3,8)
            for _ in range(n):
                orig=random.choice(targets)
                lang=bot.get("lang","en")
                txt=_botify(orig["content"],lang)
                waves.append({
                    "id":f"X{_uid()}","content":txt,"src":bot["id"],
                    "modality":"x_post",
                    "meta":{"day":day,"persona":"bot_amplifier",
                            "name":bot["name"],"lang":lang,
                            "type":"bot_amplification","amplifies":orig["id"],
                            "is_bot":True,"media":[],
                            "metrics":{"likes":random.randint(0,3),
                                       "reposts":random.randint(0,2),
                                       "replies":0,"views":random.randint(5,100),
                                       "bookmarks":0,"quote_count":0}}})
    return waves

def _gen_comment_replies(llm,posts,ppl,world):
    replyable=[p for p in posts if p.get("meta",{}).get("type") in ("thread","post")
               and p.get("meta",{}).get("persona") not in ("bot_amplifier","trending")]
    if not replyable:return []
    hot=sorted(replyable,
               key=lambda p:p.get("meta",{}).get("metrics",{}).get("views",0),
               reverse=True)[:20]
    replies=[]
    responders=[p for p in world["personas"]
                if p["role"] not in ("bot_amplifier","trending","x_news_tab","meme_account")]
    for orig in hot:
        n_replies=random.randint(1,4)
        for _ in range(n_replies):
            replier=random.choice(responders)
            if replier["id"]==orig["src"]:continue
            gt_ctx=_get_gt_for_role(replier["role"],world)
            prompt=(
                f"Write a short reply (max 200 chars) to this X post:\n"
                f"@{orig['src']}: \"{orig['content'][:180]}\"\n\n"
                f"You are {replier['name']} ({replier['role']})\n"
                f"Style: {replier.get('style','')}\n"
                f"What you know: {gt_ctx}\n\n"
                f'Return JSON: {{"content":"your reply"}}')
            try:
                r=llm.structured(prompt,{"type":"object"},role="fast")
                txt=r.get("content","")
            except:
                txt=f"@{orig['src']} interesting point"
            if txt:
                replies.append({
                    "id":f"X{_uid()}","content":txt,"src":replier["id"],
                    "modality":"x_post",
                    "meta":{"day":orig.get("meta",{}).get("day",0),
                            "persona":replier["role"],"name":replier["name"],
                            "lang":replier.get("lang","en"),
                            "type":"reply","reply_to":orig["id"],
                            "reply_to_author":orig["src"],"media":[],
                            "metrics":{"likes":0,"reposts":0,"replies":0,
                                       "views":0,"bookmarks":0,"quote_count":0}}})
    return replies

def _botify(text,lang):
    phrases={
        "en":["🚀 AMAZING!! ","WOW must see!! ","INCREDIBLE AI!! ","TOP NEWS!! "],
        "hi":["🚀 अद्भुत!! ","बहुत बड़ी खबर!! ","अविश्वसनीय!! "],
        "pt":["🚀 INCRÍVEL!! ","NOTÍCIA TOP!! ","IMPRESSIONANTE!! "],
        "de":["🚀 UNGLAUBLICH!! ","TOP NACHRICHT!! ","WAHNSINN!! "],
        "ar":["🚀 مذهل!! ","خبر عاجل!! ","لا يصدق!! "],
        "ja":["🚀 すごい!! ","大ニュース!! ","信じられない!! "],
        "zh":["🚀 太棒了!! ","重大新闻!! ","难以置信!! "],
        "ko":["🚀 대박!! ","빅뉴스!! ","믿을 수 없어!! "],
        "tr":["🚀 İNANILMAZ!! ","BÜYÜK HABER!! ","MÜTHİŞ!! "],
        "id":["🚀 LUAR BIASA!! ","BERITA BESAR!! ","MENAKJUBKAN!! "],
        "vi":["🚀 TUYỆT VỜI!! ","TIN LỚN!! ","KHÔNG THỂ TIN!! "],
        "pl":["🚀 NIESAMOWITE!! ","WIELKA WIADOMOŚĆ!! ","NIEWIARYGODNE!! "],
        "fa":["🚀 شگفت‌انگیز!! ","خبر بزرگ!! ","باورنکردنی!! "],
        "sw":["🚀 AJABU!! ","HABARI KUBWA!! ","HAIWEZEKANI!! "],
        "am":["🚀 አስደናቂ!! ","ትልቅ ዜና!! ","ማመን አይቻልም!! "],
        "ur":["🚀 حیرت انگیز!! ","بڑی خبر!! ","ناقابل یقین!! "],
    }
    prefix=random.choice(phrases.get(lang,phrases["en"]))
    return f"{prefix}{text[:80].replace(chr(10),' ')}... #AI #ML #Arbor13B #NLP"

def _assign_metrics(posts,ppl):
    for p in posts:
        role=p.get("meta",{}).get("persona","")
        day=p.get("meta",{}).get("day",0)
        typ=p.get("meta",{}).get("type","")
        base={"lead_author":5000,"ml_influencer":20000,"tech_reporter":8000,
              "hot_take_influencer":10000,"bot_amplifier":50,
              "satire_account":3000,"anonymous_leaker":2000,
              "benchmark_maintainer":4000,"careful_replicator":3000,
              "skeptic_reviewer":6000,"grad_replicator":1000,
              "meme_account":15000,"ai_ethics_researcher":4000,
              "african_nlp_researcher":3000,"tech_outlet":12000,
              "mainstream_media":50000}.get(role,500)
        virality=1.0
        if day in [2,5,6]:virality=2.5
        if day in [3,11]:virality=1.5
        if typ=="thread":virality*=1.5
        if typ in ("repost","bot_amplification"):virality*=0.3
        if typ=="reply":virality*=0.4
        v=int(base*virality*random.uniform(0.5,2.0))
        l=int(v*random.uniform(0.02,0.1))
        rp=int(v*random.uniform(0.005,0.03))
        rep=int(v*random.uniform(0.001,0.02))
        bk=int(v*random.uniform(0.001,0.008))
        qc=int(v*random.uniform(0.001,0.005))
        p["meta"]["metrics"]={"likes":l,"reposts":rp,"replies":rep,
                               "views":v,"bookmarks":bk,"quote_count":qc}

def _attach_account_info(posts,ppl):
    for p in posts:
        author=ppl.get(p.get("src",""))
        if author:
            badge="none"
            if author.get("org_verified"):badge="org_gold"
            elif author.get("verified"):badge="blue_check"
            elif author.get("legacy_verified"):badge="legacy_blue"
            p["meta"]["account"]={
                "badge":badge,
                "followers":author.get("followers",0),
                "account_type":author.get("account_type","personal")}

def _get_gt_for_role(role,world):
    gt=world["ground_truth"]
    m={
        "lead_author":gt["real_gains"][0],
        "co_author":gt["real_gains"][0],
        "senior_advisor":"Full picture, knows limitations but loyal to lab",
        "data_lead":"Knows excluded languages were problematic",
        "lab_account":"PR-approved messaging only",
        "skeptic_reviewer":gt["inflated"][0],
        "methods_critic":"Asks about baselines and decoding settings",
        "stats_reviewer":gt["inflated"][2],
        "benchmark_maintainer":f"{gt['inflated'][1]}. Knows v2.1 vs v2.2.",
        "benchmark_auto":"Automated: only sees submitted scores",
        "ml_influencer":"Sees headline numbers only",
        "tech_journalist":"Aggregates X discourse, limited depth",
        "edu_influencer":"Understands concepts, sometimes oversimplifies",
        "hot_take_influencer":"Contrarian, doesn't read papers",
        "grad_replicator":gt["replication"][0],
        "careful_replicator":gt["replication"][1],
        "independent_replicator":"Running own experiments",
        "multilingual_researcher":gt["real_gains"][1],
        "african_nlp_researcher":"Knows excluded African languages intimately",
        "indic_nlp_researcher":"Knows Hindi/Tamil/Bengali eval issues",
        "sea_nlp_researcher":"Knows Khmer/Lao were excluded",
        "arabic_nlp_researcher":"Arabic eval seems OK but wants to verify",
        "anonymous_leaker":gt["misread_figure"][0],
        "disgruntled_ex":"Claims insider knowledge, some real some exaggerated",
        "anon_peer_reviewer":"Actually reviewed the paper",
        "satire_account":"Exaggerates everything for comedy",
        "meme_account":"Makes memes about trending AI topics",
        "parody_account":"Parodies Dr. Chen with over-the-top claims",
        "bot_amplifier":"Amplifies trending content",
        "industry_translation":"Practical deployment experience",
        "startup_founder":"Investor-focused, wants hype to be true",
        "corporate_blog":"Vendor-neutral analysis",
        "production_engineer":"Cares about real-world perf, not benchmarks",
        "ai_ethics_researcher":"Concerned about hype harming communities",
        "ethics_lab":"Studying representation in NLP",
        "advocacy_org":"Policy framing, accessibility concerns",
        "tech_reporter":"Investigating, wants the full story",
        "tech_outlet":"Fast news cycle, follows X discourse",
        "mainstream_media":"Cautious, waits for multiple sources",
        "competing_lab":"Has competing model, subtly undermining",
        "competing_researcher":"Posts own results for comparison",
        "oss_community":"Wants open reproduction",
        "x_news_tab":"Algorithmic news aggregation",
        "trending":"Trending topic display",
        "nigerian_nlp":"Works on Igbo/Hausa NLP, excluded languages hit close to home",
        "latam_ml_dev":"Deploys multilingual models for Spanish LatAm market",
        "moroccan_nlp":"Works on Arabic dialects and Amazigh, knows dialect evaluation gaps",
        "ukrainian_nlp":"Works on Ukrainian NLP, sensitive to language representation issues",
        "iranian_nlp":"Works on Persian NLP, knows Farsi evaluation is limited",
        "turkish_nlp":"Works on Turkish NLP, agglutinative language challenges",
        "vietnamese_dev":"Deploys models for Vietnamese, tonal language issues",
        "indonesian_nlp":"Works on Bahasa Indonesia and Javanese",
        "filipino_dev":"Filipino NLP, understands code-switching issues",
        "ghanaian_dev":"Twi/Akan NLP, sees low-resource exclusion pattern",
        "brazilian_journalist":"Covers AI for Portuguese-speaking audience",
        "polish_researcher":"Polish NLP, Slavic language processing",
        "srilankan_nlp":"Sinhala and Tamil, multi-script challenges",
        "somali_researcher":"Horn of Africa languages, extreme low-resource",
        "swedish_journalist":"Nordic AI policy coverage",
        "ghanaian_student":"CS student interested in AI fairness",
        "argentinian_ml":"LatAm Spanish NLP, dialectal variation",
        "pakistani_nlp":"Urdu and Punjabi NLP resources",
        "ethiopian_nlp":"Amharic and Tigrinya, excluded from Arbor eval",
        "hungarian_researcher":"Hungarian computational linguistics",
        "bulgarian_dev":"Cyrillic script NLP development",
        "taiwanese_researcher":"Traditional Chinese processing",
        "chilean_dev":"Chilean tech, Latin American perspective",
        "malian_educator":"AI education in Bambara and French",
        "finnish_researcher":"Uralic language family NLP",
        "russian_journalist":"Russian tech media perspective",
        "greek_developer":"Greek NLP development",
        "nepali_nlp":"Nepali low-resource language work",
        "colombian_student":"AI enthusiast from Colombia",
        "algerian_researcher":"Algerian Arabic dialect NLP",
        "dutch_ml":"Dutch language technology",
        "portuguese_researcher":"European Portuguese NLP",
        "ethiopian_dev":"Amharic NLP tool builder",
        "turkish_journalist":"Turkish tech media",
        "serbian_dev":"South Slavic NLP",
        "kenyan_researcher":"Swahili and Bantu language NLP",
        "danish_ml":"Scandinavian NLP research",
        "vietnamese_researcher":"Vietnamese tonal language NLP",
        "tanzanian_dev":"Swahili NLP tools, East Africa",
        "polish_student":"Multilingual model evaluation",
        "estonian_nlp":"Finno-Ugric language NLP",
        "iraqi_researcher":"Kurdish and Arabic NLP",
        "israeli_researcher":"Hebrew and Arabic NLP",
        "rwandan_dev":"Kinyarwanda NLP, Central Africa",
        "hk_researcher":"Cantonese processing, Hong Kong",
        "romanian_researcher":"Romanian NLP, Romance languages",
        "malaysian_nlp":"Malay and multilingual Malaysia",
        "hausa_researcher":"Hausa NLP, Northern Nigeria",
        "uae_ml":"Arabic AI applications, Gulf region",
        "peruvian_student":"AI curious, Quechua heritage",
        "norwegian_policy":"AI governance and regulation",
        "nigerian_journalist":"African tech journalism",
        "kannada_nlp":"Kannada and Dravidian NLP",
        "south_african_dev":"Zulu and Southern Bantu NLP",
        "kazakh_nlp":"Kazakh and Turkic language NLP",
        "vietnamese_journalist":"Vietnamese tech media",
        "senegalese_dev":"Wolof NLP tools",
        "icelandic_linguist":"Small language preservation",
        "singaporean_ml":"Multilingual SE Asian deployment",
        "mexican_journalist":"LatAm AI coverage",
        "yoruba_researcher":"Yoruba language technology",
        "cuban_nlp":"Caribbean Spanish NLP",
        "kenyan_journalist":"East African tech journalism",
    }
    return m.get(role,"General observer")
