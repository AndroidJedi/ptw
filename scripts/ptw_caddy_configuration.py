#!/usr/bin/env python3
"""Manage only PTW's host block inside the independent platform configuration."""
import argparse
from pathlib import Path
import re
import subprocess

FRAGMENT = 'deploy/owner-gateway/Caddyfile.fragment'
DESTINATION = 'infrastructure/caddy/Caddyfile'

def render(content, fragment):
    host = fragment.split('{', 1)[0].strip()
    matches = list(re.finditer(r'(?m)^(?:' + re.escape(host) + r'|\{\$COMMANDER_PUBLIC_HOST\})[ \t]*\{', content))
    if len(matches) != 1:
        raise ValueError('Exactly one existing Owner Gateway Caddy host block is required')
    start = matches[0]
    depth, index = 1, start.end()
    while depth and index < len(content):
        depth += (content[index] == '{') - (content[index] == '}')
        index += 1
    if depth:
        raise ValueError('Owner Gateway Caddy block is incomplete')
    replacement = fragment.strip()
    if 'import security_headers' in content[start.end():index] and 'import security_headers' not in replacement:
        replacement = replacement.replace('{', '{\n    import security_headers', 1)
    return content[:start.start()] + replacement + content[index:]

def git(repository, *arguments):
    return subprocess.check_output(['git', '-C', str(repository), *arguments], text=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('apply', 'verify'))
    parser.add_argument('--repository', default='/root/ptw')
    parser.add_argument('--platform', default='/opt/ptw/platform')
    args = parser.parse_args()
    repository, platform = Path(args.repository), Path(args.platform)
    accepted = (repository / '.local/deployed-revision').read_text().strip()
    accepted_fragment = git(repository, 'show', accepted + ':' + FRAGMENT)
    destination = platform / DESTINATION
    original = git(platform, 'show', 'HEAD:' + DESTINATION)
    current = destination.read_text()
    if args.action == 'verify':
        if current not in (original, render(original, accepted_fragment)):
            raise SystemExit('Platform Caddy changes do not match the accepted PTW host configuration')
    else:
        fragment = (repository / FRAGMENT).read_text()
        if fragment == accepted_fragment:
            print('unchanged')
            return
        desired = render(original, fragment)
        if current != desired:
            destination.write_text(desired)
            print('changed')
        else:
            print('unchanged')

if __name__ == '__main__':
    main()
