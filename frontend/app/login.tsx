// frontend/app/login.tsx
import React, { useState } from "react";
import { View, Text, TextInput, Pressable, ActivityIndicator, StyleSheet, Alert } from "react-native";
import * as SecureStore from "expo-secure-store";
import { useRouter } from "expo-router";
import AsyncStorage from '@react-native-async-storage/async-storage';
import PayPalLoginButton from "@/components/LoginButton";


/**
 * Opens PayPal’s authorize URL.

After login, PayPal redirects to your REDIRECT_URI with ?code=...&state=....

The component catches that and calls your onSuccess({ code, state }).

Your screen must send code to your backend to exchange for tokens/session.

Backend responds with your app token → you save it and navigate.
 */
export default function LoginScreen() {
  const router = useRouter();
  const [msg, setMsg] = useState("");

  return (
    <View style={styles.container}>
      <Text style={styles.title}>🔒 Login</Text>

      <PayPalLoginButton
        // onSuccess={async ({ code, state }) => {
        //   try {
        //     setMsg("");
        //     // Exchange on YOUR backend, get your app session/JWT back
        //     const res = await fetch("http://127.0.0.1:5000/api/paypal/exchange", {
        //       method: "POST",
        //       headers: { "Content-Type": "application/json" },
        //       body: JSON.stringify({ code, state }),
        //     });
        //     if (!res.ok) throw new Error((await res.text()) || "Exchange failed");
        //     const data = await res.json();
        //     await AsyncStorage.setItem("token", data.token); // keep AsyncStorage for consistency with index.tsx
        //     router.replace("/");
        //   } catch (e: any) {
        //     const m = e?.message || "Login failed";
        //     setMsg(m);
        //     Alert.alert("Login failed", m);
        //   }
        // }}
        onSuccess={async ({ code, state }) => {
          // 1) Verify we actually got here:
          console.log('PayPal onSuccess code=', code, 'state=', state);

          // 2) TEMP: pretend we exchanged the code successfully.
          //    DO NOT use this in prod.
          await AsyncStorage.setItem('token', `DEV_TOKEN_${Date.now()}`);

          // 3) Navigate into the app so you can continue building screens.
          router.replace('/');
        }}
        onCancel={() => setMsg("Login cancelled")}
        onError={(err) => {
          const m = err instanceof Error ? err.message : String(err);
          setMsg(m);
          Alert.alert("PayPal error", m);
        }}
      />

      {!!msg && <Text style={styles.response}>{msg}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#1e1e1e", alignItems: "center", justifyContent: "center", padding: 24, width: "100%" },
  title: { color: "#f1f1f1", fontSize: 22, marginBottom: 24 },
  response: { color: "#ff6b6b", marginTop: 12, textAlign: "center" },
});
