// =========================================================
// Bhū-Darpan Firebase Authentication Configuration
// Paste your Firebase Web App configuration from:
// Firebase Console -> Project Settings -> General -> Web Apps
// =========================================================

const firebaseConfig = {
  apiKey: "AIzaSyBQ97GOuY2O3SGYK3_7jmS2YbxSWGTFUpk",
  authDomain: "bhu-darpan.firebaseapp.com",
  projectId: "bhu-darpan",
  storageBucket: "bhu-darpan.firebasestorage.app",
  messagingSenderId: "610135649050",
  appId: "1:610135649050:web:ee4debdc582b1d4366daa3",
  measurementId: "G-82HEXXELM3"
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
