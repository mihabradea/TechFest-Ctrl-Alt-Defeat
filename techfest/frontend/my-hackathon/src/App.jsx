import React, { useEffect, useState } from "react";

export default function App() {
  const [state, setState] = useState("");

  useEffect(() => {
    fetch("http://localhost:8000/api/state", { credentials: "include" })
      .then(res => res.text())
      .then(setState);
  }, []);

  useEffect(() => {
    if (!state) return;
    console.log("Using state:", state);
    const script = document.createElement("script");
    script.src = "https://www.paypalobjects.com/js/external/api.js";
    script.async = true;
    script.onload = () => {
      if (window.paypal) {
        window.paypal.use(["login"], function (login) {
          login.render({
            authend: "sandbox",
            appid: "AUwDbh92cYpOxREvA3aeugMEfJdMH5U-HwMvLi0z-ABQQ0puDUd1ijGzFsh6s7ugl2zisrqI4tZGYRAT",
            scopes: "openid email https://uri.paypal.com/services/paypalattributes https://uri.paypal.com/services/invoicing",
            containerid: "lippButton",
            responseType: "code",
            locale: "en-us",
            buttonType: "LWP",
            buttonShape: "pill",
            buttonSize: "sm",
            fullPage: "true",
            returnurl: "https://myexpo1327545753.z1.web.core.windows.net/",
            state: state
          });
        });
      }
    };
    document.body.appendChild(script);
  }, [state]);

  useEffect(() => {
    // Add animated background
    const bg = document.createElement("div");
    bg.style.position = "fixed";
    bg.style.top = "0";
    bg.style.left = "0";
    bg.style.width = "100vw";
    bg.style.height = "100vh";
    bg.style.zIndex = "-1";
    bg.style.background = "radial-gradient(circle at 20% 20%, #0070ff55 0%, transparent 60%), radial-gradient(circle at 80% 80%, #00eaff33 0%, transparent 60%), linear-gradient(135deg, #0a1f3d 0%, #0070ba 100%)";
    bg.style.animation = "bgmove 10s linear infinite alternate";
    document.body.appendChild(bg);
    const style = document.createElement("style");
    style.innerHTML = `@keyframes bgmove { 0% { filter: blur(0px); } 100% { filter: blur(8px); } }`;
    document.head.appendChild(style);
    return () => { document.body.removeChild(bg); document.head.removeChild(style); };
  }, []);

  useEffect(() => {
    // Neon effect for PayPal button
    const btn = document.getElementById("lippButton");
    if (btn) {
      btn.style.display = "flex";
      btn.style.justifyContent = "center";
      btn.style.alignItems = "center";
      btn.style.height = "80px";
      btn.style.margin = "0 auto";
      btn.style.width = "100%";
    }
    // Add neon effect to PayPal button after it renders
    const observer = new MutationObserver(() => {
      const paypalBtn = btn && btn.querySelector("button");
      if (paypalBtn) {
        paypalBtn.style.boxShadow = "0 0 20px 5px #00eaff, 0 0 40px 10px #0070ff";
        paypalBtn.style.transition = "box-shadow 0.3s";
        paypalBtn.onmouseover = () => {
          paypalBtn.style.boxShadow = "0 0 40px 10px #00eaff, 0 0 80px 20px #0070ff";
        };
        paypalBtn.onmouseout = () => {
          paypalBtn.style.boxShadow = "0 0 20px 5px #00eaff, 0 0 40px 10px #0070ff";
        };
      }
    });
    if (btn) observer.observe(btn, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, []);

  return (
    <div style={{ minHeight: "100vh", width: "100vw", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", width: "100%" }}>
        <h1 style={{ color: "#fff", textShadow: "0 0 8px #0070ff, 0 0 16px #00eaff", fontWeight: 700, fontSize: "2.5rem", marginBottom: "2rem", letterSpacing: "2px" }}>
          TechFest PayPal Connect
        </h1>
        <span id="lippButton"></span>
      </div>
    </div>
  );
}