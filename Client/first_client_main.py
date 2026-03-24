import tkinter as tk
from tkinter import filedialog, messagebox
import socket
import json
from PIL import Image, ImageTk
import hashlib

HOST = '127.0.0.1'
PORT = 4000
BUFFER_SIZE = 4096

def get_password_hash(password):
    hash_object = hashlib.sha256(password.encode('utf-8'))
    return hash_object.hexdigest()


def get_auth_data():
    auth_win = tk.Tk()
    auth_win.title("Авторизация")
    auth_win.geometry("300x350")
    user_res = {"data": None}
    photo_path = tk.StringVar()

    tk.Label(auth_win, text="Логин:").pack(pady=5)
    login_e = tk.Entry(auth_win);
    login_e.pack()
    tk.Label(auth_win, text="Пароль:").pack(pady=5)
    pass_e = tk.Entry(auth_win, show="*");
    pass_e.pack()

    def select_p():
        photo_path.set(filedialog.askopenfilename())

    tk.Button(auth_win, text="Выбрать аватар", command=select_p).pack(pady=10)

    def login():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((HOST, PORT))
            hashed = get_password_hash(pass_e.get())
            s.send(json.dumps(
                {"type": "AUTH", "login": login_e.get(), "password": hashed, "photo": photo_path.get()}).encode(
                'utf-8'))
            res = json.loads(s.recv(BUFFER_SIZE).decode('utf-8'))
            if res["status"] == "success":
                user_res["data"] = res["user"]
                auth_win.destroy()
            else:
                messagebox.showerror("Ошибка", res["message"])
        except:
            messagebox.showerror("Ошибка", "Нет связи")

    tk.Button(auth_win, text="Войти / Регистрация", command=login, bg='green', fg='white').pack(pady=20)
    auth_win.mainloop()
    return user_res["data"]


class TicTacToeClient:
    def __init__(self, root, user):
        self.root = root
        self.user = user
        self.root.title("Крестики-Нолики")
        self.root.configure(bg='#1a1a1a')

        self.side = tk.Frame(root, bg='#222', width=150)
        self.side.pack(side=tk.LEFT, fill=tk.Y, padx=5)

        try:
            img = Image.open(user['photo']).resize((100, 100))
            self.img_tk = ImageTk.PhotoImage(img)
            tk.Label(self.side, image=self.img_tk, bg='#222').pack(pady=10)
        except:
            tk.Label(self.side, text="Нет фото", fg='white', bg='#444', width=12, height=5).pack(pady=10)

        tk.Label(self.side, text=user['name'], fg='white', font=('Arial', 12, 'bold'), bg='#222').pack()

        self.main = tk.Frame(root, bg='#1a1a1a')
        self.main.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        self.top = tk.Frame(self.main, bg='#333', pady=5)
        self.top.pack(fill=tk.X)
        tk.Label(self.top, text="Сессия:", fg='white', bg='#333').pack(side=tk.LEFT, padx=5)
        self.room_e = tk.Entry(self.top, width=5);
        self.room_e.insert(0, "1");
        self.room_e.pack(side=tk.LEFT)

        self.my_role = tk.StringVar(value="X")
        tk.Radiobutton(self.top, text="X", variable=self.my_role, value="X", bg='#333', fg='white',
                       selectcolor='#1a1a1a').pack(side=tk.LEFT, padx=10)
        tk.Radiobutton(self.top, text="O", variable=self.my_role, value="O", bg='#333', fg='white',
                       selectcolor='#1a1a1a').pack(side=tk.LEFT)

        self.label_p = tk.Label(self.main, text="", font=('Arial', 14), bg='#1a1a1a')
        self.label_p.pack(pady=10)

        self.grid = tk.Frame(self.main, bg='#333')
        self.grid.pack()
        self.btns = []
        for i in range(9):
            b = tk.Button(self.grid, text="", width=5, height=2, font=('Arial', 20), command=lambda i=i: self.move(i))
            b.grid(row=i // 3, column=i % 3, padx=2, pady=2)
            self.btns.append(b)

        self.status = tk.Label(self.main, text="", bg='#1a1a1a', fg='white')
        self.status.pack(pady=5)
        tk.Button(self.main, text="Сброс", command=self.reset).pack()

        self.state = {"board": [None] * 9, "currentPlayer": 'X', "winner": None, "isDraw": False}
        self.auto_update()

    def send(self, req):
        try:
            req['room_id'] = self.room_e.get()
            req['login'] = self.user['name']
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((HOST, PORT))
            s.send(json.dumps(req).encode('utf-8'))
            data = s.recv(BUFFER_SIZE).decode('utf-8')
            parsed = json.loads(data)
            if "error" not in parsed:
                self.state = parsed
                self.update_ui()
            s.close()
        except:
            pass

    def move(self, i):
        if self.state['currentPlayer'] == self.my_role.get():
            self.send({"type": "MOVE", "index": i, "player": self.my_role.get()})

    def reset(self):
        self.send({"type": "RESET"})

    def auto_update(self):
        self.send({"type": "GET_STATE"})
        self.root.after(1000, self.auto_update)

    def update_ui(self):
        for i in range(9): self.btns[i].config(text=self.state['board'][i] or "")
        me = self.my_role.get()
        self.label_p.config(text=f"Вы: {me}", fg='#818cf8' if me == 'X' else '#10b981')
        win = self.state['winner']
        if win:
            self.status.config(text="ПОБЕДА!" if win == me else "ПРОИГРЫШ", fg='green' if win == me else 'red')
        elif self.state['isDraw']:
            self.status.config(text="НИЧЬЯ", fg='gray')
        else:
            self.status.config(text="Ваш ход" if self.state['currentPlayer'] == me else "Ожидание...")


if __name__ == "__main__":
    u = get_auth_data()
    if u:
        r = tk.Tk()
        TicTacToeClient(r, u)
        r.mainloop()