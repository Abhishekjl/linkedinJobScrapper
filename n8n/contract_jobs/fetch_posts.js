// Fetch Posts: LinkedIn posts about contract AI roles ("We're hiring ... DM me"), found with web search, read logged out.
// Too few found (search engines block this server): fall back to Apify LinkedIn post search, within a monthly post budget.
// Passes the scraper results through and adds the posts as one more result, shaped like jobs, for "Filter Jobs".
const S = $('Settings').first().json;
const h = this.helpers;
const state = $getWorkflowStaticData('global');
const sent = state.sent || {};
const sleep = ms => new Promise(r => setTimeout(r, ms));
const POST_URL = /^https:\/\/(?:[a-z]{2,3}\.)?linkedin\.com\/posts\/[^?#]*?activity-(\d{19})[^?#]*/;
// The post id carries its timestamp (ms since epoch in the top bits).
const postedAt = id => Number(BigInt(id) >> 22n);

const found = new Map();
let failedSearches = 0;
for (const q of S.post_queries) {
  try {
    // No time_range: Yahoo returns nothing with it. Old posts are dropped below by post date.
    const r = await h.httpRequest({ method: 'GET', url: S.searxng_url, qs: { q: 'site:linkedin.com/posts ' + q, format: 'json' }, json: true, timeout: 30000 });
    for (const x of r.results || []) {
      const m = String(x.url || '').match(POST_URL);
      if (m && !found.has(m[1])) found.set(m[1], { id: m[1], url: m[0], query: q, snippet: `${x.title || ''}\n${x.content || ''}` });
    }
  } catch (e) { failedSearches++; }
  await sleep(15000);   // spaced out: Google (via SearXNG) suspends us for an hour after a burst
}

const minTime = Date.now() - S.post_max_age_days * 864e5;
const todo = [...found.values()].filter(p => postedAt(p.id) >= minTime && !sent['post:' + p.id])
  .sort((a, b) => postedAt(b.id) - postedAt(a.id)).slice(0, S.max_posts_per_run);

const jobs = [];
let unread = 0;
for (const p of todo) {
  let post = null;
  try {
    const html = String(await h.httpRequest({ method: 'GET', url: p.url, timeout: 20000, headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
      'Accept-Language': 'en-US,en;q=0.9' } }));
    const ld = html.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/);
    post = ld ? JSON.parse(ld[1]) : null;
  } catch (e) { post = null; }
  // Login wall or error: fall back to the search snippet.
  if (!post || !post.articleBody) unread++;
  const text = (post && post.articleBody) || p.snippet;
  jobs.push({
    job_id: 'post:' + p.id, is_post: true,
    title: (text.split('\n').map(l => l.trim()).find(Boolean) || '').slice(0, 150),
    company: (post && post.author && post.author.name) || '', location: '', employment_type: '',
    description: text, job_url: p.url, posted_date: new Date(postedAt(p.id)).toISOString().slice(0, 10), search_title: p.query,
  });
  await sleep(2500);
}

// Fallback: Apify charges per post returned, so count them per calendar month.
const month = new Date().toISOString().slice(0, 7);
if (!state.apify || state.apify.month !== month) state.apify = { month, posts: 0 };
const budget = S.apify_max_posts_per_month - state.apify.posts;
let apify = 'not needed';
if (jobs.length < S.apify_min_posts && S.apify_token && budget >= S.apify_queries.length * S.apify_posts_per_query) {
  try {
    const items = await h.httpRequest({ method: 'POST', json: true, timeout: 300000,
      url: `https://api.apify.com/v2/acts/${S.apify_actor}/run-sync-get-dataset-items?timeout=240`,
      headers: { Authorization: 'Bearer ' + S.apify_token },
      body: { searchQueries: S.apify_queries, maxPosts: S.apify_posts_per_query, postedLimit: '24h', sortBy: 'date', profileScraperMode: 'short' } });
    const list = Array.isArray(items) ? items : [];
    state.apify.posts += list.length;
    const have = new Set(jobs.map(j => j.job_id));
    let added = 0;
    for (const x of list) {
      const id = String(x.id || ''), text = String(x.content || '');
      if (!/^\d{19}$/.test(id) || !text || have.has('post:' + id) || sent['post:' + id] || postedAt(id) < minTime) continue;
      have.add('post:' + id); added++;
      jobs.push({
        job_id: 'post:' + id, is_post: true,
        title: (text.split('\n').map(l => l.trim()).find(Boolean) || '').slice(0, 150),
        company: (x.author && x.author.name) || '', location: '', employment_type: '',
        description: text, job_url: x.linkedinUrl || `https://www.linkedin.com/feed/update/urn:li:activity:${id}/`,
        posted_date: new Date(postedAt(id)).toISOString().slice(0, 10), search_title: (x.query && x.query.search) || 'Apify',
      });
    }
    apify = `${list.length} posts, ${added} new`;
  } catch (e) { apify = 'error: ' + String(e.message || e).slice(0, 120); }
} else if (jobs.length < S.apify_min_posts) apify = S.apify_token ? 'monthly budget used' : 'no token';
console.log('Fetch Posts', JSON.stringify({ found: found.size, failed_searches: failedSearches, new_recent: todo.length, unread,
  apify, apify_posts_this_month: state.apify.posts }));
return [...$input.all(), { json: { jobs } }];
