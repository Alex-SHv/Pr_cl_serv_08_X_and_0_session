import socket
import json

HOST = '127.0.0.1'
PORT = 4000

class GameSession:
    def __init__(self):
        self.board = [None] * 9
        self.current_player = 'X'
        self.winner = None
        self.is_draw = False

    def check_winner(self):
        lines = [[0, 1, 2], [3, 4, 5], [6, 7, 8], [0, 3, 6], [1, 4, 7], [2, 5, 8], [0, 4, 8], [2, 4, 6]]
        for a, b, c in lines:
            if self.board[a] and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        return None

    def make_move(self, index, player):
        if self.winner or self.is_draw: return
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
        self.__init__()

    def get_state(self):
        return {"board": self.board, "currentPlayer": self.current_player,
                "winner": self.winner, "isDraw": self.is_draw}


# Массив сессий
sessions = {}

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((HOST, PORT))
server_socket.listen(5)

print(f"Сервер запущен на {HOST}:{PORT}")

while True:
    try:
        conn, addr = server_socket.accept()
        data = conn.recv(1024).decode('utf-8')
        if not data: continue

        req = json.loads(data)
        room_id = str(req.get('room_id', '1'))

        if room_id not in sessions:
            sessions[room_id] = GameSession()

        curr = sessions[room_id]

        if req['type'] == 'MOVE':
            curr.make_move(req['index'], req['player'])
        elif req['type'] == 'RESET':
            curr.reset()

        conn.send(json.dumps(curr.get_state()).encode('utf-8'))
        conn.close()
    except Exception as e:
        print(f"Ошибка: {e}")