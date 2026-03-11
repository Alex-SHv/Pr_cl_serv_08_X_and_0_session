import tkinter as tk
import socket
import json

HOST = '127.0.0.1'
PORT = 4000

class TicTacToeClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Крестики-Нолики")
        self.root.configure(bg='#1a1a1a')

        self.top_panel = tk.Frame(root, bg='#222', pady=5)
        self.top_panel.pack(fill=tk.X)

        tk.Label(self.top_panel, text="Сессия :", fg='white', bg='#222').pack(side=tk.LEFT, padx=5)
        self.room_entry = tk.Entry(self.top_panel, width=5)
        self.room_entry.insert(0, "1")
        self.room_entry.pack(side=tk.LEFT)

        tk.Label(self.top_panel, text="Моя роль:", fg='white', bg='#222').pack(side=tk.LEFT, padx=5)
        self.my_role = tk.StringVar(value="X")
        tk.Radiobutton(self.top_panel, text="X", variable=self.my_role, value="X",
               bg='#222', fg='white', selectcolor='#444').pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(self.top_panel, text="O", variable=self.my_role, value="O",
               bg='#222', fg='white', selectcolor='#444').pack(side=tk.LEFT, padx=5)

        self.state = {"board": [None]*9, "currentPlayer": 'X', "winner": None, "isDraw": False}

        self.label_player = tk.Label(root, text="", font=('Arial', 14, 'bold'), bg='#1a1a1a')
        self.label_player.pack(pady=10)

        self.canvas = tk.Frame(root, bg='#333')
        self.canvas.pack(pady=10)
        self.buttons = []
        for i in range(9):
            btn = tk.Button(self.canvas, text="", width=5, height=2, font=('Arial', 20, 'bold'), command=lambda i=i: self.make_move(i))
            btn.grid(row=i//3, column=i%3, padx=2, pady=2)
            self.buttons.append(btn)

        self.status_label = tk.Label(root, text="", fg='white', bg='#1a1a1a', font=('Arial', 12))
        self.status_label.pack()

        tk.Button(root, text="Перезапустить игру", command=self.reset_game).pack(pady=10)

        self.auto_update()

    def send_request(self, request):
        try:
            request['room_id'] = self.room_entry.get()
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.settimeout(0.5)
            client.connect((HOST, PORT))
            client.send(json.dumps(request).encode('utf-8'))
            data = client.recv(1024).decode('utf-8')
            client.close()
            if data:
                self.state = json.loads(data)
                self.update_ui()
        except:
            pass

    def make_move(self, index):
        role = self.my_role.get()
        if self.state['currentPlayer'] == role:
            self.send_request({"type": "MOVE", "index": index, "player": role})

    def auto_update(self):
        self.send_request({"type": "GET_STATE"})
        self.root.after(1000, self.auto_update)

    def reset_game(self):
        self.send_request({"type": "RESET"})

    def update_ui(self):
        board = self.state['board']
        winner = self.state['winner']
        me = self.my_role.get()

        for i in range(9):
            self.buttons[i].config(text=board[i] if board[i] else "")

        color = '#818cf8' if me == 'X' else '#10b981'
        self.label_player.config(text=f"Игрок: {me}", fg=color)

        if winner:
            if winner == me:
                self.status_label.config(text="Ты победил", fg='#10b981')
            else:
                self.status_label.config(text="Ты проиграл", fg='#ef4444')
        elif self.state['isDraw']:
            self.status_label.config(text="Ничья", fg='gray')
        else:
            if self.state['currentPlayer'] == me:
                self.status_label.config(text="Твой ход", fg='white')
            else:
                self.status_label.config(text="Жди хода...", fg='gray')

if __name__ == "__main__":
    root = tk.Tk()
    app = TicTacToeClient(root)
    root.mainloop()