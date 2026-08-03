# MTU Journal Evaluator - Deployment Guide

## Free Deployment Options

### Option 1: Render.com (Recommended - Easiest)

**Why Render:** Free PostgreSQL database + free web service, supports Docker natively, no credit card required.

**Steps:**

1. **Push to GitHub:**
   ```bash
   cd /Users/kamaljitsinghrajkumar/mtu-journal-evaluator
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/mtu-journal-evaluator.git
   git push -u origin main
   ```

2. **Create Render Account:**
   - Go to https://render.com
   - Sign up with GitHub

3. **Deploy via render.yaml:**
   - Click "New" → "Blueprint"
   - Connect your GitHub repo
   - Render will detect `render.yaml` and create:
     - PostgreSQL database (free tier)
     - Web service (free tier)
     - Scheduled job for quarterly re-evaluation

4. **Set Environment Variables:**
   - After deployment, go to your web service settings
   - Set `SECRET_KEY` to a strong random value
   - Set `ADMIN_PASSWORD` to your secure password

5. **Access Your App:**
   - Your app will be at `https://mtu-journal-evaluator.onrender.com`
   - Login: `mtu_admin` / your ADMIN_PASSWORD

**Database:** Render PostgreSQL (free tier: 256 MB storage, expires after 90 days of inactivity)

---

### Option 2: Fly.io (Most Generous Free Tier)

**Why Fly.io:** 3 free VMs, 256 MB RAM each, free PostgreSQL with 3 GB storage.

**Steps:**

1. **Install Fly CLI:**
   ```bash
   brew install flyctl
   ```

2. **Login and Initialize:**
   ```bash
   cd /Users/kamaljitsinghrajkumar/mtu-journal-evaluator
   fly auth login
   fly launch
   ```

3. **Follow the prompts:**
   - App name: `mtu-journal-evaluator`
   - Region: Choose closest to you
   - PostgreSQL: Yes (free tier)
   - Redis: No

4. **Set Secrets:**
   ```bash
   fly secrets set SECRET_KEY=$(openssl rand -hex 32)
   fly secrets set ADMIN_PASSWORD=your-secure-password
   ```

5. **Deploy:**
   ```bash
   fly deploy
   ```

6. **Access Your App:**
   - Your app will be at `https://mtu-journal-evaluator.fly.dev`
   - Login: `mtu_admin` / your ADMIN_PASSWORD

**Database:** Fly.io PostgreSQL (free tier: 3 GB storage, 3 VMs)

---

### Option 3: Vercel (Serverless - Limited)

**Why Vercel:** Fast global CDN, generous free tier, but serverless limitations apply.

**Limitations:**
- 10-second timeout per request (60s for Pro)
- 50MB deployment size
- Read-only filesystem (except /tmp)
- No persistent storage without external database

**Steps:**

1. **Install Vercel CLI:**
   ```bash
   npm install -g vercel
   ```

2. **Deploy:**
   ```bash
   cd /Users/kamaljitsinghrajkumar/mtu-journal-evaluator
   vercel
   ```

3. **Set Environment Variables:**
   ```bash
   vercel env add DATABASE_URL
   vercel env add SECRET_KEY
   vercel env add ADMIN_PASSWORD
   ```

4. **Database:** Use Neon.tech or Supabase for free PostgreSQL

**Note:** For Vercel, the SQLite database won't work. You MUST use PostgreSQL via DATABASE_URL.

---

### Option 4: Railway (Alternative)

**Why Railway:** $5 free credits monthly, PostgreSQL included.

**Steps:**

1. **Push to GitHub** (same as above)
2. **Go to https://railway.app**
3. **New Project** → Deploy from GitHub repo
4. **Add PostgreSQL** plugin
5. **Set environment variables**
6. **Deploy**

---

## Free Database Providers

### Neon.tech (Recommended for Vercel)
- Free tier: 3 GB storage, 100 compute hours/month
- Sign up at https://neon.tech
- Create a project → copy connection string
- Use as `DATABASE_URL`

### Supabase
- Free tier: 500 MB storage, 2 projects
- Sign up at https://supabase.com
- Create project → copy connection string from Settings → Database
- Use as `DATABASE_URL`

### Render PostgreSQL
- Free tier: 256 MB storage
- Automatically created with Render web service

### Fly.io PostgreSQL
- Free tier: 3 GB storage
- Automatically created with `fly launch`

---

## Production Checklist

Before deploying:

1. **Change Admin Password:**
   - Set `ADMIN_PASSWORD` environment variable to a strong password
   - Do NOT use the default password in production

2. **Generate Secret Key:**
   ```bash
   openssl rand -hex 32
   ```
   - Set as `SECRET_KEY` environment variable

3. **Database:**
   - Use PostgreSQL (not SQLite) for production
   - Set `DATABASE_URL` environment variable
   - The app will automatically use PostgreSQL when DATABASE_URL is set

4. **HTTPS:**
   - Render, Fly.io, and Vercel all provide HTTPS automatically
   - Do NOT disable HTTPS in production

5. **Backup:**
   - Export database regularly
   - Render: Manual export from dashboard
   - Fly.io: `fly postgres backup`
   - Supabase: Built-in backup

---

## Local Development with PostgreSQL

If you want to test with PostgreSQL locally:

1. **Install PostgreSQL:**
   ```bash
   brew install postgresql@14
   brew services start postgresql@14
   ```

2. **Create Database:**
   ```bash
   createdb mtu_journal_evaluator
   ```

3. **Set Environment Variable:**
   ```bash
   export DATABASE_URL=postgresql://localhost:5432/mtu_journal_evaluator
   ```

4. **Run App:**
   ```bash
   python run.py --web
   ```

---

## Troubleshooting

**Database Connection Issues:**
- Ensure `DATABASE_URL` is set correctly
- For Neon/Supabase, use `postgresql://` not `postgres://`
- Check firewall rules allow connections from your deployment platform

**Deployment Failures:**
- Check logs in platform dashboard
- Ensure all dependencies are in `requirements.txt`
- Verify `PYTHONPATH` includes the `src` directory

**Performance:**
- Adjust worker count: `--workers 2` for free tier, `--workers 4` for paid
- Increase timeout: `--timeout 120` for batch operations
- Use connection pooling for PostgreSQL (already configured in SQLAlchemy)
