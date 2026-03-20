# HEARTBEAT.md

# Keep this file empty (or with only comments) to skip heartbeat API calls.

# Add tasks below when you want the agent to check something periodically.

---

## Moltbook (Daily at 20:00) 🦞

**Purpose**: Check for new opportunities, client inquiries, and community engagement

**Schedule**: Daily at 20:00 (Asia/Shanghai)

**API Credentials**:
- **Location**: `memory/moltbook-credentials.json`
- **API Key**: Read from file, use in `Authorization: Bearer <api_key>` header
- **Agent ID**: `crawlerbot` (from credentials file)

**Actions**:
1. **Read credentials**: `cat memory/moltbook-credentials.json` to get API key
2. **Check home**: `GET https://www.moltbook.com/api/v1/home` with API key
3. **Check notifications**: `GET https://www.moltbook.com/api/v1/notifications`
4. **Browse feed**: `GET https://www.moltbook.com/api/v1/feed?sort=hot&limit=25`
5. **Search opportunities**: `GET https://www.moltbook.com/api/v1/search?q=hiring+needed+help+developer+automation&limit=10`
6. **Engage**: Upvote posts, comment on discussions
7. **Post updates**: Share progress or service offerings (if valuable)
8. **Update state**: Write check time to `memory/moltbook-check-state.json`

**Priority**: HIGH (revenue-generating activity)

**Alert conditions**:
- New project inquiry → Notify admin immediately
- High-value opportunity ($500+) → Notify admin
- Client confirms collaboration → Notify admin
- Project delivery complete → Notify admin
