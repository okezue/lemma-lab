import json,random,time,hashlib,traceback

def _uid():return hashlib.md5(str(time.time()+random.random()).encode()).hexdigest()[:8]

VALID_LANGS=["af","am","ar","az","be","bg","bn","bs","ca","ceb","cs","cy","da","de",
"el","en","eo","es","et","eu","fa","fi","fr","ga","gd","gl","gu","ha","he","hi","hr",
"ht","hu","hy","id","ig","is","it","ja","jv","ka","kk","km","kn","ko","ku","ky","la",
"lb","lo","lt","lv","mg","mi","mk","ml","mn","mr","ms","mt","my","ne","nl","no","ny",
"om","or","pa","pl","ps","pt","qu","rm","ro","ru","rw","sd","si","sk","sl","sn","so",
"sq","sr","st","su","sv","sw","ta","te","tg","th","ti","tk","tl","tr","ts","tt","tw",
"ug","uk","ur","uz","vi","wo","xh","yi","yo","zh","zu",
"pcm","ber","yue","bm","nah","ak","rn","lg","ee","ln","tn","ve","ss","nr"]

VALID_COUNTRIES=[
"Afghanistan","Albania","Algeria","Andorra","Angola","Argentina","Armenia","Australia",
"Austria","Azerbaijan","Bahrain","Bangladesh","Belarus","Belgium","Benin","Bhutan",
"Bolivia","Bosnia and Herzegovina","Botswana","Brazil","Brunei","Bulgaria","Burkina Faso",
"Burundi","Cambodia","Cameroon","Canada","Cape Verde","Central African Republic","Chad",
"Chile","China","Colombia","Comoros","Congo","Costa Rica","Croatia","Cuba","Cyprus",
"Czech Republic","Denmark","Djibouti","Dominican Republic","Ecuador","Egypt",
"El Salvador","Equatorial Guinea","Eritrea","Estonia","Eswatini","Ethiopia","Fiji",
"Finland","France","Gabon","Gambia","Georgia","Germany","Ghana","Greece","Guatemala",
"Guinea","Guinea-Bissau","Guyana","Haiti","Honduras","Hong Kong","Hungary","Iceland",
"India","Indonesia","Iran","Iraq","Ireland","Israel","Italy","Ivory Coast","Jamaica",
"Japan","Jordan","Kazakhstan","Kenya","Kosovo","Kuwait","Kyrgyzstan","Laos","Latvia",
"Lebanon","Lesotho","Liberia","Libya","Liechtenstein","Lithuania","Luxembourg",
"Madagascar","Malawi","Malaysia","Maldives","Mali","Malta","Mauritania","Mauritius",
"Mexico","Moldova","Mongolia","Montenegro","Morocco","Mozambique","Myanmar","Namibia",
"Nepal","Netherlands","New Zealand","Nicaragua","Niger","Nigeria","North Korea",
"North Macedonia","Norway","Oman","Pakistan","Palestine","Panama","Papua New Guinea",
"Paraguay","Peru","Philippines","Poland","Portugal","Qatar","Romania","Russia","Rwanda",
"Saudi Arabia","Senegal","Serbia","Sierra Leone","Singapore","Slovakia","Slovenia",
"Somalia","South Africa","South Korea","South Sudan","Spain","Sri Lanka","Sudan",
"Suriname","Sweden","Switzerland","Syria","Taiwan","Tajikistan","Tanzania","Thailand",
"Togo","Trinidad and Tobago","Tunisia","Turkey","Turkmenistan","Uganda","Ukraine",
"United Arab Emirates","United Kingdom","United States","Uruguay","Uzbekistan",
"Venezuela","Vietnam","Yemen","Zambia","Zimbabwe"]

CONNECTED_VIA_OPTIONS=[
"iOS App Store","Android Google Play","Web App","API",
"Web App (VPN detected)","United Kingdom App Store","India App Store",
"Brazil App Store","Japan App Store","Germany App Store"]

ACCOUNT_PROMPT="""Generate a completely unique, realistic X/Twitter account for someone who would engage in a controversy about a multilingual AI model (Arbor-13B).

The controversy: A lab published a model claiming 11.2% multilingual gains, but excluded 8 low-resource languages. The real average is ~4.7%. Social media amplified both hype and fraud allegations. The truth is nuanced.

Generate a COMPLETE account. Be creative and realistic. You can:
- Pick ANY country and language combination
- Mix languages in the bio (code-switching is common)
- Make the account verified, org-verified, legacy-verified, or unverified
- Make it a researcher, student, engineer, journalist, bot, activist, policy maker, translator, diaspora member, educator, meme account, skeptic, fan, troll, or any other realistic role
- Give them a realistic follower/following ratio for their role
- Include username change history if appropriate (especially bots, pivoted accounts)
- The account can post in multiple languages

IMPORTANT: Return VALID JSON with ALL of these fields:
{
  "id": "unique_handle_no_at",
  "name": "Display Name (can be in any script)",
  "role": "short_role_description",
  "bio": "bio text (can mix languages, max 160 chars)",
  "location": "city, country or empty",
  "country": "country name from real countries",
  "lang": "primary ISO 639-1 language code",
  "langs": ["list","of","all","language","codes","they","speak"],
  "style": "how they post (tone, habits, quirks)",
  "verified": false,
  "org_verified": false,
  "legacy_verified": false,
  "followers": 1234,
  "following": 567,
  "posts_count": 890,
  "account_type": "personal|org|bot|media",
  "joined": "Month YYYY",
  "connected_via": "iOS App Store|Android Google Play|Web App|API|Web App (VPN detected)",
  "username_changes": [{"from": "@old_name", "date": "Month YYYY"}],
  "prev_usernames": ["@old_name"],
  "header_desc": "description of header image",
  "pfp_desc": "description of profile picture",
  "credibility": 0.7,
  "website": ""
}"""

POST_PROMPT="""Generate a realistic X/Twitter post from this account about the Arbor-13B multilingual AI controversy.

Account: {account_json}

The controversy (day {day} of 14):
- Day 0-1: Paper published claiming 11.2% multilingual gains
- Day 2-3: Hype wave, bot amplification
- Day 4-5: Replication failures, cropped figure goes viral
- Day 6: Fraud accusations based on misread screenshot
- Day 7-8: Careful analysis reveals 8 excluded languages, real average ~4.7%
- Day 9: Authors issue errata
- Day 10-12: Nuanced picture emerges, partial gains confirmed
- Day 13-14: Retrospectives, policy discussions

Generate a post this person would write on day {day}. Can be:
- A standalone post, reply, quote-post, or thread starter
- In any of their languages (can mix languages / code-switch)
- Can include media (describe attached images/gifs/pdfs/videos/links)
- Can reference other posts, figures, the paper, etc.

Return VALID JSON:
{{
  "content": "the post text (max 280 chars, can be in any language or mixed)",
  "lang": "ISO 639-1 code of primary language used",
  "type": "post|reply|quote|thread",
  "media": [
    {{"type": "image|gif|video|pdf|link_preview", "desc": "what the media shows"}}
  ],
  "sentiment": "hype|skeptical|neutral|critical|supportive|sarcastic|confused|angry|measured",
  "references": "what they're reacting to (paper, another post, figure, news, etc.)"
}}"""

BATCH_POST_PROMPT="""Generate {n} diverse X/Twitter posts from different accounts about the Arbor-13B multilingual AI controversy on day {day}.

Accounts available:
{accounts_summary}

Controversy context for day {day}:
{day_context}

Generate {n} posts. Each from a DIFFERENT account. Mix languages, tones, media types.
Some should be standalone, some replies, some quotes. Include code-switching where natural.

Return VALID JSON:
{{
  "posts": [
    {{
      "author_id": "the account id",
      "content": "post text (max 280 chars, any language)",
      "lang": "primary language code",
      "type": "post|reply|quote",
      "media": [{{"type":"image|gif|video|pdf|link_preview","desc":"..."}}],
      "sentiment": "hype|skeptical|neutral|critical|supportive|sarcastic|confused|angry|measured"
    }}
  ]
}}"""

DAY_CONTEXT={
    0:"Paper just published on arXiv. Only authors and close followers know.",
    1:"Authors announce results. Initial technical reception. 11.2% headline number circulating.",
    2:"Influencers pick up the story. Hype thread goes viral. Comparisons to GPT-4.",
    3:"Bot amplification in multiple languages. #Arbor13B trending. Memes appear.",
    4:"Replication attempts begin. Some researchers notice missing languages in appendix.",
    5:"Replication failure posted. Cropped Figure 3 screenshot goes viral. Doubt spreads.",
    6:"Fraud accusations based on cropped figure. Satirist's parody taken seriously. Peak drama.",
    7:"Careful analysis by senior researcher shows 8 excluded languages. Correction threads (some in non-English).",
    8:"Benchmark maintainer confirms version issue. African/Asian NLP researchers speak up about excluded languages.",
    9:"Authors issue errata revising 11.2% to 4.7%. Official statement. Ethics discussion begins.",
    10:"Careful independent replication confirms partial gains (5-8% high-resource, not low-resource).",
    11:"Screenshot misattribution. Parody cited as real. Second bot wave. Misinformation persists.",
    12:"Nuanced picture solidifies among researchers. Influencer quietly deletes fraud thread.",
    13:"Journalist investigation. Media articles. Retrospective analysis.",
    14:"Open source reproduction toolkit released. New eval standards proposed. Constructive aftermath.",
}

def validate_account(d):
    issues=[]
    req=["id","name","role","bio","country","lang","langs","followers",
         "following","posts_count","joined","connected_via","account_type",
         "verified","org_verified","legacy_verified","style",
         "header_desc","pfp_desc","credibility"]
    for f in req:
        if f not in d:issues.append(f"missing:{f}")
    if "id" in d and not isinstance(d["id"],str):issues.append("id not string")
    if "followers" in d and not isinstance(d["followers"],(int,float)):issues.append("followers not number")
    if "following" in d and not isinstance(d["following"],(int,float)):issues.append("following not number")
    if "langs" in d and not isinstance(d["langs"],list):issues.append("langs not list")
    if "verified" in d and not isinstance(d["verified"],bool):issues.append("verified not bool")
    return issues

def validate_post(d):
    issues=[]
    for f in ["content","lang","type"]:
        if f not in d:issues.append(f"missing:{f}")
    if "content" in d and len(d.get("content",""))>500:issues.append("content too long")
    if "type" in d and d["type"] not in ("post","reply","quote","thread"):
        issues.append(f"bad type:{d['type']}")
    return issues

def generate_synthetic_accounts(llm,n=100,batch_size=5):
    print(f"Generating {n} synthetic accounts...")
    accounts=[]
    ok=0;fail=0
    configs=[]
    for i in range(n):
        t=random.uniform(0.4,1.3)
        fp=random.uniform(0.0,1.5)
        pp=random.uniform(0.0,1.5)
        configs.append({"temp":t,"fp":fp,"pp":pp})
    for i,cfg in enumerate(configs):
        try:
            r=llm.structured(ACCOUNT_PROMPT,{"type":"object"},role="fast",
                             temp=cfg["temp"],
                             frequency_penalty=cfg["fp"],
                             presence_penalty=cfg["pp"])
            issues=validate_account(r)
            if issues:
                r=_fix_account(r,issues)
                issues2=validate_account(r)
                if issues2:
                    fail+=1
                    print(f"  [{i+1}/{n}] FAIL (unfixable): {issues2[:3]}")
                    continue
            r["id"]=_sanitize_id(r.get("id",""),accounts)
            r["_gen"]={"temp":round(cfg["temp"],2),
                       "freq_pen":round(cfg["fp"],2),
                       "pres_pen":round(cfg["pp"],2)}
            accounts.append(r)
            ok+=1
            if ok%10==0:
                print(f"  [{ok}/{n}] OK (t={cfg['temp']:.1f} fp={cfg['fp']:.1f} pp={cfg['pp']:.1f}) "
                      f"-> @{r['id']} ({r['country']}, {r['langs']})")
        except Exception as e:
            fail+=1
            llm.errors+=1
            if fail%5==0:print(f"  [{i+1}/{n}] ERROR: {str(e)[:80]}")
    print(f"Accounts: {ok} ok, {fail} failed ({ok/(ok+fail)*100:.0f}% success)")
    return accounts

def generate_synthetic_posts(llm,accounts,per_day=15,days=15):
    print(f"Generating ~{per_day*days} synthetic posts across {days} days...")
    posts=[]
    ok=0;fail=0
    acct_idx={a["id"]:a for a in accounts}
    for day in range(days):
        ctx=DAY_CONTEXT.get(day,"General discussion continues.")
        batch_accts=random.sample(accounts,min(per_day,len(accounts)))
        summary="\n".join(f"- @{a['id']}: {a['name']} ({a['role']}, {a['country']}, "
                          f"langs={a['langs']}, cred={a.get('credibility',0.5)})"
                          for a in batch_accts)
        t=random.uniform(0.5,1.1)
        fp=random.uniform(0.0,1.0)
        pp=random.uniform(0.0,1.0)
        try:
            prompt=BATCH_POST_PROMPT.format(
                n=per_day,day=day,accounts_summary=summary,day_context=ctx)
            r=llm.structured(prompt,{"type":"object"},role="fast",
                             temp=t,frequency_penalty=fp,presence_penalty=pp)
            batch=r.get("posts",[])
            if not isinstance(batch,list):batch=[batch]
            for p in batch:
                issues=validate_post(p)
                if issues:
                    p=_fix_post(p,issues)
                aid=p.get("author_id","")
                acct=acct_idx.get(aid)
                post={"id":f"SX{_uid()}",
                      "content":p.get("content",""),
                      "src":aid,
                      "modality":"x_post",
                      "meta":{"day":day,
                              "persona":acct.get("role","synthetic") if acct else "synthetic",
                              "name":acct.get("name","") if acct else "",
                              "lang":p.get("lang","en"),
                              "type":p.get("type","post"),
                              "media":p.get("media",[]),
                              "sentiment":p.get("sentiment","neutral"),
                              "is_synthetic":True,
                              "gen_params":{"temp":round(t,2),"fp":round(fp,2),"pp":round(pp,2)},
                              "metrics":_rand_metrics(acct),
                              "account":_acct_badge(acct) if acct else {}}}
                posts.append(post)
                ok+=1
        except Exception as e:
            fail+=1
            llm.errors+=1
            if fail%3==0:print(f"  Day {day} batch error: {str(e)[:80]}")
        if (day+1)%3==0:
            print(f"  Day {day}: {ok} posts so far, {fail} batch failures")
    print(f"Posts: {ok} ok, {fail} batch failures")
    return posts

def generate_single_posts(llm,accounts,n=50):
    print(f"Generating {n} individual posts with max diversity...")
    posts=[]
    ok=0;fail=0
    for i in range(n):
        acct=random.choice(accounts)
        day=random.randint(0,14)
        t=random.uniform(0.3,1.4)
        fp=random.uniform(0.0,2.0)
        pp=random.uniform(0.0,2.0)
        try:
            prompt=POST_PROMPT.format(
                account_json=json.dumps({k:v for k,v in acct.items()
                                        if k!="_gen"},indent=1),
                day=day)
            r=llm.structured(prompt,{"type":"object"},role="fast",
                             temp=t,frequency_penalty=fp,presence_penalty=pp)
            issues=validate_post(r)
            if issues:r=_fix_post(r,issues)
            post={"id":f"SX{_uid()}","content":r.get("content",""),
                  "src":acct["id"],"modality":"x_post",
                  "meta":{"day":day,"persona":acct.get("role","synthetic"),
                          "name":acct.get("name",""),
                          "lang":r.get("lang",acct.get("lang","en")),
                          "type":r.get("type","post"),
                          "media":r.get("media",[]),
                          "sentiment":r.get("sentiment","neutral"),
                          "is_synthetic":True,
                          "gen_params":{"temp":round(t,2),"fp":round(fp,2),"pp":round(pp,2)},
                          "metrics":_rand_metrics(acct),
                          "account":_acct_badge(acct)}}
            posts.append(post);ok+=1
        except Exception as e:
            fail+=1;llm.errors+=1
        if (i+1)%20==0:
            print(f"  [{i+1}/{n}] {ok} ok, {fail} fail")
    print(f"Individual posts: {ok} ok, {fail} failed")
    return posts

def run_full_synthetic(llm,n_accounts=100,posts_per_day=15,
                       single_posts=50,output="./dataset_data/synthetic.json"):
    import os;os.makedirs(os.path.dirname(output),exist_ok=True)
    t0=time.time()
    accts=generate_synthetic_accounts(llm,n_accounts)
    batch_posts=generate_synthetic_posts(llm,accts,posts_per_day)
    single=generate_single_posts(llm,accts,single_posts)
    all_posts=batch_posts+single
    acct_cards={}
    for a in accts:
        badge="none"
        if a.get("org_verified"):badge="org_gold"
        elif a.get("verified"):badge="blue_check"
        elif a.get("legacy_verified"):badge="legacy_blue"
        acct_cards[a["id"]]={
            "id":a["id"],"name":a["name"],"handle":f"@{a['id']}",
            "badge":badge,"followers":a.get("followers",0),
            "following":a.get("following",0),
            "account_type":a.get("account_type","personal"),
            "bio":a.get("bio",""),"location":a.get("location",""),
            "joined":a.get("joined",""),"website":a.get("website",""),
            "header_desc":a.get("header_desc",""),"pfp_desc":a.get("pfp_desc",""),
            "lang":a.get("lang","en"),"langs":a.get("langs",[]),
            "country":a.get("country",""),
            "connected_via":a.get("connected_via",""),
            "username_changes":a.get("username_changes",[]),
            "prev_usernames":a.get("prev_usernames",[]),
            "posts_count":a.get("posts_count",0),
            "credibility":a.get("credibility",0.5),
            "style":a.get("style",""),
            "role":a.get("role",""),
            "_gen":a.get("_gen",{})}
    langs=set();countries=set();sentiments={}
    for p in all_posts:
        langs.add(p["meta"].get("lang","en"))
        for p2 in all_posts:
            s=p2["meta"].get("sentiment","neutral")
            sentiments[s]=sentiments.get(s,0)+1
    for a in accts:
        countries.add(a.get("country",""))
        for l in a.get("langs",[]):langs.add(l)
    dt=time.time()-t0
    out={"generated_at":time.strftime("%Y-%m-%d %H:%M:%S"),
         "generation_time_sec":round(dt,1),
         "observations":all_posts,
         "accounts":acct_cards,
         "stats":{"total_posts":len(all_posts),
                  "total_accounts":len(accts),
                  "post_languages":sorted(langs),
                  "account_countries":sorted(countries-{""}),
                  "sentiments":sentiments,
                  "api_usage":llm.usage()}}
    with open(output,'w') as f:json.dump(out,f,indent=2)
    print(f"\n{'='*50}")
    print(f"SYNTHETIC GENERATION COMPLETE")
    print(f"{'='*50}")
    print(f"  Time: {dt:.0f}s")
    print(f"  Accounts: {len(accts)}")
    print(f"  Posts: {len(all_posts)}")
    print(f"  Languages: {len(langs)} ({sorted(langs)[:20]}...)")
    print(f"  Countries: {len(countries-{''})}")
    print(f"  Sentiments: {sentiments}")
    print(f"  API: {llm.usage()}")
    print(f"  Output: {output}")
    return out

def _sanitize_id(id_str,existing):
    id_str=id_str.replace("@","").replace(" ","_").lower()[:20]
    if not id_str:id_str=f"synth_{_uid()}"
    used={a["id"] for a in existing}
    while id_str in used:id_str=f"{id_str}_{_uid()[:3]}"
    return id_str

def _fix_account(d,issues):
    if "missing:id" in str(issues):d["id"]=f"synth_{_uid()}"
    if "missing:name" in str(issues):d["name"]=d.get("id","Unknown")
    if "missing:role" in str(issues):d["role"]="observer"
    if "missing:bio" in str(issues):d["bio"]=""
    if "missing:country" in str(issues):d["country"]=""
    if "missing:lang" in str(issues):d["lang"]="en"
    if "missing:langs" in str(issues):d["langs"]=[d.get("lang","en")]
    if "missing:followers" in str(issues):d["followers"]=random.randint(10,5000)
    if "missing:following" in str(issues):d["following"]=random.randint(50,2000)
    if "missing:posts_count" in str(issues):d["posts_count"]=random.randint(100,5000)
    if "missing:joined" in str(issues):
        m=random.choice(["January","March","June","September","November"])
        y=random.choice(["2018","2019","2020","2021","2022","2023","2024"])
        d["joined"]=f"{m} {y}"
    if "missing:connected_via" in str(issues):
        d["connected_via"]=random.choice(CONNECTED_VIA_OPTIONS)
    if "missing:account_type" in str(issues):d["account_type"]="personal"
    if "missing:verified" in str(issues):d["verified"]=False
    if "missing:org_verified" in str(issues):d["org_verified"]=False
    if "missing:legacy_verified" in str(issues):d["legacy_verified"]=False
    if "missing:style" in str(issues):d["style"]="neutral observer"
    if "missing:header_desc" in str(issues):d["header_desc"]="Default header"
    if "missing:pfp_desc" in str(issues):d["pfp_desc"]="Default avatar"
    if "missing:credibility" in str(issues):d["credibility"]=0.5
    if "followers not number" in str(issues):
        try:d["followers"]=int(d["followers"])
        except:d["followers"]=100
    if "following not number" in str(issues):
        try:d["following"]=int(d["following"])
        except:d["following"]=100
    if "langs not list" in str(issues):d["langs"]=[d.get("lang","en")]
    if "verified not bool" in str(issues):d["verified"]=bool(d.get("verified"))
    return d

def _fix_post(d,issues):
    if "missing:content" in str(issues):d["content"]="[generated post]"
    if "missing:lang" in str(issues):d["lang"]="en"
    if "missing:type" in str(issues):d["type"]="post"
    if "bad type" in str(issues):d["type"]="post"
    if "content too long" in str(issues):d["content"]=d["content"][:280]
    return d

def _rand_metrics(acct):
    base=max(acct.get("followers",100)//10,10) if acct else 100
    v=int(base*random.uniform(0.5,3.0))
    return {"likes":int(v*random.uniform(0.02,0.12)),
            "reposts":int(v*random.uniform(0.005,0.04)),
            "replies":int(v*random.uniform(0.001,0.025)),
            "views":v,
            "bookmarks":int(v*random.uniform(0.001,0.01)),
            "quote_count":int(v*random.uniform(0.001,0.006))}

def _acct_badge(acct):
    if not acct:return {}
    badge="none"
    if acct.get("org_verified"):badge="org_gold"
    elif acct.get("verified"):badge="blue_check"
    elif acct.get("legacy_verified"):badge="legacy_blue"
    return {"badge":badge,"followers":acct.get("followers",0),
            "account_type":acct.get("account_type","personal")}
