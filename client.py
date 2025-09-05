# client.py
import tkinter as tk
from tkinter import messagebox
import requests

from mathUI import MathUI

API = "http://localhost:5000"  # presupunem că Flask rulează pe portul 5000

def on_login():
    email = email_entry.get()
    pwd   = pwd_entry.get()
    try:
        resp = requests.post(f"{API}/login", json={"email": email, "password": pwd})
        data = resp.json()
    except Exception as e:
        messagebox.showerror("Eroare", f"Nu pot contacta serverul:\n{e}")
        return

    if resp.status_code == 200 and data.get("status") == "success":
        # ─── Aici ───
        # 1) curăță toate widget-urile din root
        for w in root.winfo_children():
            w.destroy()
        # 2) lansează interfața MathUI în același root
        MathUI(root)
    else:
        messagebox.showerror("Login eșuat", data.get("message", "—"))

# ── Construiește UI-ul de login ──
root = tk.Tk()
root.title("Login")

tk.Label(root, text="Email:").pack(pady=4)
email_entry = tk.Entry(root)
email_entry.pack(pady=4)

tk.Label(root, text="Parolă:").pack(pady=4)
pwd_entry = tk.Entry(root, show="*")
pwd_entry.pack(pady=4)

tk.Button(root, text="Login", command=on_login).pack(pady=8)

root.mainloop()
