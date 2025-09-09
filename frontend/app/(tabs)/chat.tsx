// app/(tabs)/chat.tsx
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  SafeAreaView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";

type Role = "user" | "assistant" | "system";
type Message = { id: string; role: Role; text: string; pending?: boolean };

// const MOCK_MODE = process.env.EXPO_PUBLIC_MOCK !== "false"; // default true unless you set it to "false"
const MOCK_MODE = false; // For demo purposes, always true 

export default function ChatScreen() {
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [messages, setMessages] = useState<Message[]>(() => [
    {
      id: "welcome",
      role: "assistant",
      text: "Hi! I’m your assistant. Ask me anything ✨",
    },
  ]);

  const listRef = useRef<FlatList>(null);

  const canSend = useMemo(() => input.trim().length > 0 && !sending, [input, sending]);

  const scrollToEnd = useCallback(() => {
    requestAnimationFrame(() => listRef.current?.scrollToEnd({ animated: true }));
  }, []);

  useEffect(() => {
    scrollToEnd();
  }, [messages.length, scrollToEnd]);

  const fakeReply = (userText: string) =>
    new Promise<string>((resolve) => {
      // Very small “typing” delay for demo
      setTimeout(() => {
        resolve(`You said: “${userText}”. (Mock reply)`);
      }, 600);
    });

  const sendToBackend = async (userText: string) => {
    const token = await AsyncStorage.getItem("token");
    const res = await fetch("http://127.0.0.1:5000/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify([
        ...messages.map(({ role, text }) => ({ role: role, content: text })),
        { role: "user", content: userText },
      ]),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    // Expecting { reply: "..." }
    return (data.reply as string) ?? "…";
  };

  const onSend = useCallback(async () => {
    const text = input.trim();
    if (!text) return;

    setInput("");
    setSending(true);

    const userMsg: Message = { id: String(Date.now()), role: "user", text };
    const assistantPlaceholder: Message = {
      id: String(Date.now() + 1),
      role: "assistant",
      text: "Thinking…",
      pending: true,
    };

    setMessages((m) => [...m, userMsg, assistantPlaceholder]);

    try {
      const reply = MOCK_MODE ? await fakeReply(text) : await sendToBackend(text);

      // Replace placeholder with actual reply
      setMessages((m) =>
        m.map((msg) =>
          msg.id === assistantPlaceholder.id ? { ...msg, text: reply, pending: false } : msg
        )
      );
    } catch (e: any) {
      setMessages((m) =>
        m.map((msg) =>
          msg.id === assistantPlaceholder.id
            ? { ...msg, text: `Error: ${e.message}`, pending: false }
            : msg
        )
      );
    } finally {
      setSending(false);
    }
  }, [input, messages]);

  const renderItem = ({ item }: { item: Message }) => (
    <View style={[styles.row, item.role === "user" ? styles.rowEnd : styles.rowStart]}>
      <View
        style={[
          styles.bubble,
          item.role === "user" ? styles.userBubble : styles.assistantBubble,
          item.pending && styles.pending,
        ]}
      >
        <Text style={item.role === "user" ? styles.userText : styles.assistantText}>
          {item.text}
        </Text>
        {item.pending && (
          <View style={styles.inlineLoader}>
            <ActivityIndicator size="small" />
          </View>
        )}
      </View>
    </View>
  );

  return (
    <SafeAreaView style={styles.safe}>
      <KeyboardAvoidingView
        style={styles.container}
        behavior={Platform.select({ ios: "padding", android: undefined, default: undefined })}
        keyboardVerticalOffset={Platform.select({ ios: 64, default: 0 })}
      >
        <FlatList
          ref={listRef}
          data={messages}
          keyExtractor={(m) => m.id}
          renderItem={renderItem}
          contentContainerStyle={styles.listContent}
          onContentSizeChange={scrollToEnd}
          onLayout={scrollToEnd}
        />

        <View style={styles.inputBar}>
          <TextInput
            value={input}
            onChangeText={setInput}
            placeholder="Type a message…"
            placeholderTextColor="#999"
            multiline
            style={styles.input}
            onSubmitEditing={() => {
              if (canSend) onSend();
            }}
            blurOnSubmit={false}
          />
          <Pressable
            onPress={onSend}
            disabled={!canSend}
            style={[styles.sendBtn, !canSend && styles.sendBtnDisabled]}
          >
            <Text style={styles.sendText}>{sending ? "…" : "Send"}</Text>
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#0d0d0f" },
  container: { flex: 1 },
  listContent: { padding: 12, paddingBottom: 24, gap: 8 },
  row: { width: "100%", flexDirection: "row" },
  rowStart: { justifyContent: "flex-start" },
  rowEnd: { justifyContent: "flex-end" },
  bubble: {
    maxWidth: "85%",
    borderRadius: 18,
    paddingHorizontal: 14,
    paddingVertical: 10,
  },
  userBubble: { backgroundColor: "#3e82ff" },
  assistantBubble: { backgroundColor: "#1e1e22", borderWidth: 1, borderColor: "#2b2b31" },
  userText: { color: "white", fontSize: 16, lineHeight: 20 },
  assistantText: { color: "#e6e6eb", fontSize: 16, lineHeight: 20 },
  pending: { opacity: 0.8 },
  inlineLoader: { marginTop: 6 },
  inputBar: {
    flexDirection: "row",
    alignItems: "flex-end",
    paddingHorizontal: 12,
    paddingVertical: 10,
    gap: 8,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: "#2b2b31",
    backgroundColor: "#0f0f12",
  },
  input: {
    flex: 1,
    minHeight: 40,
    maxHeight: 140,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 12,
    backgroundColor: "#17171b",
    color: "white",
    fontSize: 16,
  },
  sendBtn: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 12,
    backgroundColor: "white",
  },
  sendBtnDisabled: { opacity: 0.5 },
  sendText: { fontWeight: "700" },
});
