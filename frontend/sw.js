/**
 * MedTracker Service Worker
 * =========================
 * Receives Web Push events from the server and displays native OS notifications.
 * Also handles notification action clicks (Mark Taken / Snooze).
 *
 * Served at /static/sw.js — must be at root scope to control the whole origin.
 * FastAPI mounts /static -> frontend/, so this file is accessible at /static/sw.js.
 */

const CACHE_NAME = 'medtracker-v1';

// ─── Install ─────────────────────────────────────────────────────────────────
self.addEventListener('install', (event) => {
    // Activate immediately without waiting for existing tabs to close
    self.skipWaiting();
});

// ─── Activate ────────────────────────────────────────────────────────────────
self.addEventListener('activate', (event) => {
    // Take control of any open tabs immediately
    event.waitUntil(clients.claim());
});

// ─── Push received ───────────────────────────────────────────────────────────
self.addEventListener('push', (event) => {
    if (!event.data) return;

    let data;
    try {
        data = event.data.json();
    } catch {
        data = { title: 'MedTracker', body: event.data.text() };
    }

    const options = {
        body: data.body || 'Time to take your medication',
        icon: data.icon || '/static/icon-192.png',
        badge: data.badge || '/static/icon-72.png',
        tag: data.tag || 'medtracker-dose',
        requireInteraction: true,   // Stays visible until the user interacts
        vibrate: [200, 100, 200],
        actions: [
            { action: 'taken', title: '✓ Mark Taken' },
            { action: 'snooze', title: '⏰ Snooze 1 hr' },
        ],
        data: {
            url: '/',
            tag: data.tag || 'medtracker-dose',
        },
    };

    event.waitUntil(
        self.registration.showNotification(data.title || 'MedTracker Reminder', options)
    );
});

// ─── Notification click ───────────────────────────────────────────────────────
self.addEventListener('notificationclick', (event) => {
    event.notification.close();

    const action = event.action;
    const notifData = event.notification.data || {};
    const tag = notifData.tag || '';

    // Extract medication_id from tag "medtracker-{id}"
    const medIdMatch = tag.match(/medtracker-(\d+)/);
    const medicationId = medIdMatch ? medIdMatch[1] : null;

    if (action === 'snooze' && medicationId) {
        // Open / focus the app and tell it to snooze this medication
        event.waitUntil(
            _focusOrOpenWindow('/?action=snooze&medication_id=' + medicationId)
        );
    } else {
        // Default click or "taken" — open the schedule view
        event.waitUntil(
            _focusOrOpenWindow('/')
                .then((windowClient) => {
                    if (windowClient) {
                        // Tell the open tab to switch to Schedule and optionally mark taken
                        windowClient.postMessage({
                            type: action === 'taken' ? 'MARK_TAKEN' : 'OPEN_SCHEDULE',
                            medicationId: medicationId ? parseInt(medicationId) : null,
                        });
                    }
                })
        );
    }
});

// ─── Helper ───────────────────────────────────────────────────────────────────
async function _focusOrOpenWindow(url) {
    const allClients = await clients.matchAll({
        type: 'window',
        includeUncontrolled: true,
    });

    // Focus an existing tab if one is open
    for (const client of allClients) {
        if (client.url.startsWith(self.location.origin)) {
            await client.focus();
            return client;
        }
    }

    // Otherwise open a new tab
    return clients.openWindow(url);
}
