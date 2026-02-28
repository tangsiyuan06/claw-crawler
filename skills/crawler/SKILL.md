---
name: crawler
description: Advanced web crawling and content extraction. Handles JavaScript-heavy sites, anti-bot measures, and complex web structures.
author: Ops Administrator
version: 1.0.0
homepage: https://github.com/tangsiyuan06/claw-ops
triggers:
  - "crawl"
  - "scrape"
  - "extract from website"
  - "get content from"
  - "visit and extract"
metadata: {"clawdbot":{"emoji":"🕷️","requires":{"bins":["python3","chromium-browser"]}}}
---

# Web Crawler Skill

Advanced web crawling capabilities for extracting content from complex websites.

## Features
- 🕸️ **Browser Automation**: Full Chromium browser control with JavaScript support
- 🛡️ **Anti-bot Bypass**: Handle common anti-bot measures and CAPTCHAs
- 📊 **Structured Data**: Extract and format data as JSON, CSV, or markdown
- ⚡ **Headless Mode**: Fast headless browsing for efficiency
- 🔍 **Smart Extraction**: Auto-detect main content and remove noise
- 🌐 **Multi-format Support**: Handle HTML, JSON APIs, dynamic content

## Commands

### Basic Crawling
```bash
# Simple page fetch
uv run {baseDir}/scripts/crawler.py --url "https://example.com" --output json

# With JavaScript rendering
uv run {baseDir}/scripts/crawler.py --url "https://example.com" --js --wait 5 --output markdown

# Extract specific elements
uv run {baseDir}/scripts/crawler.py --url "https://example.com" --selector ".article-content" --output text
```

### Advanced Options
```bash
# Handle authentication
uv run {baseDir}/scripts/crawler.py --url "https://example.com" --auth "user:pass" --output json

# Custom headers
uv run {baseDir}/scripts/crawler.py --url "https://example.com" --header "User-Agent: CustomBot" --output json

# Rate limiting
uv run {baseDir}/scripts/crawler.py --url "https://example.com" --delay 2 --output json
```

## Configuration
- Requires Chromium/Chrome browser installed
- Supports proxy configuration via environment variables
- Respects robots.txt by default (can be disabled)
- Automatic retry with exponential backoff

## Use Cases
- Extract news articles and blog posts
- Scrape product information from e-commerce sites
- Gather data from JavaScript-heavy applications
- Monitor website changes and updates
- Access content behind simple login forms