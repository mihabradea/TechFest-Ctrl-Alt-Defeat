let token: string | null = null;

// Set token
export function setToken(newToken: string): void {
  token = newToken;
  // optional: persist in localStorage if in browser
  if (typeof window !== "undefined") {
    localStorage.setItem("token", newToken);
  }
}

// Get token
export function getToken(): string | null {
  if (token) return token;

  // optional: fallback to localStorage if available
  if (typeof window !== "undefined") {
    return localStorage.getItem("token");
  }

  return null;
}
