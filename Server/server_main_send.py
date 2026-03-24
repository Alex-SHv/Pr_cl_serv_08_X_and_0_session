import socket
import json
import os
import threading

HOST = '127.0.0.1'
PORT = 4000
DB_FILE = "users.json"
MAX_CONNECTIONS = 5
BUFFER_SIZE = 4096


class GameSession:
    # Класс одной игровую сессии
    def __init__(self):
        self.board = [None] * 9
        self.current_player = 'X'
        self.winner = None
        self.is_draw = False
        self.players = {}
        self.lock = threading.Lock()

    def check_winner(self):
        lines = [[0, 1, 2], [3, 4, 5], [6, 7, 8], [0, 3, 6], [1, 4, 7], [2, 5, 8], [0, 4, 8], [2, 4, 6]]
        for a, b, c in lines:
            if self.board[a] and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        return None

    def make_move(self, index, player, login):
        # Проверка: ходит ли тот, кто закрепился за ( х или 0)
        if self.players.get(player) != login:
            return

        if self.winner or self.is_draw:
            return
        if self.board[index] is None and self.current_player == player:
            self.board[index] = player
            winner = self.check_winner()
            if winner:
                self.winner = winner
            elif None not in self.board:
                self.is_draw = True
            else:
                self.current_player = 'O' if self.current_player == 'X' else 'X'

    def reset(self):
        self.board = [None] * 9
        self.current_player = 'X'
        self.winner = None
        self.is_draw = False

    def get_state(self):
        # Текущее состояние сессии
        return {
            "board": self.board,
            "currentPlayer": self.current_player,
            "winner": self.winner,
            "isDraw": self.is_draw,
            "players": self.players
        }


# Массив сессий
sessions = {}
sessions_lock = threading.Lock()


def handle_client(conn, addr):
    # Обрабатывает подключение от клиента
    try:
        data = conn.recv(BUFFER_SIZE).decode('utf-8')
        if not data:
            return

        req = json.loads(data)
        login = req.get('login', 'Guest')

        if req.get('type') == 'AUTH':
            result = manage_db(req['login'], req['password'], req.get('photo'), "auth")
            conn.send(json.dumps(result).encode('utf-8'))
            return

        room_id = str(req.get('room_id', '1'))
        role = req.get('player')  # 'X' или 'O'

        # Блокируем словарь сессий пока создаём новую
        with sessions_lock:
            if room_id not in sessions:
                sessions[room_id] = GameSession()
                print(f"Создана новая сессия: сессия  #{room_id}  Всего активных сессий: {len(sessions)}")
            curr = sessions[room_id]

        # Блокируем только конкретную сессию
        with curr.lock:
            if role:
                if role not in curr.players:
                    # Если роль свободна — занимаем её
                    curr.players[role] = login
                elif curr.players[role] != login:
                    # Если роль занята
                    conn.send(json.dumps({"error": "Role occupied"}).encode('utf-8'))
                    return
            if req['type'] == 'MOVE':
                curr.make_move(req['index'], role, login)
            elif req['type'] == 'RESET':
                curr.reset()
            elif req['type'] == 'GET_STATE':
                pass

            response = json.dumps(curr.get_state()).encode('utf-8')

        conn.send(response)

    except Exception as e:
        print(f"Ошибка с клиентом {addr}: {e}")
    finally:
        conn.close()


def manage_db(login, password=None, photo=None, mode="auth"):
    # Функция паттерн "свидетель" для работы с данными  (JSON )
    data = {}
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

    if mode == "auth":
        if login not in data:
            # Регистрация нового
            data[login] = {"password": password, "photo": photo, "name": login}
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            return {"status": "success", "user": data[login]}
        else:
            # Проверка пароля
            if data[login]["password"] == password:
                return {"status": "success", "user": data[login]}
            else:
                return {"status": "error", "message": "Неверный пароль"}

            # Запуск сервера


if __name__ == "__main__":
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(MAX_CONNECTIONS)

    print(f"Сервер запущен на {HOST}:{PORT}")

    while True:
        try:
            conn, addr = server_socket.accept()
            # Каждый клиент обрабатывается в отдельном потоке
            thread = threading.Thread(target=handle_client, args=(conn, addr))
            thread.daemon = True
            thread.start()
        except Exception as e:
            print(f"Ошибка сервера: {e}")