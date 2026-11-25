// =========================================================
// Bhū-Darpan Firebase Authentication Configuration
// Paste your Firebase Web App configuration from:
// Firebase Console -> Project Settings -> General -> Web Apps
// =========================================================

const firebaseConfig = {
  apiKey: "AIzaSy_YOUR_API_KEY_HERE",
  authDomain: "bhu-darpan.firebaseapp.com",
  projectId: "bhu-darpan",
  storageBucket: "bhu-darpan.appspot.com",
  messagingSenderId: "123456789012",
  appId: "1:123456789012:web:abcdef1234567890"
};

/**
 * Initialize Firebase app and return auth instance.
 */
function getFirebaseAuth() {
  if (typeof firebase === "undefined") {
    throw new Error("Firebase SDK is not loaded. Please check your internet connection.");
  }
  if (!firebase.apps || !firebase.apps.length) {
    firebase.initializeApp(firebaseConfig);
  }
  return firebase.auth();
}

/**
 * Launch Google Sign-In popup via Firebase.
 */
async function signInWithGoogleFirebase() {
  const auth = getFirebaseAuth();
  const provider = new firebase.auth.GoogleAuthProvider();
  provider.addScope("email");
  provider.addScope("profile");
  provider.setCustomParameters({ prompt: "select_account" });

  const result = await auth.signInWithPopup(provider);
  const user = result.user;
  const idToken = await user.getIdToken();

  return {
    user: user,
    idToken: idToken,
    email: user.email,
    name: user.displayName || (user.email ? user.email.split("@")[0] : "Google User"),
    photo_url: user.photoURL || ""
  };
}
