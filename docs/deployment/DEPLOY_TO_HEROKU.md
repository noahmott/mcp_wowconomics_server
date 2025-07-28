HEROKU DEPLOYMENT INSTRUCTIONS
==============================

1. INITIALIZE GIT (if not already done):
   git init
   git add .
   git commit -m "Initial commit for Heroku deployment"

2. CREATE HEROKU APP:
   heroku create your-app-name-here

3. ADD REDIS:
   heroku addons:create heroku-redis:mini

4. SET ENVIRONMENT VARIABLES:
   heroku config:set BLIZZARD_CLIENT_ID=your_client_id_here
   heroku config:set BLIZZARD_CLIENT_SECRET=your_client_secret_here
   
   OPTIONAL (for activity logging):
   heroku config:set SUPABASE_URL=your_supabase_url
   heroku config:set SUPABASE_KEY=your_supabase_key

5. DEPLOY:
   git push heroku main
   
   (or if using master branch):
   git push heroku master

6. VERIFY:
   heroku ps
   heroku logs --tail

7. OPEN APP:
   heroku open

TROUBLESHOOTING:
- If deployment fails, check: heroku logs --tail
- If Redis connection fails, verify: heroku config:get REDIS_URL
- For performance issues, scale up: heroku ps:resize web=standard-1x

COSTS:
- Basic Dyno: $7/month
- Redis Mini: $3/month
- Total: ~$10/month