// Service Worker — Push notifications for Insta Post Auto

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  let data = { title: "Magic Post", body: "Nouveau rappel", url: "/" };
  try {
    data = event.data.json();
  } catch {}

  event.waitUntil(
    self.registration.showNotification(data.title || "Magic Post", {
      body: data.body || "",
      icon: "/static/icon-192.png",
      badge: "/static/icon-192.png",
      data: { url: data.url || "/" },
      vibrate: [200, 100, 200],
      tag: data.tag || "default",
      renotify: true,
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = event.notification.data?.url || "/";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if (client.url.includes(self.location.origin) && "focus" in client) {
          return client.focus();
        }
      }
      return self.clients.openWindow(url);
    })
  );
});
