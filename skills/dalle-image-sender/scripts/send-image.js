#!/usr/bin/env node

/**
 * DALL-E Image Sender for OpenClaw
 * Downloads Azure DALL-E images and sends via Feishu
 */

const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');

// Configuration from environment or defaults
const FEISHU_CONFIG = {
  appId: process.env.FEISHU_APP_ID || 'cli_a92827b565b89cc8',
  appSecret: process.env.FEISHU_APP_SECRET || 'kouffcksP3rFXqDqqg15RfGtqTnZkcUr',
  baseUrl: 'https://open.feishu.cn'
};

async function getTenantAccessToken() {
  const response = await fetch(`${FEISHU_CONFIG.baseUrl}/open-apis/auth/v3/tenant_access_token/internal`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      app_id: FEISHU_CONFIG.appId,
      app_secret: FEISHU_CONFIG.appSecret
    })
  });
  
  const data = await response.json();
  if (!data.tenant_access_token) {
    throw new Error(`Failed to get tenant token: ${JSON.stringify(data)}`);
  }
  return data.tenant_access_token;
}

async function downloadImage(url) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https') ? https : http;
    const tempFile = path.join('/tmp', `dalle_${Date.now()}.png`);
    
    const file = fs.createWriteStream(tempFile);
    client.get(url, (response) => {
      if (response.statusCode !== 200) {
        reject(new Error(`Download failed: ${response.statusCode}`));
        return;
      }
      response.pipe(file);
      file.on('finish', () => {
        file.close();
        resolve(tempFile);
      });
    }).on('error', (err) => {
      fs.unlink(tempFile, () => {});
      reject(err);
    });
  });
}

async function uploadToFeishu(imagePath, token) {
  const formData = new FormData();
  const fileContent = fs.readFileSync(imagePath);
  
  const blob = new Blob([fileContent], { type: 'image/png' });
  formData.append('image_type', 'message');
  formData.append('image', blob, 'image.png');
  
  const response = await fetch(`${FEISHU_CONFIG.baseUrl}/open-apis/im/v1/images`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    },
    body: formData
  });
  
  const data = await response.json();
  if (!data.data || !data.data.image_key) {
    throw new Error(`Upload failed: ${JSON.stringify(data)}`);
  }
  return data.data.image_key;
}

async function sendImageMessage(userOpenId, imageKey, token) {
  const response = await fetch(`${FEISHU_CONFIG.baseUrl}/open-apis/im/v1/messages?receive_id_type=open_id`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      receive_id: userOpenId,
      msg_type: 'image',
      content: JSON.stringify({ image_key: imageKey })
    })
  });
  
  const data = await response.json();
  return data;
}

async function main() {
  const args = process.argv.slice(2);
  const imageUrl = args[0];
  const userOpenId = args[1];
  
  if (!imageUrl || !userOpenId) {
    console.error('Usage: node send-dalle-image.js <image-url> <user-open-id>');
    process.exit(1);
  }
  
  try {
    console.log('Step 1: Downloading image from Azure DALL-E...');
    const tempFile = await downloadImage(imageUrl);
    console.log(`✓ Downloaded to: ${tempFile}`);
    
    console.log('Step 2: Getting Feishu access token...');
    const token = await getTenantAccessToken();
    console.log('✓ Got access token');
    
    console.log('Step 3: Uploading to Feishu...');
    const imageKey = await uploadToFeishu(tempFile, token);
    console.log(`✓ Uploaded with key: ${imageKey}`);
    
    console.log('Step 4: Sending image message...');
    const result = await sendImageMessage(userOpenId, imageKey, token);
    console.log('✓ Message sent successfully');
    
    // Cleanup
    fs.unlinkSync(tempFile);
    console.log('✓ Cleaned up temp file');
    
    console.log('\nDone! Image sent to user.');
    console.log(JSON.stringify(result, null, 2));
    
  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = { downloadImage, uploadToFeishu, sendImageMessage };
