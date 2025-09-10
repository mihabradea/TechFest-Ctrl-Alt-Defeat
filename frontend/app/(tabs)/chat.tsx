// app/(tabs)/chat.tsx
import * as Clipboard from "expo-clipboard";
import { Ionicons } from "@expo/vector-icons";
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
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
import { useRouter } from "expo-router"; 
import { URIS } from '@/constants/constants';
import { getToken } from "@/constants/token_prop";
import { Linking } from "react-native";

type Role = "user" | "assistant" | "system";
type Message = { id: string; role: Role; text: string; pending?: boolean };
type NotificationType = "payment" | "security" | "update" | "reminder" | "unpaid-invoice" | "recurring-payment";

// Updated notification type to include more fields for backend data
type Notification = {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  timestamp: string;
  isRead: boolean;
  amount?: number;
  currency?: string;
  dueDate?: string;
  customerName?: string;
  recurringDate?: string;
  link?: string;          // <--- add this
};

// Types for backend responses
type UnpaidInvoice = {
  invoice_id: string;
  customer_name: string;
  amount: number;
  currency: string;
  due_date: string;
  days_overdue: number;
};

type RecurringPayment = {
  payment_id: string;
  customer_name: string;
  amount: number;
  currency: string;
  next_payment_date: string;
  frequency: string;
};

type PaypalInvoiceAPI = {
  count: number;
  items: Array<{
    id: string;
    number: string;
    status: string; // e.g. "SENT"
    description?: string | null;
    amount_value?: number | null;
    amount_currency?: string | null;
    recipient: { name?: string | null; email: string };
    pay_url: string;
  }>;
};

const MOCK_MODE = false;

const convertPaypalInvoicesToNotifications = (api: PaypalInvoiceAPI): Notification[] => {
  const items = Array.isArray(api?.items) ? api.items : [];
  return items.map((inv) => ({
    id: `unpaid-${inv.id}`,
    type: "unpaid-invoice",
    title: `Invoice #${inv.number} • ${inv.status}`,
    message: `Invoice to ${inv.recipient.name || inv.recipient.email}`,
    timestamp: "Today",
    isRead: false,
    amount: inv.amount_value ?? undefined,
    currency: inv.amount_currency ?? undefined,
    customerName: inv.recipient.name || inv.recipient.email,
    link: inv.pay_url,
  }));
};

//for tts
// track last blob: url so we can revoke it on web
const currentObjectUrlRef = useRef<string | null>(null);
const webBlobUrls = useRef<Set<string>>(new Set()); // track for cleanup on unmount

// Helper function to format currency
const formatCurrency = (amount: number, currency: string = 'USD'): string => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: currency,
  }).format(amount);
};

// Helper function to format relative time
const getRelativeTime = (dateString: string): string => {
  const date = new Date(dateString);
  const now = new Date();
  const diffTime = Math.abs(now.getTime() - date.getTime());
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  
  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return '1 day ago';
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
  return `${Math.floor(diffDays / 30)} months ago`;
};

// Helper function to convert backend data to notifications
const convertUnpaidInvoicesToNotifications = (invoices: UnpaidInvoice[]): Notification[] => {
  return invoices.map(invoice => ({
    id: `unpaid-${invoice.invoice_id}`,
    type: "unpaid-invoice" as NotificationType,
    title: "Unpaid Invoice",
    message: `Invoice from ${invoice.customer_name} is ${invoice.days_overdue} days overdue`,
    timestamp: getRelativeTime(invoice.due_date),
    isRead: false,
    amount: invoice.amount,
    currency: invoice.currency,
    dueDate: invoice.due_date,
    customerName: invoice.customer_name,
  }));
};

const convertRecurringPaymentsToNotifications = (payments: RecurringPayment[]): Notification[] => {
  return payments.map(payment => ({
    id: `recurring-${payment.payment_id}`,
    type: "recurring-payment" as NotificationType,
    title: "Recurring Payment Due",
    message: `${payment.frequency} payment to ${payment.customer_name} due today`,
    timestamp: "Today",
    isRead: false,
    amount: payment.amount,
    currency: payment.currency,
    recurringDate: payment.next_payment_date,
    customerName: payment.customer_name,
  }));
};

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
      case "unpaid-invoice":
        return "alert-circle-outline";
      case "recurring-payment":
        return "refresh-circle-outline";
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
      case "unpaid-invoice":
        return "#FF4757";
      case "recurring-payment":
        return "#7B68EE";
      default:
        return "#FFFFFF";
    }
  };

  // Enhanced message with amount formatting
  const getEnhancedMessage = (notification: Notification): string => {
    if (notification.amount && notification.currency) {
      const formattedAmount = formatCurrency(notification.amount, notification.currency);
      if (notification.type === "unpaid-invoice") {
        return `${formattedAmount} invoice from ${notification.customerName} is overdue`;
      }
      if (notification.type === "recurring-payment") {
        return `${formattedAmount} recurring payment to ${notification.customerName} due today`;
      }
    }
    return notification.message;
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
          {getEnhancedMessage(notification)}
        </Text>

        {notification.type === "unpaid-invoice" && !!notification.link && (
          <Pressable
            onPress={(e) => {
              // prevent triggering the card’s onPress
              e?.stopPropagation?.();
              Linking.openURL(notification.link!);
            }}
            style={styles.linkRow}
            accessibilityRole="link"
            accessibilityLabel="Open invoice"
            hitSlop={8}
          >
            <Ionicons name="open-outline" size={16} color="#00D4FF" />
            <Text style={styles.linkText} numberOfLines={1}>
              {displayUrl(notification.link!)}
            </Text>
          </Pressable>
        )}

      </Pressable>
    </Animated.View>
  );
};

// Notifications Sidebar Component
const NotificationsSidebar = ({ 
  notifications, 
  onNotificationPress,
  isLoading = false,
  onRefresh
}: {
  notifications: Notification[];
  onNotificationPress: (notification: Notification) => void;
  isLoading?: boolean;
  onRefresh?: () => void;
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
        <View style={styles.notificationHeaderActions}>
          {onRefresh && (
            <Pressable onPress={onRefresh} style={styles.refreshBtn}>
              {isLoading ? (
                <ActivityIndicator size="small" color="rgba(255, 255, 255, 0.7)" />
              ) : (
                <Ionicons name="refresh-outline" size={18} color="rgba(255, 255, 255, 0.7)" />
              )}
            </Pressable>
          )}
          <Ionicons name="notifications-outline" size={20} color="rgba(255, 255, 255, 0.7)" />
        </View>
      </View>
      
      <ScrollView 
        style={styles.notificationsList}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={styles.notificationsContent}
      >
        {notifications.length === 0 && !isLoading ? (
          <View style={styles.emptyNotifications}>
            <Ionicons name="notifications-off-outline" size={48} color="rgba(255, 255, 255, 0.3)" />
            <Text style={styles.emptyNotificationsText}>No notifications</Text>
            <Text style={styles.emptyNotificationsSubtext}>You're all caught up!</Text>
          </View>
        ) : (
          notifications.map((notification) => (
            <NotificationItem
              key={notification.id}
              notification={notification}
              onPress={onNotificationPress}
            />
          ))
        )}
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

const addMockRecurringNotifications = (): Notification[] => {
  const now = new Date();

  const lastMonth = new Date(now);
  lastMonth.setMonth(lastMonth.getMonth() - 1);

  const twoMonthsAgo = new Date(now);
  twoMonthsAgo.setMonth(twoMonthsAgo.getMonth() - 2);

  const toISO = (d: Date) => d.toISOString();

  return [
    {
      id: `recurring-mock-${lastMonth.getFullYear()}-${lastMonth.getMonth() + 1}`,
      type: "recurring-payment",
      title: "Recurring Payment",
      message: "Recurring payment from last month",
      timestamp: getRelativeTime(toISO(lastMonth)),
      isRead: false,
      recurringDate: toISO(lastMonth),
      customerName: "Subscription",
    },
    {
      id: `recurring-mock-${twoMonthsAgo.getFullYear()}-${twoMonthsAgo.getMonth() + 1}`,
      type: "recurring-payment",
      title: "Recurring Payment",
      message: "Recurring payment from the last 2 months",
      timestamp: getRelativeTime(toISO(twoMonthsAgo)),
      isRead: false,
      recurringDate: toISO(twoMonthsAgo),
      customerName: "Subscription",
    },
  ];
};

const displayUrl = (url: string) =>
  url.replace(/^https?:\/\//, "").replace(/\/$/, "");


export default function ChatScreen() {
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const router = useRouter();
  const [loggingOut, setLoggingOut] = useState(false); 
  const [messages, setMessages] = useState<Message[]>(() => [
    {
      id: "welcome",
      role: "assistant",
      text: "Hi! I'm your PayPal AI assistant. I can help you with payments, transactions, and account management. How can I assist you today? ✨",
    },
  ]);

  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [notificationsLoading, setNotificationsLoading] = useState(false);

  const listRef = useRef<FlatList>(null);
  const canSend = useMemo(() => input.trim().length > 0 && !sending, [input, sending]);
  const scrollToEnd = useCallback(() => {
    requestAnimationFrame(() => listRef.current?.scrollToEnd({ animated: true }));
  }, []);

  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [speakingId, setSpeakingId] = useState<string | null>(null);
  const soundRef = useRef<Audio.Sound | null>(null);
  const ttsCache = useRef<Record<string, string>>({});

  const [isRecording, setIsRecording] = useState(false);
  const recordingRef = useRef<Audio.Recording | null>(null);

  // Animation refs for floating elements
  const floatAnim1 = useRef(new Animated.Value(0)).current;
  const floatAnim2 = useRef(new Animated.Value(0)).current;
  const pulseAnim = useRef(new Animated.Value(1)).current;

  // Fetch notifications from backend
  const fetchNotifications = useCallback(async () => {
  if (MOCK_MODE) return;

  setNotificationsLoading(true);
  try {
    const token = URIS.TOKEN;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };

    const [unpaidRes, recurringRes] = await Promise.all([
      fetch(`${URIS.BACKEND_URI}/unpaid-invoices`, { headers }),
      fetch(`${URIS.BACKEND_URI}/recurring/same_day`, { headers }),
    ]);

    let all: Notification[] = [];

    // unpaid invoices
    if (unpaidRes.ok) {
      const body: PaypalInvoiceAPI = await unpaidRes.json().catch(() => ({ count: 0, items: [] } as PaypalInvoiceAPI));
      all = all.concat(convertPaypalInvoicesToNotifications(body));
    } else {
      console.warn("Unpaid invoices failed:", unpaidRes.status, await unpaidRes.text().catch(() => ""));
    }

    // recurring payments (assuming it returns an array; if it returns {items}, adapt similarly)
    if (recurringRes.ok) {
      const raw = await recurringRes.json().catch(() => []);
      const arr = Array.isArray(raw?.items) ? raw.items : Array.isArray(raw) ? raw : [];
      all = all.concat(convertRecurringPaymentsToNotifications(arr));
    } else {
      console.warn("Recurring payments failed:", recurringRes.status, await recurringRes.text().catch(() => ""));
    }
    all = all.concat(addMockRecurringNotifications());

    // priority: unpaid-invoice first; then leave as-is or add custom date logic if you have real dates
    all.sort((a, b) => {
      if (a.type === "unpaid-invoice" && b.type !== "unpaid-invoice") return -1;
      if (a.type !== "unpaid-invoice" && b.type === "unpaid-invoice") return 1;
      return 0; // no reliable ISO date here; keep fetch order
    });

    setNotifications(all);
  } catch (err) {
    console.error("Error fetching notifications:", err);
  } finally {
    setNotificationsLoading(false);
  }
}, []);


  // Fetch notifications on component mount and set up periodic refresh
  useEffect(() => {
    fetchNotifications();

    // Refresh notifications every 5 minutes
    const interval = setInterval(fetchNotifications, 5 * 60 * 1000);

    return () => clearInterval(interval);
  }, [fetchNotifications]);

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

  useEffect(() => {
      return () => {
        const rec = recordingRef.current;
        if (rec) {
          rec.stopAndUnloadAsync().catch(() => {});
        }
      };
    }, []);

  const copyToClipboard = async (id: string, text: string) => {
    await Clipboard.setStringAsync(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleNotificationPress = (notification: Notification) => {
  setNotifications((prev) => prev.map((n) => (n.id === notification.id ? { ...n, isRead: true } : n)));

  if (notification.type === "unpaid-invoice") {
    const amountLine =
      notification.amount && notification.currency
        ? `Amount: ${formatCurrency(notification.amount, notification.currency)}\n`
        : "";

    Alert.alert(
      "Unpaid Invoice",
      `Recipient: ${notification.customerName}\n${amountLine}${notification.link ? "Open the invoice to view or pay." : ""}`,
      [
        { text: "Close", style: "cancel" },
        ...(notification.link
          ? [
              {
                text: "Open Invoice",
                onPress: () => Linking.openURL(notification.link!),
              },
            ]
          : []),
      ]
    );
  } else if (notification.type === "recurring-payment") {
    Alert.alert(
      "Recurring Payment Due",
      `Payment to ${notification.customerName}\n${
        notification.amount && notification.currency
          ? `Amount: ${formatCurrency(notification.amount, notification.currency)}\n`
          : ""
      }Due: ${notification.recurringDate || "Today"}`,
      [
        { text: "Cancel", style: "cancel" },
        { text: "Process Payment", onPress: () => console.log("Process recurring payment:", notification.id) },
      ]
    );
  }
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
    const token = URIS.TOKEN;
    // const token = getToken();
    console.log("[CHAT] Sending to backend…", { len: userText.length, messages: messages.length, token: token });
    const res = await fetch(`${URIS.BACKEND_URI}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify([
        ...messages.map(({ role, text }) => ({ role, content: text })),
        { role: "user", content: userText },
      ]),
    });

  let data: any;
  try {
    // Try to parse JSON even if status is not ok
    data = await res.json();
  } catch (err) {
    console.error("Failed to parse error response:", err);
    throw new Error(`HTTP ${res.status} (no JSON body)`);
  }

  if (!res.ok) {
    console.error("Backend error payload:", data);
    throw new Error(`HTTP ${res.status}: ${JSON.stringify(data)}`);
  }

  return (data.reply as string) ?? "…";
  };

  const askMicPermission = useCallback(async () => {
      const { status } = await Audio.requestPermissionsAsync();
      if (status !== "granted") throw new Error("Microphone permission denied");
    }, []);

    const startRecording = useCallback(async () => {
      await askMicPermission();

      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
        shouldDuckAndroid: true,
        //interruptionModeIOS: Audio.INTERRUPTION_MODE_IOS_DO_NOT_MIX,
        //interruptionModeAndroid: Audio.INTERRUPTION_MODE_ANDROID_DO_NOT_MIX,
        playThroughEarpieceAndroid: false,
        staysActiveInBackground: false,
      });

      const recording = new Audio.Recording();
      await recording.prepareToRecordAsync(Audio.RecordingOptionsPresets.HIGH_QUALITY);
      await recording.startAsync();

      recordingRef.current = recording;
      setIsRecording(true);
   }, [askMicPermission]);

  const stopRecording = useCallback(async () => {
      const rec = recordingRef.current;
      if (!rec) return null;

      try {
        await rec.stopAndUnloadAsync();
      } catch {}

      const uri = rec.getURI();
      recordingRef.current = null;
      setIsRecording(false);

      await Audio.setAudioModeAsync({ allowsRecordingIOS: false });

      return uri;
  }, []);


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

  const uploadForTranscription = useCallback(async (uri: string) => {
    const token = URIS.TOKEN;
    // const token = getToken();

  if (Platform.OS === "web") {
    // On web: use fetch + FormData with a Blob
    // NOTE: If your recording comes from a web-only recorder, you'll already have a Blob.
    // If `uri` is a blob/data URL, fetch it back into a Blob:
    const resp = await fetch(uri);
    const blob = await resp.blob();

    const form = new FormData();
    // Name the file with an extension your backend accepts (m4a or wav if you converted).
    form.append("file", blob, `recording-${Date.now()}.m4a`);

    const res = await fetch("http://127.0.0.1:8000/stt", {
      method: "POST",
      // Don't set Content-Type manually; the browser adds the correct multipart boundary.
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      body: form,
    });

    if (!res.ok) throw new Error(`STT HTTP ${res.status}`);
    const data = await res.json();
    return (data.text as string) ?? "";
  }

  // On native (iOS/Android): keep uploadAsync
  const result = await FileSystem.uploadAsync(
    "http://127.0.0.1:8000/stt",
    uri,
    {
      httpMethod: "POST",
      uploadType: FileSystem.FileSystemUploadType.MULTIPART,
      fieldName: "file",
      mimeType: "audio/m4a", // or "audio/wav" if you transcoded
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    }
  );

  if (result.status !== 200) throw new Error(`STT HTTP ${result.status}: ${result.body}`);
  const data = JSON.parse(result.body);
  return (data.text as string) ?? "";
}, []);


  const onSendWithText = useCallback(async (text: string) => {
        if (!text.trim()) return;
        setInput("");
        await sendMessage(text);
      }, [sendMessage]);

  const onMicPress = useCallback(async () => {
      try {
        if (isRecording) {
          const uri = await stopRecording();
          if (!uri) return;
          const text = await uploadForTranscription(uri);
          setInput((prev) => (prev.length ? `${prev} ${text}` : text));
        } else {
          await startRecording();
        }
      } catch (e) {
        console.warn("Mic error:", e);
      }
    }, [isRecording, startRecording, stopRecording, uploadForTranscription]);

  const handleChangeText = (t: string) => {
    if (t.endsWith("\n")) {
      const toSend = t.replace(/\n+$/, "");
      onSendWithText(toSend);
    } else {
      setInput(t);
    }
  };

const isStartingRef = useRef(false);
const speakingIdRef = useRef<string | null>(null);
const stopInProgressRef = useRef(false);
const lastStopAtRef = useRef(0);

// simple click guard to avoid double-fires on web
const lastPressTsRef = useRef(0);
const lastPressIdRef = useRef<string | null>(null);

// keep ref in sync with state
useEffect(() => {
  speakingIdRef.current = speakingId;
}, [speakingId]);

  const stopSpeaking = useCallback(async () => {
  if (stopInProgressRef.current) return;
  stopInProgressRef.current = true;

  const s = soundRef.current;
  soundRef.current = null;

  try {
    if (s) {
      s.setOnPlaybackStatusUpdate(null);
      if (Platform.OS === "web") {
        try { await s.pauseAsync(); } catch {}
        try { await s.setPositionAsync(0); } catch {}
      } else {
        try { await s.stopAsync(); } catch {}
      }
      try { await s.unloadAsync(); } catch {}
    }
  } finally {
    // clear both state and ref so toggle works reliably
    speakingIdRef.current = null;
    setSpeakingId(null);
    lastStopAtRef.current = Date.now();
    stopInProgressRef.current = false;
  }
}, []);

// -------------------- PLAY --------------------
const playLocalFile = useCallback(async (fileUri: string) => {
  // ❌ no stopSpeaking here — it resets speakingId during start

  const { sound } = await Audio.Sound.createAsync(
    { uri: fileUri },
    { shouldPlay: true, progressUpdateIntervalMillis: 250 }
  );

  soundRef.current = sound;

  sound.setOnPlaybackStatusUpdate((status) => {
    if (!status.isLoaded) return;
    if ((status as any).didJustFinish) {
      console.log("[TTS] Finished");
      // fire-and-forget
      stopSpeaking();
    }
  });
}, [stopSpeaking]);

// -------------------- FETCH --------------------
const fetchTtsFile = useCallback(async (id: string, text: string) => {
  const cached = ttsCache.current[id];
  if (cached) return cached;

  const token = URIS.TOKEN;
  // const token = getToken();
  console.log("[TTS] Fetching MP3 from backend…", { len: text.length });

  const res = await fetch(`${URIS.BACKEND_URI}/tts`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ text, filename: null, download: false }),
  });

  if (!res.ok) throw new Error(`TTS HTTP ${res.status}`);

  if (Platform.OS === "web") {
    // Force correct MIME on web and create a fresh blob URL
    const ab = await res.arrayBuffer();
    const blob = new Blob([ab], { type: "audio/mpeg" });
    const objectUrl = URL.createObjectURL(blob);
    ttsCache.current[id] = objectUrl;
    webBlobUrls.current.add(objectUrl); // track for cleanup later
    console.log("[TTS] Created blob URL:", objectUrl);
    return objectUrl;
  } else {
    // Native: save to cache as base64
    const arrayBuffer = await res.arrayBuffer();
    const base64 = Buffer.from(arrayBuffer).toString("base64");

    const fileUri = `${FileSystem.cacheDirectory}tts-${id}.mp3`;
    await FileSystem.writeAsStringAsync(fileUri, base64, {
      encoding: FileSystem.EncodingType.Base64,
    });

    console.log("[TTS] Saved MP3 to cache:", fileUri);
    ttsCache.current[id] = fileUri;
    return fileUri;
  }
}, []);

// -------------------- SPEAK --------------------
const speakMessage = useCallback(async (id: string, text: string) => {
  console.log("[TTS] handler", { id, speakingIdRef: speakingIdRef.current, stopInProgress: stopInProgressRef.current });

  const now = Date.now();

  if (stopInProgressRef.current) return;
  if (now - lastStopAtRef.current < 400) return;

  // debounce RN Web double-fires
  if (lastPressIdRef.current === id && now - lastPressTsRef.current < 350) return;
  lastPressIdRef.current = id;
  lastPressTsRef.current = now;

  if (isStartingRef.current) return;

  // Toggle: same id -> stop and exit
  if (speakingIdRef.current === id) {
    await stopSpeaking();
    return;
  }

  isStartingRef.current = true;
  try {
    if (MOCK_MODE) {
      console.log("[TTS MOCK] button pressed", {
        id,
        preview: text.slice(0, 80),
        length: text.length,
      });
      return;
    }

    // Switching to a different id? stop current first (not in playLocalFile)
    if (speakingIdRef.current && speakingIdRef.current !== id) {
      await stopSpeaking();
      if (Date.now() - lastStopAtRef.current < 200) return;
    }

    // Mark active id BEFORE awaits
    speakingIdRef.current = id;
    setSpeakingId(id);

    const fileUri = await fetchTtsFile(id, text);
    await playLocalFile(fileUri);
    console.log("[TTS] Playing:", fileUri);
  } catch (e) {
    console.warn("TTS error:", e);
    speakingIdRef.current = null;
    setSpeakingId(null);
  } finally {
    isStartingRef.current = false;
  }
}, [MOCK_MODE, stopSpeaking, fetchTtsFile, playLocalFile]);

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

  const logout = useCallback(() => {
  Alert.alert(
    "Log out",
    "Are you sure you want to log out?",
    [
      { text: "Cancel", style: "cancel" },
      {
        text: "Log out",
        style: "destructive",
        onPress: async () => {
          try {
            setLoggingOut(true);
            await stopSpeaking();
            await AsyncStorage.removeItem("token");
            setMessages([
              {
                id: "welcome",
                role: "assistant",
                text:
                  "Hi! I'm your PayPal AI assistant. I can help you with payments, transactions, and account management. How can I assist you today? ✨",
              },
            ]);

            // ⬇️ Go to /login (cannot go back to tabs)
            router.replace("/login");
          } finally {
            setLoggingOut(false);
          }
        },
      },
    ],
    { cancelable: true }
  );
}, [router, stopSpeaking, setMessages]);

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
            
              <View style={styles.headerRow}>
                <View style={styles.headerContent}>
                  <View style={styles.headerIcon}>
                    <Text style={styles.headerEmoji}>🤖</Text>
                  </View>
                  <View style={styles.headerTextContainer}>
                    <Text style={styles.headerTitle}>PayPal AI Assistant</Text>
                    <Text style={styles.headerSubtitle}>Online • Ready to help</Text>
                  </View>
              </View>

                <Pressable
                  onPress={logout}
                  disabled={loggingOut}
                  hitSlop={10}
                  style={({ pressed }) => [
                    styles.logoutBtn,
                    loggingOut && { opacity: 0.6 },
                    pressed && { transform: [{ scale: 0.98 }] },
                  ]}
                  accessibilityRole="button"
                  accessibilityLabel="Log out"
                >
                  {loggingOut ? (
                    <ActivityIndicator size="small" color="#0A0A2E" />
                  ) : (
                    <View style={styles.logoutInner}>
                      <Ionicons name="log-out-outline" size={16} color="#0A0A2E" />
                      <Text style={styles.logoutText}>Log out</Text>
                    </View>
                  )}
                </Pressable>
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
                onPress={onMicPress}
                style={[styles.micBtn, isRecording && styles.micBtnActive]}
              >
                <Ionicons name={isRecording ? "stop" : "mic"} size={20} color="#0A0A2E" />
              </Pressable>
              
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
            isLoading={notificationsLoading}
            onRefresh={fetchNotifications}
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
  linkRow: {
    marginTop: 8,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  linkText: {
    color: "#00D4FF",
    fontSize: 13,
    textDecorationLine: "underline",
    flexShrink: 1,
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
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  headerContent: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  logoutBtn: {
    paddingHorizontal: 12,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#00D4FF',
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#00D4FF',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 3,
    elevation: 3,
  },
  logoutInner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  logoutText: {
    color: '#0A0A2E',
    fontWeight: '700',
    fontSize: 13,
    letterSpacing: -0.2,
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
  micBtn: {
      width: 44,
      height: 44,
      borderRadius: 22,
      backgroundColor: '#FFFFFF',
      justifyContent: 'center',
      alignItems: 'center',
      shadowColor: '#FFFFFF',
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.2,
      shadowRadius: 4,
      elevation: 4,
  },
  micBtnActive: {
      backgroundColor: '#FF6B9D',
      shadowColor: '#FF6B9D',
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
  notificationHeaderActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  refreshBtn: {
    padding: 4,
    borderRadius: 12,
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
  },
  notificationsList: {
    flex: 1,
    paddingTop: 8,
  },
  notificationsContent: {
    paddingHorizontal: 12,
    paddingBottom: 20,
  },
  emptyNotifications: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 40,
  },
  emptyNotificationsText: {
    color: 'rgba(255, 255, 255, 0.6)',
    fontSize: 16,
    fontWeight: '500',
    marginTop: 12,
  },
  emptyNotificationsSubtext: {
    color: 'rgba(255, 255, 255, 0.4)',
    fontSize: 14,
    marginTop: 4,
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