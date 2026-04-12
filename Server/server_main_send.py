import socket
import json
import os
import threading
import config
import hashlib
from datetime import datetime

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

class GameSession:
    def __init__(self):
        self.board = [None] * 9
        self.current_player = 'X'
        self.winner = None
        self.is_draw = False
        self.players = {}
        self.lock = threading.Lock()
        self.moves_history = []
        self.start_time = datetime.now()

    def check_winner(self):
        lines = [[0, 1, 2], [3, 4, 5], [6, 7, 8], [0, 3, 6], [1, 4, 7], [2, 5, 8], [0, 4, 8], [2, 4, 6]]
        for a, b, c in lines:
            if self.board[a] and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        return None

    def make_move(self, index, player, login):
        if self.players.get(player) != login:
            return

        if self.winner or self.is_draw:
            return
        if self.board[index] is None and self.current_player == player:
            self.board[index] = player
            self.moves_history.append({"player": player, "login": login, "index": index, "time": datetime.now().strftime("%H:%M:%S")})
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
        return {
            "board": self.board,
            "currentPlayer": self.current_player,
            "winner": self.winner,
            "isDraw": self.is_draw,
            "players": self.players
        }


sessions = {}
sessions_lock = threading.Lock()
db_lock = threading.Lock()


def handle_client(conn, addr):
    try:
        f_obj = conn.makefile('rb')
        line = f_obj.readline()

        if not line:
            return

        req = decrypt_data(line)
        if not req:
            return

        req_type = req.get('type')

        if req_type == 'ADMIN_SESSIONS':
            with sessions_lock:
                sess_data = {k: v.get_state() for k, v in sessions.items()}
            conn.sendall(encrypt_data({"status": "success", "sessions": sess_data}))
            return

        elif req_type == 'ADMIN_USERS':
            with db_lock:
                data = {}
                if os.path.exists(config.DB_FILE):
                    with open(config.DB_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
            response = encrypt_data({"status": "success", "users": data})
            conn.sendall(response)
            return

        elif req_type == 'ADMIN_USER_STATS':
            target_login = req.get('target')
            with db_lock:
                data = {}
                if os.path.exists(config.DB_FILE):
                    with open(config.DB_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)

                if target_login in data:
                    user_data = data[target_login]
                    conn.sendall(encrypt_data({"status": "success", "user": user_data}))
                else:
                    conn.sendall(encrypt_data({"status": "error", "message": "Игрок не найден"}))
            return

        elif req_type == 'ADMIN_GAME_HISTORY':
            room_id = str(req.get('room_id'))
            with sessions_lock:
                if room_id in sessions:
                    session = sessions[room_id]
                    history = {
                        "players": session.players,
                        "movesHistory": session.moves_history,
                        "board": session.board,
                        "winner": session.winner,
                        "isDraw": session.is_draw,
                        "startTime": session.start_time.isoformat()
                    }
                    conn.sendall(encrypt_data({"status": "success", "history": history}))
                else:
                    conn.sendall(encrypt_data({"status": "error", "message": "Игра не найдена"}))
            return

        elif req_type == 'ADMIN_ACTION':
            action = req.get('action')
            target = req.get('target')
            with db_lock:
                data = {}
                if os.path.exists(config.DB_FILE):
                    with open(config.DB_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)

                if target in data:
                    if action == 'delete':
                        del data[target]
                    elif action == 'ban':
                        data[target]['banned'] = True
                    elif action == 'unban':
                        data[target]['banned'] = False

                    with open(config.DB_FILE, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=4)
                    conn.sendall(encrypt_data({"status": "success"}))
                else:
                    conn.sendall(encrypt_data({"status": "error", "message": "Игрок не найден"}))
            return

        login = req.get('login', 'Guest')

        if req.get('type') == 'AUTH':
            result = manage_db(req['login'], req['password'], req.get('photo'), "auth")
            conn.send(encrypt_data(result))
            return

        room_id = str(req.get('room_id', '1'))
        role = req.get('player')

        with sessions_lock:
            if room_id not in sessions:
                sessions[room_id] = GameSession()
                print(f"Создана новая сессия: сессия  #{room_id}  Всего активных сессий: {len(sessions)}")
            curr = sessions[room_id]

        with curr.lock:
            if role:
                if role not in curr.players:
                    curr.players[role] = login
                elif curr.players[role] != login:
                    conn.send(encrypt_data({"error": "Role occupied"}))
                    return

            if req.get('type') == 'MOVE':
                index = req.get('index')
                if index is not None:
                    curr.make_move(index, role, login)
            elif req.get('type') == 'RESET':
                curr.reset()
            elif req.get('type') == 'GET_STATE':
                pass

        encrypted_result = encrypt_data(curr.get_state())
        conn.send(encrypted_result)
    except Exception as e:
        print(f"Ошибка шифрования/обработки с {addr}: {e}")
    finally:
        conn.close()



def manage_db(login, password=None, photo=None, mode="auth"):
    with db_lock:
        data = {}
        if os.path.exists(config.DB_FILE):
            with open(config.DB_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

        if mode == "auth":
            if login not in data:
                data[login] = {"password": password, "photo": photo, "name": login, "banned": False}
                with open(config.DB_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                return {"status": "success", "user": data[login]}
            else:
                if data[login].get("banned"):
                    return {"status": "error", "message": "Аккаунт заблокирован администратором."}

                if data[login]["password"] == password:
                    return {"status": "success", "user": data[login]}
                else:
                    return {"status": "error", "message": "Неверный пароль"}


if __name__ == "__main__":
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((config.HOST, config.PORT))
    server_socket.listen(config.MAX_CONNECTIONS)

    print(f"Сервер запущен на {config.HOST}:{config.PORT}")

    while True:
        try:
            conn, addr = server_socket.accept()
            thread = threading.Thread(target=handle_client, args=(conn, addr))
            thread.daemon = True
            thread.start()
        except Exception as e:
            print(f"Ошибка сервера: {e}")