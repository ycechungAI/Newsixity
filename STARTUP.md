# Newsixity Startup Guide

## Quick Start

### Manual Start
To start the app manually, run:
```bash
./start.sh
```

This will:
- Start Ollama server
- Start Next.js dev server
- Open Brave browser to http://localhost:3000

### Manual Stop
To stop all services:
```bash
./stop.sh
```

Or use the **STOP** button in the Console page at http://localhost:3000/console

---

## First-Time Setup

After cloning the repository, run:
```bash
npm install
npm run hooks:install   # installs the git pre-commit lint hook
```

See [README.md](./README.md) for full setup instructions including environment
variables, Deep Research configuration, and the macOS auto-start agent.

---

## Auto-Start on Login (macOS)

The Launch Agent has been created at:
```
~/Library/LaunchAgents/com.newsixity.startup.plist
```

### Enable Auto-Start

Load the Launch Agent:
```bash
launchctl load ~/Library/LaunchAgents/com.newsixity.startup.plist
```

The app will now start automatically when you log in to your Mac.

### Disable Auto-Start

To stop auto-starting on login:
```bash
launchctl unload ~/Library/LaunchAgents/com.newsixity.startup.plist
```

### Check Status

To see if the Launch Agent is loaded:
```bash
launchctl list | grep newsixity
```

### View Logs

If auto-start isn't working, check the logs:
```bash
cat /tmp/newsixity-startup.log
cat /tmp/newsixity-startup-error.log
```

---

## Troubleshooting

### Brave Browser Not Opening
If Brave doesn't open automatically, make sure it's installed in `/Applications/Brave Browser.app`

### Ollama Not Starting
Make sure Ollama is installed:
```bash
brew install ollama
```

### Next.js Not Starting
Make sure dependencies are installed:
```bash
npm install
```

### Port Already in Use
If port 3000 is already in use, stop other processes:
```bash
lsof -ti:3000 | xargs kill -9
```

---

## Files

- `start.sh` - Startup script
- `stop.sh` - Stop script
- `~/Library/LaunchAgents/com.newsixity.startup.plist` - macOS Launch Agent

## Console Controls

Access the Console at http://localhost:3000/console to:
- View summarization queue
- See system logs
- Trigger a manual database backup
- **STOP** all servers with one click
