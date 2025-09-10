// app/(tabs)/chat.tsx
import * as Clipboard from "expo-clipboard";
import { Ionicons } from "@expo/vector-icons";
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
  Animated,
  ScrollView,
} from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { Audio } from "expo-av";
import * as FileSystem from "expo-file-system";
import { Buffer } from "buffer";
import { LinearGradient } from 'expo-linear-gradient';

type Role = "user" | "assistant" | "system";
type Message = { id: string; role: Role; text: string; pending?: boolean };
type NotificationType = "payment" | "security" | "update" | "reminder";
type Notification = { 
  id: string; 
  type: NotificationType; 
  title: string; 
  message: string; 
  timestamp: string;
  isRead: boolean;
};

const MOCK_MODE = false;

// Hardcoded notifications data
const MOCK_NOTIFICATIONS: Notification[] = [
  {
    id: "1",
    type: "payment",
    title: "Payment Received",
    message: "You received $125.00 from John Smith for dinner split",
    timestamp: "2 min ago",
    isRead: false,
  },
  {
    id: "2",
    type: "security",
    title: "Security Alert",
    message: "New login detected from iPhone 14 Pro in New York",
    timestamp: "1 hour ago",
    isRead: false,
  },
  {
    id: "3",
    type: "payment",
    title: "Payment Sent",
    message: "Successfully sent $50.00 to Sarah Johnson",
    timestamp: "3 hours ago",
    isRead: true,
  },
  {
    id: "4",
    type: "update",
    title: "App Update Available",
    message: "Version 2.1.0 includes new security features and bug fixes",
    timestamp: "1 day ago",
    isRead: true,
  },
  {
    id: "5",
    type: "reminder",
    title: "Bill Reminder",
    message: "Your Netflix subscription payment is due tomorrow",
    timestamp: "2 days ago",
    isRead: true,
  },
];

// Notification Item Component
const NotificationItem = ({ 
  notification, 
  onPress 
}: {
  notification: Notification;
  onPress: (notification: Notification) => void;
}) => {
  const fadeAnim = useRef(new Animated.Value(0)).current;
  
  useEffect(() => {
    Animated.timing(fadeAnim, {
      toValue: 1,
      duration: 300,
      useNativeDriver: true,
    }).start();
  }, []);

  const getNotificationIcon = (type: NotificationType) => {
    switch (type) {
      case "payment":
        return "card-outline";
      case "security":
        return "shield-checkmark-outline";
      case "update":
        return "download-outline";
      case "reminder":
        return "time-outline";
      default:
        return "notifications-outline";
    }
  };

  const getNotificationColor = (type: NotificationType) => {
    switch (type) {
      case "payment":
        return "#00D4FF";
      case "security":
        return "#FF6B9D";
      case "update":
        return "#4ECDC4";
      case "reminder":
        return "#FFE66D";
      default:
        return "#FFFFFF";
    }
  };

  return (
    <Animated.View style={[styles.notificationItem, { opacity: fadeAnim }]}>
      <Pressable 
        onPress={() => onPress(notification)}
        style={[
          styles.notificationContent,
          !notification.isRead && styles.unreadNotification
        ]}
      >
        <View style={styles.notificationHeader}>
          <View 
            style={[
              styles.notificationIcon, 
              { backgroundColor: getNotificationColor(notification.type) + '20' }
            ]}
          >
            <Ionicons 
              name={getNotificationIcon(notification.type) as any} 
              size={18} 
              color={getNotificationColor(notification.type)} 
            />
          </View>
          <View style={styles.notificationTextContainer}>
            <View style={styles.notificationTitleRow}>
              <Text style={styles.notificationTitle} numberOfLines={1}>
                {notification.title}
              </Text>
              {!notification.isRead && <View style={styles.unreadDot} />}
            </View>
            <Text style={styles.notificationTimestamp}>
              {notification.timestamp}
            </Text>
          </View>
        </View>
        
        <Text style={styles.notificationMessage} numberOfLines={2}>
          {notification.message}
        </Text>
      </Pressable>
    </Animated.View>
  );
};

// Notifications Sidebar Component
const NotificationsSidebar = ({ 
  notifications, 
  onNotificationPress 
}: {
  notifications: Notification[];
  onNotificationPress: (notification: Notification) => void;
}) => {
  const unreadCount = notifications.filter(n => !n.isRead).length;

  return (
    <LinearGradient
      colors={['rgba(255, 255, 255, 0.08)', 'rgba(255, 255, 255, 0.04)']}
      style={styles.notificationsSidebar}
    >
      <View style={styles.notificationsHeader}>
        <View style={styles.notificationsHeaderContent}>
          <Text style={styles.notificationsTitle}>Notifications</Text>
          {unreadCount > 0 && (
            <View style={styles.unreadBadge}>
              <Text style={styles.unreadBadgeText}>{unreadCount}</Text>
            </View>
          )}
        </View>
        <Ionicons name="notifications-outline" size={20} color="rgba(255, 255, 255, 0.7)" />
      </View>
      
      <ScrollView 
        style={styles.notificationsList}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.notificationsContent}
      >
        {notifications.map((notification) => (
          <NotificationItem
            key={notification.id}
            notification={notification}
            onPress={onNotificationPress}
          />
        ))}
      </ScrollView>
    </LinearGradient>
  );
};

// Separate component for message items to properly use hooks
const MessageItem = ({ 
  item, 
  copiedId, 
  speakingId, 
  onCopy, 
  onSpeak,
  pulseAnim 
}: {
  item: Message;
  copiedId: string | null;
  speakingId: string | null;
  onCopy: (id: string, text: string) => void;
  onSpeak: (id: string, text: string) => void;
  pulseAnim: Animated.Value;
}) => {
  const fadeAnim = useRef(new Animated.Value(0)).current;
  const slideAnim = useRef(new Animated.Value(20)).current;
  const dotAnim1 = useRef(new Animated.Value(0.3)).current;
  const dotAnim2 = useRef(new Animated.Value(0.3)).current;
  const dotAnim3 = useRef(new Animated.Value(0.3)).current;

  useEffect(() => {
    // Entry animation
    Animated.parallel([
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 400,
        useNativeDriver: true,
      }),
      Animated.timing(slideAnim, {
        toValue: 0,
        duration: 400,
        useNativeDriver: true,
      }),
    ]).start();
  }, []);

  useEffect(() => {
    if (item.pending) {
      // Typing dots animation
      const createDotAnimation = (anim: Animated.Value, delay: number) => {
        return Animated.loop(
          Animated.sequence([
            Animated.timing(anim, {
              toValue: 1,
              duration: 600,
              useNativeDriver: true,
            }),
            Animated.timing(anim, {
              toValue: 0.3,
              duration: 600,
              useNativeDriver: true,
            }),
          ])
        );
      };

      const dot1 = createDotAnimation(dotAnim1, 0);
      const dot2 = createDotAnimation(dotAnim2, 200);
      const dot3 = createDotAnimation(dotAnim3, 400);

      setTimeout(() => dot1.start(), 0);
      setTimeout(() => dot2.start(), 200);
      setTimeout(() => dot3.start(), 400);

      return () => {
        dot1.stop();
        dot2.stop();
        dot3.stop();
      };
    }
  }, [item.pending]);

  return (
    <Animated.View
      style={[
        styles.row,
        item.role === "user" ? styles.rowEnd : styles.rowStart,
        {
          opacity: fadeAnim,
          transform: [{ translateY: slideAnim }],
        },
      ]}
    >
      {item.role === "assistant" && (
        <View style={styles.avatarContainer}>
          <Animated.View 
            style={[
              styles.botAvatar,
              { transform: [{ scale: pulseAnim }] }
            ]}
          >
            <Text style={styles.botAvatarText}>🤖</Text>
          </Animated.View>
        </View>
      )}
      
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
            <View style={styles.typingContainer}>
              <Animated.View style={[styles.typingDot, { opacity: dotAnim1 }]} />
              <Animated.View style={[styles.typingDot, { opacity: dotAnim2 }]} />
              <Animated.View style={[styles.typingDot, { opacity: dotAnim3 }]} />
            </View>
          </View>
        )}

        {item.role === "assistant" && !item.pending && (
          <View style={styles.actions}>
            <Pressable onPress={() => onCopy(item.id, item.text)} style={styles.iconBtn}>
              {copiedId === item.id ? (
                <Ionicons name="checkmark-outline" size={16} color="#00D4FF" />
              ) : (
                <Ionicons name="copy-outline" size={16} color="rgba(255, 255, 255, 0.6)" />
              )}
            </Pressable>

            <Pressable onPress={() => onSpeak(item.id, item.text)} style={styles.iconBtn}>
              <Ionicons
                name={speakingId === item.id ? "stop-outline" : "volume-high-outline"}
                size={16}
                color={speakingId === item.id ? "#00D4FF" : "rgba(255, 255, 255, 0.6)"}
              />
            </Pressable>
          </View>
        )}
      </View>
    </Animated.View>
  );
};

export default function ChatScreen() {
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [messages, setMessages] = useState<Message[]>(() => [
    {
      id: "welcome",
      role: "assistant",
      text: "Hi! I'm your PayPal AI assistant. I can help you with payments, transactions, and account management. How can I assist you today? ✨",
    },
  ]);

  const [notifications, setNotifications] = useState<Notification[]>(MOCK_NOTIFICATIONS);

  const listRef = useRef<FlatList>(null);
  const canSend = useMemo(() => input.trim().length > 0 && !sending, [input, sending]);
  const scrollToEnd = useCallback(() => {
    requestAnimationFrame(() => listRef.current?.scrollToEnd({ animated: true }));
  }, []);

  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [speakingId, setSpeakingId] = useState<string | null>(null);
  const soundRef = useRef<Audio.Sound | null>(null);
  const ttsCache = useRef<Record<string, string>>({});

  // Animation refs for floating elements
  const floatAnim1 = useRef(new Animated.Value(0)).current;
  const floatAnim2 = useRef(new Animated.Value(0)).current;
  const pulseAnim = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    // Subtle floating animations for background elements
    const floatAnimation1 = Animated.loop(
      Animated.sequence([
        Animated.timing(floatAnim1, {
          toValue: -8,
          duration: 3000,
          useNativeDriver: true,
        }),
        Animated.timing(floatAnim1, {
          toValue: 8,
          duration: 3000,
          useNativeDriver: true,
        }),
      ])
    );
    
    const floatAnimation2 = Animated.loop(
      Animated.sequence([
        Animated.timing(floatAnim2, {
          toValue: 6,
          duration: 2500,
          useNativeDriver: true,
        }),
        Animated.timing(floatAnim2, {
          toValue: -6,
          duration: 2500,
          useNativeDriver: true,
        }),
      ])
    );

    const pulseAnimation = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, {
          toValue: 1.05,
          duration: 2000,
          useNativeDriver: true,
        }),
        Animated.timing(pulseAnim, {
          toValue: 1,
          duration: 2000,
          useNativeDriver: true,
        }),
      ])
    );

    floatAnimation1.start();
    floatAnimation2.start();
    pulseAnimation.start();

    Audio.setAudioModeAsync({ playsInSilentModeIOS: true });

    return () => {
      floatAnimation1.stop();
      floatAnimation2.stop();
      pulseAnimation.stop();
    };
  }, []);

  const copyToClipboard = async (id: string, text: string) => {
    await Clipboard.setStringAsync(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleNotificationPress = (notification: Notification) => {
    // Mark notification as read
    setNotifications(prev => 
      prev.map(n => 
        n.id === notification.id ? { ...n, isRead: true } : n
      )
    );
    
    // You can add additional logic here, like navigating to a specific screen
    console.log('Notification pressed:', notification);
  };

  useEffect(() => {
    scrollToEnd();
  }, [messages.length, scrollToEnd]);

  const fakeReply = (userText: string) =>
    new Promise<string>((resolve) => {
      setTimeout(() => {
        resolve(`You said: "${userText}". (Mock reply)`);
      }, 600);
    });

  const sendToBackend = async (userText: string) => {
    const token = await AsyncStorage.getItem("token");
    const res = await fetch("http://127.0.0.1:8000/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        messages: [
          ...messages.map(({ role, text }) => ({ role, content: text })),
          { role: "user", content: userText },
        ],
      }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
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
  }, [messages]);

  const onSend = useCallback(async () => {
    const text = input.trim();
    if (!text) return;
    await sendMessage(text);
  }, [input, sendMessage]);

  const onSendWithText = useCallback(async (text: string) => {
    if (!text.trim()) return;
    setInput("");
    await sendMessage(text);
  }, [sendMessage]);

  const handleChangeText = (t: string) => {
    if (t.endsWith("\n")) {
      const toSend = t.replace(/\n+$/, "");
      onSendWithText(toSend);
    } else {
      setInput(t);
    }
  };

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

  const fetchTtsFile = useCallback(async (id: string, text: string) => {
    const cached = ttsCache.current[id];
    if (cached) return cached;

    const token = await AsyncStorage.getItem("token");
    console.log("[TTS] Fetching MP3 from backend…", { len: text.length });

    const res = await fetch("http://127.0.0.1:8000/tts", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        text,
        filename: null,
        download: false,
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
      if (speakingId === id) {
        await stopSpeaking();
        return;
      }

      if (MOCK_MODE) {
        console.log("[TTS MOCK] button pressed", {
          id,
          preview: text.slice(0, 80),
          length: text.length,
        });
        return;
      }

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
    <MessageItem 
      item={item}
      copiedId={copiedId}
      speakingId={speakingId}
      onCopy={copyToClipboard}
      onSpeak={speakMessage}
      pulseAnim={pulseAnim}
    />
  );

  return (
    <LinearGradient
      colors={['#0A0A2E', '#16213E', '#0E4B99']}
      style={styles.gradient}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
    >
      <SafeAreaView style={styles.safe}>
        {/* Background decorative elements */}
        <View style={styles.backgroundElements}>
          <Animated.View 
            style={[
              styles.floatingCircle, 
              styles.circle1,
              { transform: [{ translateY: floatAnim1 }] }
            ]} 
          />
          <Animated.View 
            style={[
              styles.floatingCircle, 
              styles.circle2,
              { transform: [{ translateY: floatAnim2 }] }
            ]} 
          />
        </View>

        <View style={styles.mainContainer}>
          {/* Chat Section */}
          <KeyboardAvoidingView
            style={styles.chatContainer}
            behavior={Platform.select({ ios: "padding", android: undefined, default: undefined })}
            keyboardVerticalOffset={Platform.select({ ios: 64, default: 0 })}
          >
            {/* Header */}
            <LinearGradient
              colors={['rgba(255, 255, 255, 0.1)', 'rgba(255, 255, 255, 0.05)']}
              style={styles.header}
            >
              <View style={styles.headerContent}>
                <View style={styles.headerIcon}>
                  <Text style={styles.headerEmoji}>🤖</Text>
                </View>
                <View style={styles.headerTextContainer}>
                  <Text style={styles.headerTitle}>PayPal AI Assistant</Text>
                  <Text style={styles.headerSubtitle}>Online • Ready to help</Text>
                </View>
              </View>
            </LinearGradient>

            <FlatList
              ref={listRef}
              data={messages}
              keyExtractor={(m) => m.id}
              renderItem={renderItem}
              contentContainerStyle={styles.listContent}
              onContentSizeChange={scrollToEnd}
              onLayout={scrollToEnd}
              showsVerticalScrollIndicator={false}
            />

            <LinearGradient
              colors={['rgba(255, 255, 255, 0.08)', 'rgba(255, 255, 255, 0.04)']}
              style={styles.inputBar}
            >
              <View style={styles.inputContainer}>
                <TextInput
                  value={input}
                  onChangeText={handleChangeText}
                  placeholder="Ask me about payments, transfers, or account help..."
                  placeholderTextColor="rgba(255, 255, 255, 0.5)"
                  multiline
                  style={styles.input}
                  blurOnSubmit={false}
                />
                
                <Pressable
                  onPress={onSend}
                  disabled={!canSend}
                  style={[styles.sendBtn, !canSend && styles.sendBtnDisabled]}
                >
                  {sending ? (
                    <ActivityIndicator size="small" color="#0A0A2E" />
                  ) : (
                    <Ionicons name="send" size={20} color="#0A0A2E" />
                  )}
                </Pressable>
              </View>
            </LinearGradient>
          </KeyboardAvoidingView>

          {/* Notifications Sidebar */}
          <NotificationsSidebar 
            notifications={notifications}
            onNotificationPress={handleNotificationPress}
          />
        </View>
      </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  gradient: {
    flex: 1,
  },
  safe: { 
    flex: 1,
  },
  backgroundElements: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    overflow: 'hidden',
  },
  floatingCircle: {
    position: 'absolute',
    borderRadius: 100,
    opacity: 0.03,
  },
  circle1: {
    width: 80,
    height: 80,
    backgroundColor: '#00D4FF',
    top: '20%',
    left: '80%',
  },
  circle2: {
    width: 60,
    height: 60,
    backgroundColor: '#FF6B9D',
    bottom: '30%',
    left: '10%',
  },
  mainContainer: {
    flex: 1,
    flexDirection: 'row',
  },
  chatContainer: { 
    flex: 3,
  },
  header: {
    paddingVertical: 16,
    paddingHorizontal: 20,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: 'rgba(255, 255, 255, 0.1)',
  },
  headerContent: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  headerIcon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.2)',
  },
  headerEmoji: {
    fontSize: 22,
  },
  headerTextContainer: {
    flex: 1,
  },
  headerTitle: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '600',
    letterSpacing: -0.3,
  },
  headerSubtitle: {
    color: 'rgba(255, 255, 255, 0.7)',
    fontSize: 13,
    marginTop: 2,
  },
  listContent: { 
    padding: 16, 
    paddingBottom: 24, 
    gap: 12,
  },
  row: { 
    width: "100%", 
    flexDirection: "row",
    alignItems: 'flex-end',
  },
  rowStart: { 
    justifyContent: "flex-start",
  },
  rowEnd: { 
    justifyContent: "flex-end",
  },
  avatarContainer: {
    marginRight: 8,
    marginBottom: 4,
  },
  botAvatar: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.2)',
  },
  botAvatarText: {
    fontSize: 16,
  },
  bubble: {
    maxWidth: "80%",
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  userBubble: { 
    backgroundColor: '#00D4FF',
    borderBottomRightRadius: 6,
  },
  assistantBubble: { 
    backgroundColor: 'rgba(255, 255, 255, 0.08)',
    borderWidth: 1, 
    borderColor: 'rgba(255, 255, 255, 0.15)',
    borderBottomLeftRadius: 6,
  },
  userText: { 
    color: "#0A0A2E", 
    fontSize: 16, 
    lineHeight: 22,
    fontWeight: '500',
  },
  assistantText: { 
    color: '#FFFFFF', 
    fontSize: 16, 
    lineHeight: 22,
  },
  pending: { 
    opacity: 0.8,
  },
  inlineLoader: { 
    marginTop: 8,
    alignItems: 'flex-start',
  },
  typingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  typingDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: 'rgba(255, 255, 255, 0.6)',
  },
  inputBar: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: 'rgba(255, 255, 255, 0.1)',
  },
  inputContainer: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 12,
  },
  input: {
    flex: 1,
    minHeight: 44,
    maxHeight: 120,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 22,
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.2)',
    color: '#FFFFFF',
    fontSize: 16,
    lineHeight: 20,
  },
  sendBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#00D4FF',
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#00D4FF',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3,
    shadowRadius: 4,
    elevation: 4,
  },
  sendBtnDisabled: { 
    opacity: 0.5,
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
  },
  actions: {
    flexDirection: "row",
    marginTop: 8,
    justifyContent: "flex-end",
    gap: 16,
  },
  iconBtn: {
    padding: 6,
    borderRadius: 12,
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
  },
  
  // Notifications Sidebar Styles
  notificationsSidebar: {
    flex: 1,
    borderLeftWidth: StyleSheet.hairlineWidth,
    borderLeftColor: 'rgba(255, 255, 255, 0.1)',
    paddingVertical: 16,
  },
  notificationsHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingBottom: 16,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: 'rgba(255, 255, 255, 0.1)',
  },
  notificationsHeaderContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  notificationsTitle: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '600',
    letterSpacing: -0.3,
  },
  unreadBadge: {
    backgroundColor: '#FF6B9D',
    borderRadius: 10,
    paddingHorizontal: 6,
    paddingVertical: 2,
    minWidth: 20,
    alignItems: 'center',
  },
  unreadBadgeText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '600',
  },
  notificationsList: {
    flex: 1,
    paddingTop: 8,
  },
  notificationsContent: {
    paddingHorizontal: 12,
    paddingBottom: 20,
  },
  notificationItem: {
    marginBottom: 8,
  },
  notificationContent: {
    backgroundColor: 'rgba(255, 255, 255, 0.06)',
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
  },
  unreadNotification: {
    backgroundColor: 'rgba(255, 255, 255, 0.08)',
    borderColor: 'rgba(0, 212, 255, 0.3)',
  },
  notificationHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  notificationIcon: {
    width: 32,
    height: 32,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 10,
  },
  notificationTextContainer: {
    flex: 1,
  },
  notificationTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 2,
  },
  notificationTitle: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
    flex: 1,
  },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#00D4FF',
    marginLeft: 4,
  },
  notificationTimestamp: {
    color: 'rgba(255, 255, 255, 0.6)',
    fontSize: 11,
    fontWeight: '400',
  },
  notificationMessage: {
    color: 'rgba(255, 255, 255, 0.8)',
    fontSize: 13,
    lineHeight: 18,
  },
});