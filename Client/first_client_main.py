import tkinter as tk
from tkinter import filedialog, messagebox
import socket
import json
from PIL import Image, ImageTk
import config
import hashlib

# Функции ширования и дешифрования.
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
        print(f"Ошибка безопасности/декодирования: {e}")
        return {"status": "error", "message": "Ошибка шифрования"}

def get_password_hash(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def get_auth_data():
    auth_win = tk.Tk()
    auth_win.title("Авторизация")
    auth_win.geometry("300x350")
    user_res = {"data": None}
    photo_path = tk.StringVar(value="")

    tk.Label(auth_win, text="Логин:").pack(pady=5)
    login_e = tk.Entry(auth_win); login_e.pack()
    tk.Label(auth_win, text="Пароль:").pack(pady=5)
    pass_e = tk.Entry(auth_win, show="*"); pass_e.pack()
    
    def select_p():
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg")])
        if path: photo_path.set(path)
    
    tk.Button(auth_win, text="Выбрать аватар", command=select_p).pack(pady=10)

    def login():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5) # Чтобы клиент не зависал вечно
            s.connect((config.HOST, config.PORT))
            
            hashed = get_password_hash(pass_e.get())
            
            # Шифруем данные перед отправкой
            payload = {
                "type": "AUTH", 
                "login": login_e.get(), 
                "password": hashed, 
                "photo": photo_path.get()
            }
            s.send(encrypt_data(payload))
            
            # Дешифруем ответ                    
            def recv_line(sock):
                buf = b""
                while True:
                    chunk = sock.recv(1)
                    if not chunk or chunk == b"\n":
                         break
                    buf += chunk
                return buf + b"\n"
            raw_res = recv_line(s)        
            res = decrypt_data(raw_res)
            
            if res.get("status") == "success":
                user_res["data"] = res["user"]
                auth_win.destroy()
            else: 
                messagebox.showerror("Ошибка", res.get("message", "Неизвестная ошибка"))
            s.close()
        except Exception as e: 
            messagebox.showerror("Ошибка", f"Нет связи с сервером: {e}")
    
    tk.Button(auth_win, text="Войти / Регистрация", command=login, bg='green', fg='white').pack(pady=20)
    auth_win.mainloop()
    return user_res["data"]

class TicTacToeClient:
    def __init__(self, root, user):
        self.root = root
        self.user = user
        self.root.title(f"Крестики-Нолики - {user['name']}")
        self.root.configure(bg='#1a1a1a')

        # Левая панель
        self.side = tk.Frame(root, bg='#222', width=150)
        self.side.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        if user.get('photo'):
            try:
                img = Image.open(user['photo']).resize((100, 100))
                self.img_tk = ImageTk.PhotoImage(img)
                tk.Label(self.side, image=self.img_tk, bg='#222').pack(pady=10)
            except: 
                tk.Label(self.side, text="Ошибка фото", fg='white', bg='#444').pack(pady=10)
        
        tk.Label(self.side, text=user['name'], fg='white', font=('Arial', 12, 'bold'), bg='#222').pack()

        # Правая панель
        self.main = tk.Frame(root, bg='#1a1a1a')
        self.main.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        self.top = tk.Frame(self.main, bg='#333', pady=5)
        self.top.pack(fill=tk.X)
        tk.Label(self.top, text="Комната:", fg='white', bg='#333').pack(side=tk.LEFT, padx=5)
        self.room_e = tk.Entry(self.top, width=5); self.room_e.insert(0, "1"); self.room_e.pack(side=tk.LEFT)
        
        self.my_role = tk.StringVar(value="X")
        tk.Radiobutton(self.top, text="X", variable=self.my_role, value="X", bg='#333', fg='white', selectcolor='#1a1a1a').pack(side=tk.LEFT, padx=10)
        tk.Radiobutton(self.top, text="O", variable=self.my_role, value="O", bg='#333', fg='white', selectcolor='#1a1a1a').pack(side=tk.LEFT)

        self.label_p = tk.Label(self.main, text="", font=('Arial', 14), bg='#1a1a1a')
        self.label_p.pack(pady=10)

        self.grid = tk.Frame(self.main, bg='#333')
        self.grid.pack()
        self.btns = []
        for i in range(9):
            b = tk.Button(self.grid, text="", width=5, height=2, font=('Arial', 20), command=lambda i=i: self.move(i))
            b.grid(row=i//3, column=i%3, padx=2, pady=2)
            self.btns.append(b)

        self.status = tk.Label(self.main, text="", bg='#1a1a1a', fg='white')
        self.status.pack(pady=5)
        tk.Button(self.main, text="Сбросить игру", command=self.reset).pack(pady=5)
        
        self.state = {"board": [None]*9, "currentPlayer": 'X', "winner": None, "isDraw": False}
        self.auto_update()

    def send(self, req):
        try:
            req['room_id'] = self.room_e.get()
            req['login'] = self.user['name']
            req['player'] = self.my_role.get() # Передаем роль во всех запросах
            
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect((config.HOST, config.PORT))
            
            # Шифруем
            s.send(encrypt_data(req))
            
            # Дешифруем            
            def recv_line(sock):
                buf = b""
                while True:
                    chunk = sock.recv(1)
                    if not chunk or chunk == b"\n":
                         break
                    buf += chunk
                return buf + b"\n"                   
            raw_data = recv_line(s)
            if raw_data:
                parsed = decrypt_data(raw_data)
                if "error" not in parsed:
                    self.state = parsed
                    self.update_ui()
                else:
                    self.status.config(text=parsed["error"], fg="orange")
            s.close()
        except Exception as e: 
            print(f"Ошибка связи: {e}")

    def move(self, i):
        # Простая проверка на стороне клиента (основная на сервере)
        if self.state.get('winner') or self.state.get('isDraw'):
            return
        self.send({"type": "MOVE", "index": i})

    def reset(self): 
        self.send({"type": "RESET"})
        
    def auto_update(self):
        self.send({"type": "GET_STATE"})
        # Обновление раз в секунду
        self.root.after(1000, self.auto_update)

    def update_ui(self):
        board = self.state.get('board', [None]*9)
        for i in range(9):
            val = board[i] or ""
            self.btns[i].config(text=val, fg="#818cf8" if val == 'X' else "#10b981")
        
        me = self.my_role.get()
        self.label_p.config(text=f"Вы играете за: {me}", fg='#818cf8' if me == 'X' else '#10b981')
        
        win = self.state.get('winner')
        if win:
            self.status.config(text=f"ПОБЕДА {win}!", fg='green' if win == me else 'red')
        elif self.state.get('isDraw'):
            self.status.config(text="НИЧЬЯ", fg='gray')
        else:
            curr = self.state.get('currentPlayer')
            self.status.config(text="Ваш ход" if curr == me else f"Ходит {curr}...")

if __name__ == "__main__":
    u = get_auth_data()
    if u:
        r = tk.Tk()
        app = TicTacToeClient(r, u)
        r.mainloop()