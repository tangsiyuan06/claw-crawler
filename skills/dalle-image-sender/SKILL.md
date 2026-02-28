---
name: dalle-image-sender
description: Download Azure DALL-E generated images and send them via Feishu. Handles temporary URL limitations and provides reliable image delivery.
author: Ops Administrator
version: 1.0.0
triggers:
  - "send image"
  - "deliver image"
  - "forward image"
metadata: {"clawdbot":{"emoji":"🖼️","requires":{"bins":["curl","jq"]}}}
---

# DALL-E Image Sender

Automatically downloads images from Azure DALL-E and sends them via Feishu messaging.

## Problem Solved
Azure DALL-E generates temporary signed URLs that:
- Expire after a few hours
- May have IP restrictions
- Cannot be reliably shared directly

## Solution
This skill:
1. Downloads the image from Azure's temporary URL
2. Uploads it to Feishu's media server
3. Sends the image as a native Feishu image message

## Usage

### Via Script
```bash
./scripts/send-dalle-image.sh "<image-url>" "<user-open-id>"
```

### Via Tool Call
The agent will automatically:
1. Detect DALL-E image generation results
2. Download the image
3. Send it to the user via Feishu

## Configuration
Requires:
- Feishu App ID and Secret (from openclaw.json)
- curl and jq installed
- Write access to /tmp directory

## Example Flow
1. User requests: "生成一张一马当先的图片"
2. Agent calls DALL-E API
3. Agent receives temporary URL
4. Agent downloads image locally
5. Agent uploads to Feishu
6. Agent sends image message to user