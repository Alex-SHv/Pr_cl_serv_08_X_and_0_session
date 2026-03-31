import tkinter as tk
from tkinter import messagebox, scrolledtext
import socket
import json
import hashlib
import config

def xor_cipher(data, key):
    hashed_key = hashlib.sha256(key).digest()
    key_len = len(hashed_key)
    if isinstance(data, str):
        data = data.encode('utf-8')
    return bytes([b ^ hashed_key[i % key_len] for i, b in enumerate(data)])

def encrypt_data(data_dict):
    json_str = json.dumps(data_dict)
    encrypted = xor_cipher(json_str, config.SECRET_KEY)
    return (encrypted.hex() + "\n").encode('utf-8')

def decrypt_data(encrypted_bytes):
    try:
        hex_data = encrypted_bytes.decode('utf-8').strip()
        if not hex_data:
            return {"error": "Empty data"}
        raw_encrypted = bytes.fromhex(hex_data)
        decrypted_json = xor_cipher(raw_encrypted, config.SECRET_KEY).decode('utf-8')
        return json.loads(decrypted_json)
    except Exception as e:
        return {"status": "error", "message": f"Ошибка декодирования: {e}"}

def send_admin_request(req_dict):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((config.HOST, config.PORT))
            s.send(encrypt_data(req_dict))
            f_obj = s.makefile('rb')
            line = f_obj.readline()
            return decrypt_data(line)
    except Exception as e:
        return {"status": "error", "message": str(e)}

def send_admin_request(req_dict):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)

            s.connect((config.HOST, config.PORT))

            s.sendall(encrypt_data(req_dict))

            f_obj = s.makefile('rb')
            line = f_obj.readline()

            if not line:
                return {"status": "error", "message": "Сервер не отправил ответ"}

            return decrypt_data(line)
    except socket.timeout:
        return {"status": "error", "message": "Таймаут: сервер не ответил в течение 5 сек"}
    except ConnectionRefusedError:
        return {"status": "error", "message": "Ошибка: не удалось подключиться к серверу. Убедитесь, что сервер запущен"}
    except Exception as e:
        return {"status": "error", "message": f"Ошибка сети: {str(e)}"}

class AdminApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Tic-Tac-Toe Admin Panel")
        self.root.geometry("700x700")

        top_frame = tk.Frame(root)
        top_frame.pack(pady=10, fill=tk.X, padx=10)

        tk.Button(top_frame, text="Обновить сессии", command=self.load_sessions).pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="Список игроков", command=self.load_users).pack(side=tk.LEFT, padx=5)

        self.display = scrolledtext.ScrolledText(root, width=85, height=30)
        self.display.pack(padx=1, pady=1, fill=tk.BOTH)

        action_frame = tk.LabelFrame(root, text="Действия с игроком", padx=10, pady=15)
        action_frame.pack(fill=tk.X, padx=1, pady=30)

        input_container = tk.Frame(action_frame)
        input_container.pack(side=tk.LEFT, padx=5)

        tk.Label(input_container, text="Логин:", font=('Arial', 10)).pack(side=tk.LEFT, padx=1)
        self.login_entry = tk.Entry(input_container, width=20)
        self.login_entry.pack(side=tk.LEFT, padx=5)

        buttons_container = tk.Frame(action_frame)
        buttons_container.pack(side=tk.LEFT, padx=1)

        tk.Button(buttons_container, text="Бан", font=('Arial', 10),fg="white", bg="orange", command=lambda: self.user_action("ban"), width=10, height=2).pack(side=tk.LEFT, padx=3)
        tk.Button(buttons_container, text="Разбан", font=('Arial', 10),fg="white", bg="green", command=lambda: self.user_action("unban"), width=10, height=2).pack(side=tk.LEFT, padx=3)
        tk.Button(buttons_container, text="Удалить", font=('Arial', 10),fg="white", bg="red", command=lambda: self.user_action("delete"), width=10, height=2).pack(side=tk.LEFT, padx=3)

    def log(self, text):
        self.display.delete('1.0', tk.END)
        self.display.insert(tk.END, text)

    def load_sessions(self):
        self.display.delete('1.0', tk.END)
        res = send_admin_request({"type": "ADMIN_SESSIONS"})

        if res is None:
            messagebox.showerror("Ошибка", "Сервер не ответил")
            return

        if res.get("status") == "success":
            sessions = res.get("sessions", {})
            if not sessions:
                self.log("Активных сессий нет. (Начните игру в игровом клиенте)")
                return

            out = "АКТИВНЫЕ СЕССИИ\n"
            for room_id, state in sessions.items():
                players = state.get('players', {})
                p_str = ", ".join([f"{k}: {v}" for k, v in players.items()]) if players else "Пусто"

                out += f"\n[Комната {room_id}]\n"
                out += f"  Игроки: {p_str}\n"
                out += f"  Ходит: {state.get('currentPlayer')}\n"
                out += f"  Поле: {state.get('board')}\n"
                out += "------------------------------------------------------------------"
            self.log(out)
        else:
            messagebox.showerror("Ошибка", f"Сервер вернул: {res.get('message')}")

    def load_users(self):
        res = send_admin_request({"type": "ADMIN_USERS"})
        if res.get("status") == "success":
            users = res.get("users", {})
            out = "СПИСОК ИГРОКОВ\n\n"
            for login, data in users.items():
                status = "[BANNED]" if data.get("banned") else "[ACTIVE]"
                out += f" - {login.ljust(1)} {status}\n"
            self.log(out)
        else:
            messagebox.showerror("Ошибка", res.get("message"))

    def user_action(self, action):
        target = self.login_entry.get().strip()
        if not target:
            messagebox.showwarning("Внимание", "Введите логин игрока")
            return

        confirm = messagebox.askyesno("Подтверждение", f"Вы уверены, что хотите выполнить '{action}' для {target}?")
        if confirm:
            res = send_admin_request({"type": "ADMIN_ACTION", "action": action, "target": target})
            if res.get("status") == "success":
                messagebox.showinfo("Успех", f"Действие {action} выполнено")
                self.load_users()
            else:
                messagebox.showerror("Ошибка", res.get("message"))

if __name__ == "__main__":
    root = tk.Tk()
    app = AdminApp(root)
    root.mainloop()