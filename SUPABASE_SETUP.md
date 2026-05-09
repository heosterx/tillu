# Supabase Environment Setup

## ✅ Completed

1. **MCP Server Configured**
   - Location: `.kiro/settings/mcp.json`
   - Project: `dpkmzkyzvmysvzmevhrm`
   - Restart Kiro or reconnect MCP server to activate

2. **Agent Skills Installed**
   - `supabase` — general best practices
   - `supabase-postgres-best-practices` — performance optimization
   - Location: `.agents/skills/`

3. **Environment Files Updated**
   - `.env` — local development (created)
   - `.env.production` — production deployment (updated)
   - Both files have Supabase URL and anon key pre-filled

## 🔑 Missing Keys (Manual Setup Required)

You need to manually add these from the [Supabase Dashboard](https://supabase.com/dashboard/project/dpkmzkyzvmysvzmevhrm/settings/api):

### In both `.env` and `.env.production`:

1. **Service Role Key** (backend only, bypasses RLS)
   ```bash
   SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   ```
   - Dashboard → Settings → API → `service_role` (secret)

2. **JWT Secret** (for token verification)
   ```bash
   SUPABASE_JWT_SECRET=your-jwt-secret-here
   ```
   - Dashboard → Settings → API → JWT Settings → JWT Secret

## 📋 Already Configured

```bash
# Project URL
SUPABASE_URL=https://dpkmzkyzvmysvzmevhrm.supabase.co

# Publishable key (modern format)
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_wzhLbkG23DHYpPLWQ34Brw_KN3XxcfO

# Anon key (legacy format, safe for client-side)
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRwa216a3l6dm15c3Z6bWV2aHJtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzgxNDQ4NTMsImV4cCI6MjA5MzcyMDg1M30.DkEJLAETuU_Df3MPwJXGKr1qYIaIP0KJRjsEA1e7awA
```

## 🚀 Next Steps

1. Add the missing service role key and JWT secret to `.env`
2. Test the connection:
   ```bash
   python -c "from app.config import settings; print(settings.SUPABASE_URL)"
   ```
3. Initialize the database schema:
   ```bash
   # Apply the schema from supabase/schema.sql
   ```

## 🔗 Quick Links

- [API Settings](https://supabase.com/dashboard/project/dpkmzkyzvmysvzmevhrm/settings/api)
- [Database](https://supabase.com/dashboard/project/dpkmzkyzvmysvzmevhrm/editor)
- [Table Editor](https://supabase.com/dashboard/project/dpkmzkyzvmysvzmevhrm/editor)
- [SQL Editor](https://supabase.com/dashboard/project/dpkmzkyzvmysvzmevhrm/sql)
