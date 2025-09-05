// frontend/app/login.tsx
import React, { useState } from "react";
import { View, Text, TextInput, Pressable, ActivityIndicator, StyleSheet } from "react-native";
import * as SecureStore from "expo-secure-store";
import { useRouter } from "expo-router";
import AsyncStorage from '@react-native-async-storage/async-storage';

export default function LoginScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const login = async () => {
    setLoading(true);
    setMsg("");
    try {
      const res = await fetch("http://127.0.0.1:5000/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (data.status === "success" && data.token) {
        await AsyncStorage.setItem("token", data.token);
        router.replace("/");
      } else {
        setMsg(data.message || "Unauthorized");
      }
    } catch (e: any) {
      setMsg("Connection error: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>🔒 Login</Text>
      <TextInput
        style={styles.input}
        placeholder="Email"
        placeholderTextColor="#aaa"
        autoCapitalize="none"
        keyboardType="email-address"
        value={email}
        onChangeText={setEmail}
      />
      <TextInput
        style={styles.input}
        placeholder="Password"
        placeholderTextColor="#aaa"
        secureTextEntry
        value={password}
        onChangeText={setPassword}
      />
      <Pressable style={styles.button} onPress={login} disabled={loading}>
        {loading ? <ActivityIndicator /> : <Text style={styles.buttonText}>Login</Text>}
      </Pressable>

      {msg ? <Text style={styles.response}>{msg}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#1e1e1e", alignItems: "center", justifyContent: "center", padding: 24 },
  title: { color: "#f1f1f1", fontSize: 22, marginBottom: 24 },
  input: {
    width: "100%", padding: 12, marginBottom: 16, borderWidth: 2, borderColor: "#444",
    borderRadius: 6, backgroundColor: "#3a3a3a", color: "#fff", fontSize: 15,
  },
  button: {
    width: "100%", padding: 12, backgroundColor: "#fff", borderRadius: 6, alignItems: "center",
  },
  buttonText: { color: "#1e1e1e", fontWeight: "bold", fontSize: 16 },
  response: { color: "#ff6b6b", marginTop: 12 },
});
