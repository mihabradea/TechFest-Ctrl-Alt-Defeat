// app/(tabs)/chat.tsx
import * as Clipboard from "expo-clipboard";
import { Ionicons } from "@expo/vector-icons"; // Expo icons
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
import { Audio } from "expo-av";
import * as FileSystem from "expo-file-system";
import { Buffer } from "buffer";       // for ArrayBuffer -> base64


type Role = "user" | "assistant" | "system";
type Message = { id: string; role: Role; text: string; pending?: boolean };

const MOCK_MODE = process.env.EXPO_PUBLIC_MOCK !== "false"; // default true unless you set it to "false"

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

  const [copiedId, setCopiedId] = useState<string | null>(null);

  const copyToClipboard = async (id: string, text: string) => {
    await Clipboard.setStringAsync(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000); // revert after 2s
  };

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
      body: JSON.stringify({
        messages: [
          // You can send the full history if your backend expects it
          ...messages.map(({ role, text }) => ({ role, content: text })),
          { role: "user", content: userText },
        ],
      }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    // Expecting { reply: "..." }
    return (data.reply as string) ?? "…";
  };

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim()) return;

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
  }, [MOCK_MODE, fakeReply, sendToBackend]);


  // onSend now uses the input state
  const onSend = useCallback(async () => {
      const text = input.trim();
      if (!text) return;
      await sendMessage(text);
  }, [input, sendMessage]);

  // onSendWithText for handling custom text (e.g., from newline)
  const onSendWithText = useCallback(async (text: string) => {
    if (!text.trim()) return;
    setInput(""); // clear immediately so no newline remains
    await sendMessage(text);
  }, [sendMessage]);

  // handleChangeText for TextInput
  const handleChangeText = (t: string) => {
    if (t.endsWith("\n")) {
      const toSend = t.replace(/\n+$/, ""); // strip the just-typed newline(s)
      onSendWithText(toSend);
    } else {
      setInput(t);
    }
  };

  const [speakingId, setSpeakingId] = useState<string | null>(null);
  const soundRef = useRef<Audio.Sound | null>(null);
  const ttsCache = useRef<Record<string, string>>({}); // messageId -> local file uri

  useEffect(() => {
    Audio.setAudioModeAsync({ playsInSilentModeIOS: true });
  }, []);

  const stopSpeaking = useCallback(async () => {
  try {
    if (soundRef.current) {
      console.log("[TTS] Stopping playback");
      await soundRef.current.stopAsync();
      await soundRef.current.unloadAsync();
      soundRef.current = null;
    }
  } finally {
    setSpeakingId(null);
  }
}, []);

const playLocalFile = useCallback(async (fileUri: string) => {
  await stopSpeaking();
  const { sound } = await Audio.Sound.createAsync({ uri: fileUri }, { shouldPlay: true });
  soundRef.current = sound;
  sound.setOnPlaybackStatusUpdate((status) => {
    if (!status.isLoaded) return;
    if ((status as any).didJustFinish) {
      console.log("[TTS] Finished");
      stopSpeaking();
    }
  });
}, [stopSpeaking]);

// POST /tts, get MP3 bytes, save as local file, return local fileUri
// POST /tts, get MP3 bytes, save as local file, return local fileUri
const fetchTtsFile = useCallback(async (id: string, text: string) => {
  // cache hit?
  const cached = ttsCache.current[id];
  if (cached) return cached;

  const token = await AsyncStorage.getItem("token");
  console.log("[TTS] Fetching MP3 from backend…", { len: text.length });

  const res = await fetch("http://127.0.0.1:5000/tts", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      text,            // required by your endpoint
      filename: null,  // optional
      download: false, // "inline" disposition
    }),
  });

  if (!res.ok) throw new Error(`TTS HTTP ${res.status}`);

  const arrayBuffer = await res.arrayBuffer();
  const base64 = Buffer.from(arrayBuffer).toString("base64");

  const fileUri = `${FileSystem.cacheDirectory}tts-${id}.mp3`;
  await FileSystem.writeAsStringAsync(fileUri, base64, {
    encoding: FileSystem.EncodingType.Base64,
  });

  console.log("[TTS] Saved MP3 to cache:", fileUri);
  ttsCache.current[id] = fileUri;
  return fileUri;
}, []);


  const speakMessage = useCallback(async (id: string, text: string) => {
    try {
    // toggle stop if currently playing this one
    if (speakingId === id) {
      await stopSpeaking();
      return;
    }

    if (MOCK_MODE) {
      // Dev mode: don't speak, just log so you can see it's wired
      console.log("[TTS MOCK] button pressed", {
        id,
        preview: text.slice(0, 80),
        length: text.length,
      });
      return;
    }

    // Real mode: fetch + play
    const fileUri = await fetchTtsFile(id, text);
    setSpeakingId(id);
    await playLocalFile(fileUri);
    console.log("[TTS] Playing:", fileUri);
  } catch (e) {
    console.warn("TTS error:", e);
    setSpeakingId(null);
  }
}, [MOCK_MODE, speakingId, stopSpeaking, fetchTtsFile, playLocalFile]);


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

        {item.role === "assistant" && !item.pending && (
          <View style={styles.actions}>
            {/* Copy */}
            <Pressable onPress={() => copyToClipboard(item.id, item.text)} style={styles.iconBtn}>
              {copiedId === item.id ? (
                <Ionicons name="checkmark-outline" size={18} color="#4caf50" />
              ) : (
                <Ionicons name="copy-outline" size={18} color="#aaa" />
              )}
            </Pressable>

            {/* Speaker */}
            <Pressable onPress={() => speakMessage(item.id, item.text)} style={styles.iconBtn}>
              <Ionicons
                name={speakingId === item.id ? "stop-outline" : "volume-high-outline"}
                size={18}
                color={speakingId === item.id ? "#fff" : "#aaa"}
              />
            </Pressable>

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
         {/* Header */}
        <View style={styles.header}>
          <Text style={styles.headerTitle}>Ctrl + Alt + Defeat</Text>
        </View>
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
          onChangeText={handleChangeText}
          placeholder="Type a message…"
          placeholderTextColor="#999"
          multiline
          style={styles.input}
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
  header: {
  paddingVertical: 16,
  backgroundColor: "#0f0f12",
  alignItems: "center",
  borderBottomWidth: StyleSheet.hairlineWidth,
  borderBottomColor: "#2b2b31",
  },
  headerTitle: {
    color: "white",
    fontSize: 18,
    fontWeight: "700",
  },
  actions: {
    flexDirection: "row",
    marginTop: 6,
    justifyContent: "flex-end",
    gap: 12,
  },
  iconBtn: {
    padding: 4,
  },
  toast: {
    position: "absolute",
    top: 10,
    alignSelf: "center",
    backgroundColor: "rgba(0,0,0,0.8)",
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
    zIndex: 1000,
  },
  toastText: {
    color: "white",
    fontSize: 14,
  },

});
