# n8n Workflows

Automation workflows for [n8n](https://n8n.io/). These workflows integrate with the plugin's PostgreSQL database to automate social media posting and other tasks.

## Setup

### Prerequisites

- n8n instance (self-hosted or cloud)
- PostgreSQL database configured (see `tools/database/README.md`)
- Platform credentials (Twitter/X OAuth2, etc.)

### Import a Workflow

1. Open your n8n instance
2. Go to **Workflows** > **Add workflow** > **Import from file**
3. Select the `.json` file from this directory
4. Update credential references to match your n8n credential names
5. Activate the workflow

### Credentials

Workflow files use placeholder credential IDs (`<your-credential-id>`). After importing, you'll need to configure each node's credentials to point to your own:

- **PostgreSQL** — connection to your database
- **Twitter/X OAuth2** — required for posting tweets and uploading media. Create an app at [developer.x.com](https://developer.x.com/), enable OAuth 2.0 with read/write permissions, then add the credentials in n8n as a "Twitter OAuth2 API" type. The workflow uses this for both the native Twitter node (text-only posts) and HTTP Request nodes (chunked media uploads via X API v2).

## Workflows

### Auto Post to Twitter/X

**File:** `n8n-auto-post-twitter.json`

Automatically posts tweets from the database on a schedule. Picks a random post from the least-posted pool, handles media uploads (chunked video upload via X API v2), and tracks post counts.

**Schedule:** 4x daily (8:00 AM, 11:30 AM, 5:30 PM, 8:30 PM)

**Flow:**
1. Query enabled tweets from database (least-posted first)
2. Pick a random tweet from the least-posted pool
3. Check if tweet has media attached
4. **With media:** Read file > chunked upload to X API > post with media > update DB
5. **Text only:** Post tweet > update DB
6. Mark tweet as posted, increment `times_posted`, set `posted_at`

**Cost:** Twitter/X API uses a credit system. Posting a tweet costs ~$0.01 per tweet.

**Database requirements:**
- Albums and tracks synced via `db_sync_album` MCP tool
- Tweets created via `db_create_tweet` with `enabled = true`
- Media paths must be accessible from the n8n server's filesystem
