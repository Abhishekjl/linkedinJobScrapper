// Filter Jobs: all scraped jobs and LinkedIn posts in, one Telegram message per company with new matches out.
// Steps: dedupe -> contract/part-time -> remote -> AI title or JD keyword -> drop list -> open to India/global -> not sent before.
const S = $('Settings').first().json;
const state = $getWorkflowStaticData('global');
state.sent = state.sent || {};

// Contract wins from the title: LinkedIn's employment type is set by the poster and is sometimes wrong.
const TITLE_TYPE = /\b(contract(?:or)?|freelancer?|part[\s-]?time)\b/i;
const OK_TYPES = ['contract', 'part-time', 'temporary', 'freelance'];
const REMOTE = /\bremote\b/i;
const NOT_REMOTE = /\b(not|no|non)[\s-]+(a\s+)?remote\b/i;
// A timezone in the JD means remote and usually global hiring. Abbreviations are case-sensitive (French "est").
const TZ_ABBR = /\b(EST|EDT|PST|PDT|CST|CET|CEST|GMT|UTC|IST|BST|AEST|SGT)\b/;
const TZ_WORDS = /time[\s-]?zones?|\b(US|U\.S\.|European|EU|Americas?|North American|Pacific|Eastern|Central) (business )?hours/i;
const AI_TITLE = /\b(AI|A\.I\.|Artificial Intelligence|ML|LLM|Gen ?AI|Generative|Machine Learning|Deep Learning|NLP|MLOps|LangChain|LangGraph|RAG|Agent\w*|Agentic|Data Scien\w*|Applied Scientist|Research (Scientist|Engineer)|Researcher|Inference|Computer Vision)\b/i;
const BAD_TITLE = /\b(trainer|annotat\w*|tutor|writer|evaluator|rater|labell?er|intern(ship)?|sales|recruit\w*|teacher|instructor|SAP|Salesforce|ServiceNow|subject matter expert|generalist|content specialist)\b/i;
const DROP = new RegExp([
  'employer of record', '\\bEOR\\b', 'provident fund', '\\bPF\\b', '\\bESIC?\\b', '\\bC2H\\b', 'contract[- ]to[- ]hire',
  'third[- ]party payroll', 'on (our|the|their) payroll',
  '(authori[sz]ed|eligible|legally able|right) to work in (the )?(US|U\\.S\\.|United States|UK|United Kingdom|EU|Canada|Europe)',
  '(US|U\\.S\\.) citizens?', 'green card', 'security clearance', 'must (reside|be located|live|be based) in', '\\bW-?2\\b',
  '(outside|inside) IR35', 'work from (the )?office', '\\bWFO\\b', '\\bon[- ]?site\\b',
  '\\bGC\\s*/\\s*(USC|EAD)', '\\bUSC\\s*/\\s*GC', '\\bH-?1B\\b', '\\bC2C\\b', '(US|USA|U\\.S\\.)[- ]based (candidates|applicants|resources|consultants|only)',
  'location\\s*:\\s*(USA|US|U\\.S\\.|United States|Canada|UK|United Kingdom)\\b',
  '\\bhybrid\\b(?!\\s+(search|retrieval|rag|cloud|models?|approach|architecture|rank\\w*|index\\w*))',
  '\\b(LATAM|Latin America|EMEA|Europe|EU|US|USA|Canada)[- ](only|based candidates)\\b', 'residents? of (the )?(US|United States|Canada|UK|EU)',
].join('|'), 'i');
const ANYWHERE = /remote\s*[(\-–:,]\s*(worldwide|global|anywhere)|work(ing)? from anywhere|anywhere in the world|(location|based)\s*:\s*(remote\s*[(\-–]?\s*)?(worldwide|anywhere|global)|open to (candidates|applicants|talent|contractors)[^.]{0,40}(worldwide|globally|anywhere|any country|all countries)|from any country|any location worldwide|fully remote,? (worldwide|global)|\bAPAC\b|\bIndia\b/i;
const RATE = /(?:[$€£₹]|USD|EUR|INR)\s?\d[\d,.]*\s?[kK]?(?:\s?(?:-|–|to)\s?(?:[$€£₹]|USD|EUR|INR)?\s?\d[\d,.]*\s?[kK]?)?\s?(?:\/|per\s)\s?(?:hr|hour|h|day|month|mo|year|yr|annum)\b|\d[\d.]*\s?(?:-|–|to)?\s?\d*[\d.]*\s?LPA\b/i;
// Listed in the US, Canada, UK or EU: a timezone there usually means local hours, not global hiring.
const LOCAL_ONLY_LOC = /United States|, [A-Z]{2}$|\bCanada\b|United Kingdom|England|Scotland|London|European (Union|Economic Area)|Germany|France|Netherlands|Belgium|Spain|Portugal|Italy|Ireland|Austria|Poland|Czechia|Sweden|Denmark|Finland|Norway|Switzerland|Romania|Greece|Hungary|Bulgaria|Croatia|Slovakia|Lithuania|Latvia|Estonia|Luxembourg/;
const KEYWORDS = new RegExp('(?:^|[^\\w-])(' + S.jd_keywords.map(k => k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')(?![\\w-])', 'i');

const searchLoc = {};
for (const s of S.searches) searchLoc[s.phrase] = s.location;
const decode = s => String(s || '').replace(/&#(\d+);/g, (_, n) => String.fromCharCode(+n))
  .replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>');
const esc = s => String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const norm = s => String(s || '').toLowerCase().replace(/\W+/g, ' ').trim();
// Agencies repost one role as "ML Engineer (Remote | $60–$120/hr)", "ML Engineer | Remote": compare the core title.
const coreTitle = t => norm(t.replace(/\(.*?\)|\[.*?\]/g, ' ').split(/\s[|–—-]\s/)[0]) || norm(t);
const around = (text, m, n = 60) => text.slice(Math.max(0, m.index - n), m.index + m[0].length + n).replace(/\s+/g, ' ').trim();

const now = Date.now(), keepMs = S.remember_days * 864e5;
for (const [k, t] of Object.entries(state.sent)) if (now - t > keepMs) delete state.sent[k];

const stats = { fetched: 0, failed_searches: 0, unique: 0, type: 0, remote: 0, relevant: 0, drop_list: 0, open_to_us: 0, already_sent: 0 };
const seenIds = new Set(), seenKeys = new Set(), out = [];
for (const item of $input.all()) {
  if (item.json.error) { stats.failed_searches++; continue; }
  for (const j of item.json.jobs || []) {
    stats.fetched++;
    const title = decode(j.title), company = decode(j.company), loc = decode(j.location), desc = decode(j.description);
    const key = j.is_post ? j.job_id : norm(company) + '|' + coreTitle(title);
    if (!j.job_id || seenIds.has(j.job_id) || seenKeys.has(key)) continue;   // same role is posted in many countries
    seenIds.add(j.job_id); seenKeys.add(key); stats.unique++;

    // Posts have no LinkedIn job type: the text must say contract / freelance / part-time.
    const tt = title.match(TITLE_TYPE) || (j.is_post && desc.match(TITLE_TYPE));
    const type = tt ? (tt[1].toLowerCase().startsWith('part') ? 'part-time' : 'contract') : String(j.employment_type || '').toLowerCase();
    if (!OK_TYPES.includes(type)) continue;
    stats.type++;

    const tz = desc.match(TZ_ABBR) || desc.match(TZ_WORDS);
    const remoteSaid = REMOTE.test(title + ' ' + loc) || (REMOTE.test(desc) && !NOT_REMOTE.test(desc));
    if (!remoteSaid && !tz && j.workplace_type === 'Hybrid') continue;
    const remote = remoteSaid || !!tz ? 'Remote' : 'remote not stated';
    stats.remote++;

    const kw = desc.match(KEYWORDS);
    if (BAD_TITLE.test(title) || !(AI_TITLE.test(title) || kw)) continue;
    stats.relevant++;

    const drop = (title + '\n' + desc).match(DROP);
    if (drop) continue;
    stats.drop_list++;

    const anyw = desc.match(ANYWHERE) || title.match(ANYWHERE);
    let tag, signal = '';
    if (/india/i.test(loc) || (j.is_post && /\bIndia\b/.test(desc))) tag = '🇮🇳';
    else if (anyw) { tag = '🌍'; signal = around(desc.includes(anyw[0]) ? desc : title, anyw); }
    else if (tz && !LOCAL_ONLY_LOC.test(loc)) { tag = '🕒'; signal = around(desc, tz); }
    else continue;
    if (tag === '🇮🇳' && tz) signal = around(desc, tz);
    stats.open_to_us++;

    if (state.sent[j.job_id] || state.sent[key]) { stats.already_sent++; continue; }

    const rate = (j.salary && decode(j.salary)) || ((title + ' ' + desc).match(RATE) || [''])[0];
    const url = j.job_url || ('https://www.linkedin.com/jobs/view/' + j.job_id);
    if (j.is_post) tag += '📣';
    const lines = [
      `${tag} <b>${esc(title)}</b>`,
      j.is_post ? `👤 ${esc(company)} · 📅 ${esc(j.posted_date)}` : `🏢 ${esc(company)} · 📍 ${esc(loc)}`,
      `📝 ${type} · ${remote}` + (j.experience_required ? ` · ${esc(j.experience_required)}` : '') + (rate ? ` · 💰 ${esc(rate)}` : ''),
    ];
    if (kw || AI_TITLE.test(title)) lines.push(`🎯 ${esc(kw ? kw[1] : 'AI title')}`);
    if (signal) lines.push(`🔎 <i>${esc(signal)}</i>`);
    lines.push(`🔗 ${esc(url)}`);
    lines.push(j.is_post ? `<i>via LinkedIn post search "${esc(j.search_title)}"</i>`
      : `<i>via "${esc(j.search_title)}" (${esc(searchLoc[j.search_title] || '')})</i>`);
    out.push({ company, tag, lines, keys: [j.job_id, key], rate,
      role: `${tag} <a href="${esc(url)}">${esc(title)}</a>` + (loc ? ` · ${esc(loc)}` : '') });
  }
}

// One message per company: agencies post the same gig under many titles at once.
const groups = {};
for (const m of out) { const g = norm(m.company) || m.keys[0]; (groups[g] = groups[g] || []).push(m); }
const msgs = Object.values(groups).map(g => {
  const text = g.length === 1 ? g[0].lines.join('\n') : [
    `🏢 <b>${esc(g[0].company)}</b> · ${g.length} roles` + (g[0].rate ? ` · 💰 ${esc(g[0].rate)}` : ''),
    ...g.slice(0, 10).map(m => m.role),
    ...(g.length > 10 ? [`+${g.length - 10} more`] : []),
  ].join('\n');
  return { json: { sent_keys: g.flatMap(m => m.keys), text, order: g.some(m => !m.tag.startsWith('🇮🇳')) ? 0 : 1 } };
});
msgs.sort((a, b) => a.json.order - b.json.order);
console.log('Filter Jobs', JSON.stringify(stats), 'jobs', out.length, 'messages', Math.min(msgs.length, S.max_messages_per_run));
return msgs.slice(0, S.max_messages_per_run);
