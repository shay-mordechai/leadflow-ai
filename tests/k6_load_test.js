import http from 'k6/http';
import { check, sleep } from 'k6';
import crypto from 'k6/crypto';

export const options = {
    stages: [
        { duration: '30s', target: 50 },  // Ramp up to 50 concurrent virtual users
        { duration: '1m', target: 200 },  // Spike to 200 concurrent (Stress Phase)
        { duration: '30s', target: 0 },   // Cool down
    ],
};

// Replace this with the actual secret from your .env for local testing
const SECRET = 'YOUR_WHATSAPP_APP_SECRET'; 

export default function () {
    const url = 'http://localhost:8000/webhooks/whatsapp';
    
    // Simulating an incoming WhatsApp message from Meta
    const payload = JSON.stringify({
        object: 'whatsapp_business_account',
        entry: [{ 
            changes: [{ 
                value: { 
                    messages: [{ 
                        id: `wamid.${Math.random().toString(36).substring(7)}`, 
                        from: "972501234567", 
                        type: "text", 
                        text: { body: "Load Test Message" } 
                    }] 
                } 
            }] 
        }]
    });

    // Generate valid HMAC signature to pass security middleware
    const signature = crypto.hmac('sha256', SECRET, payload, 'hex');

    const params = {
        headers: {
            'Content-Type': 'application/json',
            'X-Hub-Signature-256': `sha256=${signature}`,
        },
    };

    const res = http.post(url, payload, params);

    check(res, {
        'is status 200': (r) => r.status === 200,
        'is not 429 (Rate Limited)': (r) => r.status !== 429,
        'is not 500 (Server Error)': (r) => r.status !== 500,
    });

    sleep(0.1);
}