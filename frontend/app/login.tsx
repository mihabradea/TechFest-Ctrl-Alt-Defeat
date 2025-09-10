// frontend/app/login.tsx
import React, { useState, useEffect, useRef } from "react";
import { 
  View, 
  Text, 
  Pressable, 
  StyleSheet, 
  Alert, 
  Dimensions, 
  Animated,
  StatusBar 
} from "react-native";
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useRouter } from "expo-router";
import PayPalLoginButton from "@/components/LoginButton";
import { LinearGradient } from 'expo-linear-gradient';

const { width, height } = Dimensions.get('window');

export default function LoginScreen() {
  const router = useRouter();
  const [msg, setMsg] = useState("");
  
  // Animation values
  const fadeAnim = useRef(new Animated.Value(0)).current;
  const slideAnim = useRef(new Animated.Value(50)).current;
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const floatAnim = useRef(new Animated.Value(0)).current;
  const [attemptedLogin, setAttemptedLogin] = useState(false);

  useEffect(() => {
    // Entrance animations
    Animated.parallel([
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 1000,
        useNativeDriver: true,
      }),
      Animated.timing(slideAnim, {
        toValue: 0,
        duration: 800,
        useNativeDriver: true,
      }),
    ]).start();

    // Continuous floating animation for decorative elements
    const floatAnimation = Animated.loop(
      Animated.sequence([
        Animated.timing(floatAnim, {
          toValue: -10,
          duration: 2000,
          useNativeDriver: true,
        }),
        Animated.timing(floatAnim, {
          toValue: 10,
          duration: 2000,
          useNativeDriver: true,
        }),
      ])
    );
    floatAnimation.start();

    // Pulse animation for accent elements
    const pulseAnimation = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, {
          toValue: 1.1,
          duration: 1500,
          useNativeDriver: true,
        }),
        Animated.timing(pulseAnim, {
          toValue: 1,
          duration: 1500,
          useNativeDriver: true,
        }),
      ])
    );
    pulseAnimation.start();
  }, []);

  return (
    <>
      <StatusBar barStyle="light-content" backgroundColor="#0A0A2E" />
      <LinearGradient
        colors={['#0A0A2E', '#16213E', '#0E4B99', '#2E86AB']}
        style={styles.gradient}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
      >
        {/* Background decorative elements */}
        <View style={styles.backgroundElements}>
          <Animated.View 
            style={[
              styles.floatingCircle, 
              styles.circle1,
              { transform: [{ translateY: floatAnim }] }
            ]} 
          />
          <Animated.View 
            style={[
              styles.floatingCircle, 
              styles.circle2,
              { transform: [{ translateY: floatAnim }, { scale: pulseAnim }] }
            ]} 
          />
          <Animated.View 
            style={[
              styles.floatingCircle, 
              styles.circle3,
              { transform: [{ translateY: floatAnim }] }
            ]} 
          />
          
          {/* Neural network lines */}
          <View style={styles.networkLines}>
            <View style={[styles.line, styles.line1]} />
            <View style={[styles.line, styles.line2]} />
            <View style={[styles.line, styles.line3]} />
          </View>
        </View>

        <Animated.View 
          style={[
            styles.container,
            {
              opacity: fadeAnim,
              transform: [{ translateY: slideAnim }]
            }
          ]}
        >
          {/* Header Section */}
          <View style={styles.header}>
            <View style={styles.logoContainer}>
              <Animated.View 
                style={[
                  styles.botIcon,
                  { transform: [{ scale: pulseAnim }] }
                ]}
              >
                <Text style={styles.botEmoji}>🤖</Text>
              </Animated.View>
            </View>
            
            <Text style={styles.title}>PayPal AI Assistant</Text>
            <Text style={styles.subtitle}>
              Intelligent payments powered by conversation
            </Text>
          </View>

          {/* Main Content */}
          <View style={styles.mainContent}>
            {/* Feature highlights */}
            <View style={styles.featuresContainer}>
              <FeatureItem 
                icon="💬" 
                text="Chat-based transactions" 
                delay={200}
              />
              <FeatureItem 
                icon="🔒" 
                text="Secure & encrypted" 
                delay={400}
              />
              <FeatureItem 
                icon="⚡" 
                text="Instant processing" 
                delay={600}
              />
            </View>

            {/* Login Section */}
            <View style={styles.loginSection}>
              <Text style={styles.loginPrompt}>
                Connect with PayPal to get started
              </Text>
              
              <View style={styles.buttonContainer}>
                <PayPalLoginButton
                    onSuccess={async ({ code, state }) => {
                      setAttemptedLogin(false);
                      await AsyncStorage.setItem('token', `DEV_TOKEN_${Date.now()}`);
                      router.replace('/');
                    }}
                    onCancel={() => attemptedLogin && setMsg("Login cancelled")}
                    onError={(err) => {
                      if (attemptedLogin) {
                        const m = err instanceof Error ? err.message : String(err);
                        setMsg(m);
                        Alert.alert("PayPal error", m);
                      }
                    }}
                />
              </View>

              {!!msg && (
                <Animated.View style={styles.messageContainer}>
                  <Text style={styles.responseMessage}>{msg}</Text>
                </Animated.View>
              )}
            </View>
          </View>

          {/* Footer */}
          <View style={styles.footer}>
            <Text style={styles.footerText}>
              By continuing, you agree to our Terms & Privacy Policy
            </Text>
          </View>
        </Animated.View>
      </LinearGradient>
    </>
  );
}

// Feature item component with animation
type FeatureItemProps = {
  icon: string;
  text: string;
  delay: number;
};

const FeatureItem = ({ icon, text, delay }: FeatureItemProps) => {
  const fadeAnim = useRef(new Animated.Value(0)).current;
  const slideAnim = useRef(new Animated.Value(20)).current;

  useEffect(() => {
    setTimeout(() => {
      Animated.parallel([
        Animated.timing(fadeAnim, {
          toValue: 1,
          duration: 600,
          useNativeDriver: true,
        }),
        Animated.timing(slideAnim, {
          toValue: 0,
          duration: 600,
          useNativeDriver: true,
        }),
      ]).start();
    }, delay);
  }, []);

  return (
    <Animated.View 
      style={[
        styles.featureItem,
        {
          opacity: fadeAnim,
          transform: [{ translateX: slideAnim }]
        }
      ]}
    >
      <Text style={styles.featureIcon}>{icon}</Text>
      <Text style={styles.featureText}>{text}</Text>
    </Animated.View>
  );
};

const styles = StyleSheet.create({
  gradient: {
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
    opacity: 0.1,
  },
  circle1: {
    width: 120,
    height: 120,
    backgroundColor: '#00D4FF',
    top: '10%',
    left: '10%',
  },
  circle2: {
    width: 80,
    height: 80,
    backgroundColor: '#FF6B9D',
    top: '20%',
    right: '15%',
  },
  circle3: {
    width: 60,
    height: 60,
    backgroundColor: '#00FF88',
    bottom: '25%',
    left: '20%',
  },
  networkLines: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
  },
  line: {
    position: 'absolute',
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    height: 1,
  },
  line1: {
    width: '60%',
    top: '30%',
    left: '20%',
    transform: [{ rotate: '15deg' }],
  },
  line2: {
    width: '40%',
    top: '60%',
    right: '10%',
    transform: [{ rotate: '-20deg' }],
  },
  line3: {
    width: '50%',
    bottom: '20%',
    left: '10%',
    transform: [{ rotate: '45deg' }],
  },
  container: {
    flex: 1,
    paddingHorizontal: 24,
    paddingTop: 60,
    paddingBottom: 40,
  },
  header: {
    alignItems: 'center',
    marginBottom: 40,
  },
  logoContainer: {
    marginBottom: 20,
  },
  botIcon: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: 'rgba(255, 255, 255, 0.2)',
  },
  botEmoji: {
    fontSize: 40,
  },
  title: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#FFFFFF',
    textAlign: 'center',
    marginBottom: 8,
    letterSpacing: -0.5,
  },
  subtitle: {
    fontSize: 16,
    color: 'rgba(255, 255, 255, 0.8)',
    textAlign: 'center',
    lineHeight: 24,
  },
  mainContent: {
    flex: 1,
    justifyContent: 'center',
  },
  featuresContainer: {
    marginBottom: 50,
  },
  featureItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 20,
    backgroundColor: 'rgba(255, 255, 255, 0.08)',
    borderRadius: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
  },
  featureIcon: {
    fontSize: 24,
    marginRight: 16,
  },
  featureText: {
    fontSize: 16,
    color: 'rgba(255, 255, 255, 0.9)',
    fontWeight: '500',
  },
  loginSection: {
    alignItems: 'center',
  },
  loginPrompt: {
    fontSize: 18,
    color: '#FFFFFF',
    textAlign: 'center',
    marginBottom: 30,
    fontWeight: '500',
    lineHeight: 26,
  },
  buttonContainer: {
    width: '100%',
    alignItems: 'center',
    marginBottom: 20,
  },
  messageContainer: {
    backgroundColor: 'rgba(255, 107, 107, 0.15)',
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderWidth: 1,
    borderColor: 'rgba(255, 107, 107, 0.3)',
  },
  responseMessage: {
    color: '#FF6B6B',
    textAlign: 'center',
    fontSize: 14,
    fontWeight: '500',
  },
  footer: {
    alignItems: 'center',
    paddingTop: 20,
  },
  footerText: {
    fontSize: 12,
    color: 'rgba(255, 255, 255, 0.6)',
    textAlign: 'center',
    lineHeight: 18,
  },
});