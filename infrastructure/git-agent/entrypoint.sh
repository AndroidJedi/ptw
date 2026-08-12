#!/bin/sh
set -eu
install -d -o ptw -g ptw -m 0700 /run/ptw-git-agent
agent_output=$(su-exec ptw ssh-agent -a /run/ptw-git-agent/agent.sock -s)
eval "$agent_output"
SSH_AUTH_SOCK=/run/ptw-git-agent/agent.sock su-exec ptw \
  ssh-add -h github.com -H /run/ptw-known-hosts/known_hosts - \
  </run/ptw-deploy-key/id_ed25519 >/dev/null
trap 'ssh-agent -k >/dev/null' TERM INT EXIT
while kill -0 "$SSH_AGENT_PID" 2>/dev/null; do sleep 5; done
