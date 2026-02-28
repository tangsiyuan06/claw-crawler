#!/usr/bin/env python3
"""
Find Skills - OpenClaw Skill Discovery Tool
Searches for OpenClaw skills on ClawHub and GitHub
"""

import sys
import json
import subprocess
import os

def search_skills(query, max_results=10):
    """Search for OpenClaw skills using SearXNG"""
    try:
        # Use the existing searxng skill
        search_query = f"site:clawhub.com OR site:github.com openclaw skill {query}"
        
        # Execute searxng search
        result = subprocess.Popen([
            'uv', 'run', '/home/admin/.openclaw/workspace/skills/searxng/scripts/searxng.py',
            'search', search_query, '-n', str(max_results), '--format', 'json'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd='/home/admin/.openclaw/workspace')
        
        stdout, stderr = result.communicate()
        
        if result.returncode == 0:
            return json.loads(stdout.decode('utf-8'))
        else:
            print("Search failed: " + stderr.decode('utf-8'), file=sys.stderr)
            return []
            
    except Exception as e:
        print("Error during search: " + str(e), file=sys.stderr)
        return []

def install_skill(skill_url, workspace_path):
    """Install a skill from URL to specified workspace"""
    try:
        skill_name = skill_url.split('/')[-1]
        skills_dir = os.path.join(workspace_path, 'skills')
        target_dir = os.path.join(skills_dir, skill_name)
        
        # Create skills directory if it doesn't exist
        if not os.path.exists(skills_dir):
            os.makedirs(skills_dir)
        
        # Clone the repository
        result = subprocess.Popen(['git', 'clone', skill_url, target_dir], 
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = result.communicate()
        
        if result.returncode == 0:
            print("Successfully installed skill: " + skill_name)
            return True
        else:
            print("Git clone failed: " + stderr.decode('utf-8'), file=sys.stderr)
            return False
        
    except Exception as e:
        print("Failed to install skill: " + str(e), file=sys.stderr)
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: find-skills.py <search|install> [query|url]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "search":
        if len(sys.argv) < 3:
            print("Usage: find-skills.py search <query>")
            sys.exit(1)
        query = " ".join(sys.argv[2:])
        results = search_skills(query)
        print(json.dumps(results, indent=2))
        
    elif command == "install":
        if len(sys.argv) < 4:
            print("Usage: find-skills.py install <skill_url> <workspace_path>")
            sys.exit(1)
        skill_url = sys.argv[2]
        workspace_path = sys.argv[3]
        install_skill(skill_url, workspace_path)
        
    else:
        print("Unknown command: " + command)
        sys.exit(1)

if __name__ == "__main__":
    main()