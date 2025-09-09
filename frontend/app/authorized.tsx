// frontend/app/authorized.tsx
import React, { useEffect, useState } from "react";
import { View, Text, Pressable, ActivityIndicator, StyleSheet } from "react-native";
import * as SecureStore from "expo-secure-store";
import { useRouter } from "expo-router";
import AsyncStorage from '@react-native-async-storage/async-storage';

export default function AuthorizedScreen() {
  const [message, setMessage] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  useEffect(() => {
    (async () => {
      const token = await AsyncStorage.getItem("token");
      if (!token) {
        setMessage("❌ No token found. Please log in.");
        setLoading(false);
        setTimeout(() => router.replace("/login"), 1500);
        return;
      }
      try {
        const res = await fetch("http://127.0.0.1:5000/protected", {
          method: "GET",
          headers: { Authorization: "Bearer " + token },
        });
        const data = await res.json();
        setMessage(data.message || "Authorized");
      } catch (e: any) {
        setMessage("Error: " + e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const logout = async () => {
    await AsyncStorage.removeItem("token"); // on logout
    router.replace("/login");
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>✅ You are authorized!</Text>
      {loading ? <ActivityIndicator /> : <Text style={styles.status}>{message}</Text>}
      <Pressable style={styles.button} onPress={logout}>
        <Text style={styles.buttonText}>Log out</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#1e1e1e", alignItems: "center", justifyContent: "center", padding: 24 },
  title: { color: "green", fontSize: 20, marginBottom: 16 },
  status: { color: "cyan", marginVertical: 16, textAlign: "center" },
  button: { padding: 12, backgroundColor: "#fff", borderRadius: 6, marginTop: 12 },
  buttonText: { color: "#1e1e1e", fontWeight: "bold" },
});
