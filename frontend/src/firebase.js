import { initializeApp } from "firebase/app";
import { getAuth, connectAuthEmulator } from "firebase/auth";
import { getFirestore, connectFirestoreEmulator } from "firebase/firestore";

// These values are fine for local development with emulator.
// Replace with actual config for production deployment.
const firebaseConfig = {
  apiKey: "demo-key",
  authDomain: "demo-local.firebaseapp.com",
  projectId: "demo-local",
  storageBucket: "demo-local.appspot.com",
  messagingSenderId: "123456789",
  appId: "1:123456789:web:abcdef"
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);

// Connect to Emulators when in development mode
if (window.location.hostname === "localhost") {
  connectAuthEmulator(auth, "http://localhost:9099");
  connectFirestoreEmulator(db, "localhost", 8080);
}

export { auth, db };
