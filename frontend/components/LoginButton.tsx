// PayPalLoginButton.tsx// React Native component to start the "Log in with PayPal" OAuth flow using the
// manual button guide you pasted. Uses an external browser + deep link return.
//
// ❗ Security note: Exchange the authorization code for tokens on YOUR BACKEND.
//    Do NOT ship your PayPal client secret in the mobile app.

import * as Random from 'expo-random'; // If not using Expo, polyfill with another random lib
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Image, Linking, Platform, Pressable } from 'react-native';
import InAppBrowser from 'react-native-inappbrowser-reborn';
import { URIS } from '@/constants/constants';
// =====================
// 1) CONFIGURATION
// =====================
// Fill these from your environment / secrets service (NOT hardcoded in prod):
const PAYPAL_CLIENT_ID = URIS.PAYPAL_CLIENT_ID;
const REDIRECT_URI = URIS.REDIRECT_URI;
const USE_SANDBOX = true; // set false for live

// Scopes: include at least "openid". Add others as needed.
const SCOPES = [
  'email'
];

// Advanced parameter from the guide. If you prefer mini-browser (default), omit this param.
const FULL_PAGE = false; // true opens full-page in same tab (browser), false = mini browser

const AUTH_BASE = USE_SANDBOX
  ? 'https://www.sandbox.paypal.com'
  : 'https://www.paypal.com';

// =====================
// 2) HELPERS
// =====================
function urlEncodeParams(params: Record<string, string | undefined>) {
  const usp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (typeof v === 'string' && v.length) usp.append(k, v);
  });
  return usp.toString();
}

async function generateState(bytes = 16) {
  const arr = await Random.getRandomBytesAsync(bytes);
  return Array.from(arr, b => b.toString(16).padStart(2, '0')).join('');
}

// =====================
// 3) MAIN COMPONENT
// =====================
export default function PayPalLoginButton({
  onSuccess,
  onCancel,
  onError,
}: {
  onSuccess?: (payload: { code: string; scope?: string; state?: string }) => void;
  onCancel?: () => void;
  onError?: (err: unknown) => void;
}) {
  const [loading, setLoading] = useState(false);
  const stateRef = useRef<string | null>(null);

  // Build the authorization URL as in the guide
  const buildAuthUrl = useCallback(async () => {
    const state = await generateState();
    stateRef.current = state;

    const query = urlEncodeParams({
      flowEntry: 'static',
      client_id: PAYPAL_CLIENT_ID,
      response_type: 'code',
      scope: SCOPES.join(' '),
      redirect_uri: REDIRECT_URI,
      state,
      fullPage: FULL_PAGE ? 'true' : undefined,
    });

    // Note: the guide shows both /signin/authorize and /connect/. Either works for the static flow.
    // We'll use /signin/authorize to mirror the template shown earlier.
    return `${AUTH_BASE}/signin/authorize?${query}`;
  }, []);

  // Deep link handler: your redirect URI should look like yourapp://oauth/callback/paypal
  useEffect(() => {
    const handleUrl = (event: { url: string }) => {
      const { url } = event;
      // Example redirect: yourapp://oauth/callback/paypal?code=XXXX&scope=openid%20profile&state=YYYY
      const qIndex = url.indexOf('?');
      const params = new URLSearchParams(qIndex >= 0 ? url.slice(qIndex + 1) : '');
      const code = params.get('code') ?? undefined;
      const scope = params.get('scope') ?? undefined;
      const state = params.get('state') ?? undefined;

      if (stateRef.current && state && state !== stateRef.current) {
        onError?.(new Error('State mismatch. Possible CSRF.'));
        return;
      }

      if (code) {
        onSuccess?.({ code, scope, state });
      } else if (params.get('error')) {
        onError?.(new Error(params.get('error_description') || 'Authorization error'));
      } else {
        onCancel?.();
      }
    };

    const sub = Linking.addEventListener('url', handleUrl);
    // If the app was cold-started via the deep link, grab the initial URL too
    (async () => {
      const initUrl = await Linking.getInitialURL();
      if (initUrl) handleUrl({ url: initUrl });
    })();

    return () => sub.remove();
  }, [onCancel, onError, onSuccess]);

  const openAuth = useCallback(async () => {
    try {
      setLoading(true);
      const authUrl = await buildAuthUrl();

      if (Platform.OS === 'web') { 
        window.open(authUrl, '_blank');
      } else if (await InAppBrowser.isAvailable()) {
        const res = await InAppBrowser.openAuth(authUrl, REDIRECT_URI, {
          // iOS options
          ephemeralWebSession: true,
          // Android options
          showTitle: true,
          enableUrlBarHiding: true,
          enableDefaultShare: false,
        });

        if (res.type === 'cancel') {
          onCancel?.();
        }
      } else {
        // Fallback to plain Linking
        const supported = await Linking.canOpenURL(authUrl);
        if (!supported) throw new Error('No browser installed to open the PayPal login');
        await Linking.openURL(authUrl);
      }
    } catch (e) {
      onError?.(e);
    } finally {
      setLoading(false);
    }
  }, [buildAuthUrl, onCancel, onError]);

  return (
    <Pressable
      onPress={openAuth}
      disabled={loading}
      style={({ pressed }) => ({
        opacity: pressed || loading ? 0.6 : 1,
        borderRadius: 12,
        overflow: 'hidden',
      })}
      accessibilityRole="button"
      accessibilityLabel="Log in with PayPal"
    >
      {/* Option A: Use PayPal-hosted branded image (recommended by the guide) */}
      <Image
        source={{ uri: 'https://www.paypalobjects.com/devdoc/log-in-with-paypal-button.png' }}
        resizeMode="cover"
        // Size your button as you like:
        style={{
        width: 200,   // 👈 fixed width instead of 100%
        height: 48,
        backgroundColor: '#fff',
      }}
      />
    </Pressable>
  );
}

// =====================
// 4) APP INTEGRATION NOTES
// =====================
// a) Deep linking setup
//    - iOS: In Xcode, add URL Type with Identifier="yourapp" and URL Schemes="yourapp".
//    - Android: In AndroidManifest.xml add an <intent-filter> for your scheme/host/path
//      matching REDIRECT_URI (e.g., yourapp://oauth/callback/paypal).
//    - Expo (app.json/app.config.js): add "scheme": "yourapp" and, if needed, a custom intent filter.
//    - The same REDIRECT_URI must be registered in PayPal Developer Dashboard (Apps & Credentials).
//
// b) Server-side token exchange (RECOMMENDED)
//    POST /api/paypal/exchange { code }
//    Your backend should:
//      1. Validate the `state` if you echo it back.
//      2. Exchange the code for tokens via PayPal's token endpoint using client_id + client_secret.
//      3. Fetch the user profile (userinfo) if you requested OIDC scopes.
//      4. Create a session/JWT for your app and return it to the client.
//    IMPORTANT: Do not keep client_secret in the app. Never perform the token exchange on-device.
//
// c) Handling results in-app
//    <PayPalLoginButton
//      onSuccess={async ({ code, scope, state }) => {
//        try {
//          const res = await fetch('https://your.api.host/api/paypal/exchange', {
//            method: 'POST',
//            headers: { 'Content-Type': 'application/json' },
//            body: JSON.stringify({ code, state }),
//          });
//          if (!res.ok) throw new Error('Token exchange failed');
//          const session = await res.json();
//          // session might contain your own app token + PayPal profile info
//          // navigate to your logged-in screen
//        } catch (e) {
//          Alert.alert('Login failed', (e as Error).message);
//        }
//      }}
//      onCancel={() => console.log('User cancelled PayPal login')}
//      onError={(err) => Alert.alert('PayPal error', String(err))}
//    />
//
// d) Testing sandbox vs live
//    - Toggle USE_SANDBOX and use the appropriate client ID.
//    - Ensure the REDIRECT_URI exactly matches one registered in Apps & Credentials.
//    - Verify scopes: If you request unsupported scopes, PayPal will error.
//
// e) Optional: Full-page vs mini-browser
//    - The guide says omit fullPage param for mini-browser. We pass it only when FULL_PAGE = true.
//
// f) Alternatives
//    - Expo users can use `expo-auth-session` with `promptAsync` and a custom discovery config
//      pointing to the same authorization endpoint, while still doing the code exchange on the server.
