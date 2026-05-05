#!/bin/bash
# Push a local agent repo to GitHub as a new public repo
# Usage: bash tools/push-agent-repo.sh <directory-name> [description]

REPO_DIR="$1"
DESC="${2:-Autonomous agent built by Seed}"

if [ -z "$REPO_DIR" ]; then
    echo "Usage: bash tools/push-agent-repo.sh <directory> [description]"
    exit 1
fi

FULL_PATH="$HOME/$REPO_DIR"
if [ ! -d "$FULL_PATH" ]; then
    echo "Directory $FULL_PATH does not exist"
    exit 1
fi

TOKEN=$(grep github ~/.git-credentials | sed "s|.*x:||;s|@.*||")
if [ -z "$TOKEN" ]; then
    echo "No GitHub token found in ~/.git-credentials"
    exit 1
fi

# Create the repo on GitHub
echo "[push-agent] Creating github.com/seedpi867-cmd/$REPO_DIR..."
RESULT=$(curl -sf -X POST \
    -H "Authorization: token $TOKEN" \
    -H "Accept: application/vnd.github+json" \
    https://api.github.com/user/repos \
    -d "{\"name\":\"$REPO_DIR\",\"description\":\"$DESC\",\"private\":false}" 2>/dev/null)

URL=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('html_url',''))" 2>/dev/null)

if [ -z "$URL" ]; then
    # Repo might already exist
    URL="https://github.com/seedpi867-cmd/$REPO_DIR"
    echo "[push-agent] Repo may already exist: $URL"
fi

cd "$FULL_PATH"

# Init git if needed
if [ ! -d .git ]; then
    git init
    git branch -m main
    git add -A
    git commit -m "Initial: $REPO_DIR agent"
fi

# Set remote
git remote remove origin 2>/dev/null
git remote add origin "https://github.com/seedpi867-cmd/$REPO_DIR.git"

# Push
git -c "http.https://github.com/.extraheader=AUTHORIZATION: token $TOKEN" push -u origin main 2>&1

# Do not leave a credential-bearing remote in the child checkout.
git remote set-url origin "https://github.com/seedpi867-cmd/$REPO_DIR.git"
git remote set-url --push origin "https://github.com/seedpi867-cmd/$REPO_DIR.git"

echo "[push-agent] Done: $URL"
