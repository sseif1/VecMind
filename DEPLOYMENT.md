# Deployment Guide

This guide covers deploying VecMind to various platforms.

## Prerequisites

- GitHub repository with your VecMind code
- OpenAI API key
- PostgreSQL database with pgvector extension (or use platform-provided database)

## Quick Deploy Options

### 🚂 Railway (Easiest - Recommended)

1. Go to [railway.app](https://railway.app) and sign up/login
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your VecMind repository
4. Railway will auto-detect the Dockerfile and start building
5. Add PostgreSQL:
   - Click "+ New" → "Database" → "Add PostgreSQL"
   - Railway automatically sets `DATABASE_URL`
6. Enable pgvector:
   - Go to PostgreSQL service → "Query" tab
   - Run: `CREATE EXTENSION vector;`
7. Set environment variable:
   - Go to your web service → "Variables"
   - Add: `OPENAI_API_KEY` = your OpenAI API key
8. Deploy! Your app will be live at `your-app.railway.app`

**Note:** Railway automatically handles `PORT` environment variable.

### 🎨 Render

1. Go to [render.com](https://render.com) and sign up
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Configure:
   - **Name**: vecmind (or your choice)
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add PostgreSQL database:
   - Click "New +" → "PostgreSQL"
   - Note the connection string
6. Enable pgvector:
   - Go to database → "Connect" → "psql"
   - Run: `CREATE EXTENSION vector;`
7. Set environment variables:
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `DATABASE_URL`: From your PostgreSQL database
8. Deploy!

### 🟣 Heroku

1. Install Heroku CLI: `brew install heroku/brew/heroku` (Mac) or [download](https://devcenter.heroku.com/articles/heroku-cli)
2. Login: `heroku login`
3. Create app: `heroku create your-app-name`
4. Add PostgreSQL: `heroku addons:create heroku-postgresql:mini`
5. Enable pgvector:
   ```bash
   heroku pg:psql
   CREATE EXTENSION vector;
   \q
   ```
6. Set environment variables:
   ```bash
   heroku config:set OPENAI_API_KEY=your_key_here
   ```
7. Deploy:
   ```bash
   git push heroku main
   ```

### 🐳 Docker (Self-hosted)

```bash
# Build image
docker build -t vecmind .

# Run with docker-compose (includes PostgreSQL)
docker-compose up -d

# Or run standalone (requires external PostgreSQL)
docker run -d \
  -p 8000:8000 \
  -e OPENAI_API_KEY=your_key \
  -e DATABASE_URL=postgresql://user:pass@host:5432/vecmind \
  --name vecmind \
  vecmind
```

## Post-Deployment Steps

### 1. Index Your Documents

After deployment, you need to index your documents:

```bash
# Via API
curl -X POST https://your-app-url.com/index

# Or via Heroku CLI
heroku run python -m app.ingest
```

### 2. Verify Deployment

Check that everything is working:

```bash
# Check document/chunk counts
curl https://your-app-url.com/debug/count

# Test search
curl -X POST https://your-app-url.com/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "top_k": 5}'
```

### 3. Access Web UI

Open your browser to: `https://your-app-url.com`

## Environment Variables

Required environment variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | Your OpenAI API key for embeddings |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `PORT` | No | Server port (usually auto-set by platform) |

## Troubleshooting

### Database Connection Issues

- Verify `DATABASE_URL` is set correctly
- Check that pgvector extension is enabled: `SELECT * FROM pg_extension WHERE extname = 'vector';`
- Ensure database is accessible from your deployment platform

### pgvector Extension Not Found

If you get errors about pgvector:

```sql
-- Connect to your database and run:
CREATE EXTENSION IF NOT EXISTS vector;
```

### Empty Search Results

1. Make sure documents are indexed: `POST /index`
2. Check logs for errors
3. Verify embeddings are being generated (check OpenAI API key)

### Port Issues

- Most platforms set `PORT` automatically
- If using Docker, ensure port mapping: `-p 8000:8000`
- Check platform-specific port configuration

## Platform-Specific Notes

### Railway
- Automatically detects Dockerfile
- PostgreSQL includes pgvector by default
- Free tier available with limitations

### Render
- Use `render.yaml` for configuration
- Free tier available
- PostgreSQL requires manual pgvector setup

### Heroku
- Uses `Procfile` for process definition
- Free tier discontinued, requires paid plan
- PostgreSQL addon includes pgvector support

### Docker
- Fully self-hosted
- Requires managing PostgreSQL separately
- Best for VPS/cloud instances

## Monitoring

After deployment, monitor:

1. **Application logs**: Check platform logs for errors
2. **Database usage**: Monitor PostgreSQL connection limits
3. **API usage**: Track OpenAI API usage and costs
4. **Performance**: Monitor search response times

## Scaling Considerations

- **Small scale** (< 1k documents): Current setup is fine
- **Medium scale** (1k-10k documents): Consider optimizing index parameters
- **Large scale** (> 10k documents): May need to optimize Python fallback or fix pgvector issue

## Security Notes

- Never commit `.env` file to git
- Use platform secrets management for API keys
- Consider adding authentication for production use
- Enable HTTPS (usually automatic on platforms)

