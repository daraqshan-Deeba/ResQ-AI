/* Firebase Cloud Messaging service worker — config injected at runtime from the page. */
importScripts("https://www.gstatic.com/firebasejs/10.14.1/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/10.14.1/firebase-messaging-compat.js");

self.addEventListener("message", (event) => {
  if (event.data?.type !== "FIREBASE_CONFIG") return;
  if (self.__firebaseInitialized) return;

  firebase.initializeApp(event.data.config);
  const messaging = firebase.messaging();
  messaging.onBackgroundMessage((payload) => {
    const title = payload.notification?.title ?? "ResQ AI Alert";
    const options = {
      body: payload.notification?.body ?? "",
      icon: "/favicon.ico",
    };
    self.registration.showNotification(title, options);
  });
  self.__firebaseInitialized = true;
});
