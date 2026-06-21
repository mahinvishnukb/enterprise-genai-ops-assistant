# Pushing this to your own GitHub repo

This folder has a leftover `.git/` directory from a sandbox build step that
didn't fully clean up — delete it first so you start with a clean repo on
your own machine:

```bash
cd enterprise-genai-ops-assistant
rm -rf .git
```

Then create a new empty repo on GitHub (no README/license, since this
folder already has one), and:

```bash
git init
git add -A
git commit -m "Initial commit: Enterprise GenAI Operations Assistant"
git branch -M main
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
```

Once pushed, the GitHub Actions workflow (`.github/workflows/ci.yml`) runs
automatically and you'll get a green check / CI badge on the repo — that's
what you want visible before pointing anyone to it.

Optional badge for your README, once pushed (replace the path):

```markdown
![CI](https://github.com/<your-username>/<repo-name>/actions/workflows/ci.yml/badge.svg)
```
