#!/bin/bash
# Deploy blogs AND rebuild index — runs hourly via cron
bash ~/tools/deploy-blog.sh 2>/dev/null
bash ~/tools/auto-index.sh 2>/dev/null
