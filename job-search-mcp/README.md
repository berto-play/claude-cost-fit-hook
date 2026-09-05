# Job Search for Claude

Search live job openings from inside Claude. Ask "find senior product designer
roles in remote US paying over 150k" and get real listings back, with apply links.

## The honest part about LinkedIn

You asked for LinkedIn. This does not use LinkedIn, on purpose:

- LinkedIn has no open jobs API.
- Scraping it breaks their terms of service, and they have sued over it. Risk is
  a banned account plus legal exposure.

So this uses **Adzuna** instead: a free, legal API that pulls listings from many
job boards at once. Most roles that show up on LinkedIn also show up here. You get
the same jobs without the risk.

## What you get

One tool, `search_jobs`, that takes:

- `what` (required): keywords or job title
- `where`: location, including "remote"
- `country`: two-letter code, default `us`
- `results`: how many, 1 to 50, default 10
- `salary_min`: floor on pay
- `max_days_old`: only recent postings
- `full_time`: true to skip part-time
- `sort_by`: `relevance`, `date`, or `salary`

## Setup (about 5 minutes)

### 1. Get free Adzuna keys

- Go to https://developer.adzuna.com and register an app.
- Copy your **App ID** and **App Key**. The free tier is enough for personal use.

### 2. Add the server to Claude

You need the full path to `jobs_server.py`. From this folder, run `pwd` to get it.

**Claude Code (command line):**

```bash
claude mcp add \
  -e ADZUNA_APP_ID=your_id_here \
  -e ADZUNA_APP_KEY=your_key_here \
  -t stdio \
  job-search \
  -- python3 /absolute/path/to/job-search-mcp/jobs_server.py
```

Add `-s user` before `job-search` to make it available in every project, not just
this one.

**Claude Desktop:**

Open the config file:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Add this (merge into `mcpServers` if the block already exists):

```json
{
  "mcpServers": {
    "job-search": {
      "command": "python3",
      "args": ["/absolute/path/to/job-search-mcp/jobs_server.py"],
      "env": {
        "ADZUNA_APP_ID": "your_id_here",
        "ADZUNA_APP_KEY": "your_key_here"
      }
    }
  }
}
```

### 3. Restart Claude

Quit Claude completely and reopen it. Then ask it to search for jobs.

## Check it works

No keys or internet needed for this. It tests the server itself:

```bash
python3 jobs_server.py --selftest
```

You should see `SELFTEST PASSED`.

## Requirements

- Python 3.8 or newer
- No pip install. Standard library only.

## Notes

- Your keys stay on your machine, in your Claude config. They are never sent
  anywhere except Adzuna.
- If a search returns nothing, try broader keywords or drop the location.
- Rate limits are Adzuna's, not this server's. The free tier is generous for
  one person.

## Country codes

`at` `au` `be` `br` `ca` `ch` `de` `es` `fr` `gb` `in` `it` `mx` `nl` `nz` `pl`
`sg` `us` `za`
