// ── EDIT SETTINGS HERE ──
// Remote contract / part-time AI jobs that hire from India or anywhere, from LinkedIn (self-hosted scraper).
// The scraper only fetches; every filter lives in "Filter Jobs". New matches go to Telegram, each job once.
return [{ json: {
  scraper_url: 'http://linkedin-scraper:8000/scrape-jobs',
  date_posted: '24h',               // 24h | week | month
  count_per_search: 20,             // LinkedIn returns 10 per page

  // location 'India' = jobs listed in India (many are foreign companies hiring remote contractors).
  // location 'Worldwide' = abroad listings; kept only if the JD says Global/anywhere/APAC/India or names a timezone.
  searches: [
    { phrase: 'AI Engineer contract remote',                       location: 'India' },
    { phrase: 'Machine Learning Researcher contract remote',       location: 'India' },
    { phrase: 'LLM Engineer contract remote',                      location: 'India' },
    { phrase: 'Senior Machine Learning Engineer contract remote',  location: 'India' },
    { phrase: 'AI Agent Developer contract remote',                location: 'India' },
    { phrase: 'LLM fine-tuning engineer contract',                 location: 'India' },
    { phrase: 'AI Researcher contract remote worldwide',           location: 'Worldwide' },
    { phrase: 'AI Engineer contract remote US time zone',          location: 'Worldwide' },
    { phrase: 'AI Engineer contract work from anywhere',           location: 'Worldwide' },
  ],

  // A job is relevant if its title is an AI role OR the JD mentions any one of these.
  jd_keywords: ['LangChain', 'LangGraph', 'LLM', 'LLMs', 'multi-agent', 'multiagent', 'agentic', 'RAG',
                'retrieval-augmented', 'generative AI', 'GenAI'],

  max_messages_per_run: 25,
  remember_days: 45,                // a job is not sent again for this long

  telegram_url: '__TELEGRAM_URL__',
  telegram_chat_id: '__TELEGRAM_CHAT_ID__',
}}];
