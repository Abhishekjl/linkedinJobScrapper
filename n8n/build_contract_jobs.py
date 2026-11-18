"""Generate the "Contract Jobs - Remote AI" n8n workflow JSON.

Usage: python3 -I build_contract_jobs.py <out.json> [--test]
Code lives in contract_jobs/*.js. The Telegram bot URL and chat id are copied from the Job Hunt workflow export.
--test: two searches only, separate workflow id.
"""
import json
import os
import re
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
JOB_HUNT = "/data/job_hunt_complete_local.json"

out_path = sys.argv[1]
TEST = "--test" in sys.argv[2:]
read = lambda name: open(os.path.join(HERE, "contract_jobs", name), encoding="utf-8").read()

jh = json.load(open(JOB_HUNT))
jh = jh[0] if isinstance(jh, list) else jh
tg = next(n["parameters"] for n in jh["nodes"] if n["name"] == "Send Telegram")
tg_chat = re.search(r"chat_id:\s*'([^']+)'", tg["jsonBody"]).group(1)
settings_js = read("settings.js").replace("__TELEGRAM_URL__", tg["url"]).replace("__TELEGRAM_CHAT_ID__", tg_chat)
if TEST:
    settings_js = settings_js.replace("return [{ json: {", "// TEST overrides below\nconst cfg = {", 1)
    settings_js = settings_js.rstrip().removesuffix("}}];") + """};
cfg.searches = [cfg.searches[0], cfg.searches[6]];
cfg.post_queries = cfg.post_queries.slice(0, 2);
return [{ json: cfg }];"""

nid = lambda: str(uuid.uuid4())
x = 0
def pos():
    global x
    x += 240
    return [x, 304]
def code(name, js):
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.code", "typeVersion": 2, "position": pos(), "parameters": {"jsCode": js}}
def post(name, url, body, timeout, interval):
    return {"id": nid(), "name": name, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": pos(),
            "parameters": {"method": "POST", "url": url, "sendBody": True, "specifyBody": "json", "jsonBody": body,
                           "options": {"timeout": timeout, "batching": {"batch": {"batchSize": 1, "batchInterval": interval}}}},
            "onError": "continueRegularOutput"}
SET = "$('Settings').first().json"

chain = [
    code("Settings", settings_js),
    code("Search Requests", f"const S = {SET};\n"
         "return S.searches.map(s => ({ json: { titles: [s.phrase], location: s.location, date_posted: S.date_posted,\n"
         "  count: S.count_per_search, fetch_details: true } }));"),
    # One search at a time: the scraper runs titles of one request in parallel, LinkedIn rate-limits bursts.
    post("Scrape LinkedIn", f"={{{{ {SET}.scraper_url }}}}", "={{ JSON.stringify($json) }}", 1800000, 3000),
    code("Fetch Posts", read("fetch_posts.js")),
    code("Filter Jobs", read("filter.js")),
    post("Send Telegram", f"={{{{ {SET}.telegram_url }}}}",
         f"={{{{ JSON.stringify({{ chat_id: {SET}.telegram_chat_id, text: $json.text, parse_mode: 'HTML', disable_web_page_preview: true }}) }}}}",
         30000, 1200),
    code("Mark Sent", "// Remember a job only after Telegram accepted it.\n"
         "const state = $getWorkflowStaticData('global');\nstate.sent = state.sent || {};\n"
         "const src = $('Filter Jobs').all();\nlet sent = 0;\n"
         "$input.all().forEach((it, i) => {\n  if (it.json.error || it.json.ok === false || !src[i]) return;\n"
         "  for (const k of src[i].json.sent_keys) state.sent[k] = Date.now();\n  sent++;\n});\n"
         "return [{ json: { sent, failed: src.length - sent } }];"),
]
triggers = [
    {"id": nid(), "name": "Every 4 Hours", "type": "n8n-nodes-base.scheduleTrigger", "typeVersion": 1.2, "position": [0, 208],
     "parameters": {"rule": {"interval": [{"field": "cronExpression", "expression": "0 0,4,8,12,16,20 * * *"}]}}},
    {"id": nid(), "name": "Manual Run", "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "position": [0, 400], "parameters": {}},
]
note = {"id": nid(), "name": "How it works", "type": "n8n-nodes-base.stickyNote", "typeVersion": 1, "position": [208, -180],
        "parameters": {"width": 1000, "height": 280, "content":
            "## Contract Jobs - Remote AI\n"
            "Every 4 hours: runs the LinkedIn searches in **Settings** (past 24 h) through the self-hosted scraper; "
            "**Fetch Posts** adds recent LinkedIn hiring posts (web search for linkedin.com/posts, read logged out, marked 📣). "
            "**Filter Jobs** keeps a job or post only if it is contract / part-time / freelance (LinkedIn type, or the title says so), "
            "remote (a timezone in the JD counts), an AI title or an AI keyword in the JD (LangChain, LangGraph, LLM, RAG, "
            "multi-agent...), has nothing from the drop list (PF, EOR, C2H, W-2, IR35, US/UK/EU work authorization, on-site, hybrid), "
            "and is listed in India 🇮🇳, says Global/anywhere 🌍, or names a timezone 🕒.\n\n"
            "A timezone counts as global only outside US/Canada/UK/EU listings. One Telegram message per company; "
            "each job is sent once (remembered 45 days; only scheduled runs remember). "
            "Edit searches and keywords in **Settings**, rules at the top of **Filter Jobs**."}}
link = lambda a, b: {a: {"main": [[{"node": b, "type": "main", "index": 0}]]}}
connections = {}
for t in triggers:
    connections.update(link(t["name"], "Settings"))
for a, b in zip(chain, chain[1:]):
    connections.update(link(a["name"], b["name"]))

wf = {
    "id": "ContractJobsTST1" if TEST else "ContractJobsWf01",
    "name": ("[TEST] " if TEST else "") + "Contract Jobs - Remote AI",
    "active": False,
    "nodes": triggers + chain + [note],
    "connections": connections,
    "settings": {"executionOrder": "v1", "binaryMode": "separate", "timezone": "Asia/Kolkata"},
    "pinData": {},
    "tags": [],
}
with open(out_path, "w") as f:
    json.dump(wf, f, indent=1, ensure_ascii=False)
print("wrote", out_path, len(wf["nodes"]), "nodes")
