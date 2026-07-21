// This file MUST be served from the root of your site (same folder as
// index.html/dashboard.html), at exactly this filename — Firebase looks for
// it at that fixed path when registering for background push.

importScripts('https://www.gstatic.com/firebasejs/10.13.1/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.13.1/firebase-messaging-compat.js');
importScripts('./firebase-config.js');

firebase.initializeApp(firebaseConfig);
const messaging = firebase.messaging();

// Fires when a push arrives while no tab has focus (or the browser is
// closed, on platforms that support that).
messaging.onBackgroundMessage((payload) => {
  const title = (payload.notification && payload.notification.title) || 'ResQ AI Alert';
  const body = (payload.notification && payload.notification.body) || '';
  self.registration.showNotification(title, { body });
});
