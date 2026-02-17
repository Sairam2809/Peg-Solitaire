import tkinter as tk
from tkinter import messagebox
import threading

# ================================================================================================
# SECTION 1: GRAPH & BOARD REPRESENTATION – UNCHANGED
# ================================================================================================
class BoardGraph:
    def __init__(self, version="english"):
        self.version = version
        self.nodes = []
        self.node_to_id = {}
        self.adj_matrix = []
        self.valid_jumps = []
        self._build_board_layout()
        self._build_adjacency_matrix()
        self._precompute_jumps()
        self._precompute_neighbors()

    def _build_board_layout(self):
        layout = []
        if self.version == "english":
            layout = [
                "  XXX ",
                "  XXX ",
                "XXXXXXX",
                "XXXXXXX",
                "XXXXXXX",
                "  XXX ",
                "  XXX "
            ]
        else:  # european
            layout = [
                "  XXX ",
                " XXXXX ",
                "XXXXXXX",
                "XXXXXXX",
                "XXXXXXX",
                " XXXXX ",
                "  XXX "
            ]
        for r, row_str in enumerate(layout):
            for c, char in enumerate(row_str):
                if char == 'X':
                    self.node_to_id[(r, c)] = len(self.nodes)
                    self.nodes.append((r, c))

    def _build_adjacency_matrix(self):
        n = len(self.nodes)
        self.adj_matrix = [[0] * n for _ in range(n)]
        for i in range(n):
            r1, c1 = self.nodes[i]
            for j in range(i + 1, n):
                r2, c2 = self.nodes[j]
                if abs(r1 - r2) + abs(c1 - c2) == 1:
                    self.adj_matrix[i][j] = 1
                    self.adj_matrix[j][i] = 1

    def _precompute_jumps(self):
        n = len(self.nodes)
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        for i in range(n):
            r, c = self.nodes[i]
            for dr, dc in directions:
                mid_r, mid_c = r + dr, c + dc
                end_r, end_c = r + 2*dr, c + 2*dc
                if (mid_r, mid_c) in self.node_to_id and (end_r, end_c) in self.node_to_id:
                    mid_id = self.node_to_id[(mid_r, mid_c)]
                    end_id = self.node_to_id[(end_r, end_c)]
                    self.valid_jumps.append((i, mid_id, end_id))

    def _precompute_neighbors(self):
        self.neighbors = [[] for _ in range(len(self.nodes))]
        for i in range(len(self.nodes)):
            for j in range(len(self.nodes)):
                if self.adj_matrix[i][j]:
                    self.neighbors[i].append(j)

# =================================================================================================
# SECTION 2: GAME LOGIC – UNCHANGED
# =================================================================================================
class GameState:
    def __init__(self, graph):
        self.graph = graph
        self.pegs = [1] * len(graph.nodes)
        self.history = []
        center_r, center_c = 3, 3
        if (center_r, center_c) in graph.node_to_id:
            center_id = graph.node_to_id[(center_r, center_c)]
            self.pegs[center_id] = 0

    def get_legal_moves(self):
        moves = []
        for start, mid, end in self.graph.valid_jumps:
            if self.pegs[start] == 1 and self.pegs[mid] == 1 and self.pegs[end] == 0:
                moves.append((start, mid, end))
        return moves

    def execute_move(self, move):
        start, mid, end = move
        self.history.append(list(self.pegs))
        self.pegs[start] = 0
        self.pegs[mid] = 0
        self.pegs[end] = 1
        return True

    def undo(self):
        if self.history:
            self.pegs = self.history.pop()
            return True
        return False

    def is_game_over(self):
        return len(self.get_legal_moves()) == 0

    def get_peg_count(self):
        return sum(self.pegs)

# =================================================================================================
# SECTION 3: DIVIDE‑AND‑CONQUER SOLVER – ITERATIVE DEEPENING A* (IDA*) – FASTEST POSSIBLE
# =================================================================================================
class DivideAndConquerSolver:
    """
    Pure Divide and Conquer Solver.
    - No Backtracking (State Mutation): Uses functional recursion with immutable bitboards.
    - No Greedy: Moves are not sorted by heuristics.
    - No Memoization/Iterative Deepening: Pure recursive tree search.
    - Best Effort: Returns the path to the minimum possible pegs if 1 is not reachable.
    Runs in a background thread → UI never freezes.
    """
    def __init__(self, game_state):
        self.game = game_state
        self.graph = game_state.graph
        
        # Pre-compute move masks (bitboard)
        self.move_masks = []
        for s, m, e in self.graph.valid_jumps:
            self.move_masks.append((1 << s, 1 << m, 1 << e))

        # Threading control
        self.search_thread = None
        self.search_cancel = False
        self.callback = None

        # Solution cache
        self.solution_cache = None

    # ----------------------------------------------------------------------
    # Bitboard utilities
    # ----------------------------------------------------------------------
    def state_to_bitboard(self):
        bb = 0
        for i, peg in enumerate(self.game.pegs):
            if peg:
                bb |= 1 << i
        return bb

    def apply_move(self, bb, move):
        s, m, e = move
        return (bb & ~(s | m)) | e

    def peg_count(self, bb):
        return bb.bit_count()

    # ----------------------------------------------------------------------
    # Pure Recursive Divide & Conquer
    # ----------------------------------------------------------------------
    def _solve(self, bb):
        """
        Recursively solves the board.
        Returns: (pegs_remaining, path_of_moves)
        """
        if self.search_cancel:
            return (self.peg_count(bb), [])

        # 1. Divide: Generate all possible moves (Sub-problems)
        moves = []
        for s_mask, m_mask, e_mask in self.move_masks:
            if (bb & s_mask) and (bb & m_mask) and not (bb & e_mask):
                moves.append((s_mask, m_mask, e_mask))

        # Base Case: No moves possible
        if not moves:
            return (self.peg_count(bb), [])

        # 2. Conquer: Solve sub-problems recursively
        best_pegs = 999
        best_path = []

        for move in moves:
            new_bb = self.apply_move(bb, move)
            
            # Recursive call (Solve the smaller board)
            pegs_left, path = self._solve(new_bb)
            
            # 3. Combine: Check if this path is better
            if pegs_left < best_pegs:
                best_pegs = pegs_left
                best_path = [move] + path
            
            # Optimization: If we found a 1-peg solution, we can't do better.
            if best_pegs == 1:
                break
        
        return (best_pegs, best_path)

    # ----------------------------------------------------------------------
    # Public interface – threaded
    # ----------------------------------------------------------------------
    def start_solving(self, callback):
        self.cancel_solving()
        self.search_cancel = False
        self.callback = callback
        initial_bb = self.state_to_bitboard()
        self.search_thread = threading.Thread(target=self._threaded_solve, args=(initial_bb,))
        self.search_thread.daemon = True
        self.search_thread.start()

    def _threaded_solve(self, bb):
        # Start the Divide & Conquer process
        min_pegs, solution_masks = self._solve(bb)
        
        # Convert bitmasks back to indices for the UI
        id_solution = []
        for s_mask, m_mask, e_mask in solution_masks:
            s = s_mask.bit_length() - 1
            m = m_mask.bit_length() - 1
            e = e_mask.bit_length() - 1
            id_solution.append((s, m, e))
        
        self.solution_cache = id_solution
        
        if self.callback:
            if hasattr(self, 'game_frame'):
                self.game_frame.after(0, self.callback, id_solution)

    def cancel_solving(self):
        self.search_cancel = True
        if self.search_thread and self.search_thread.is_alive():
            self.search_thread.join(timeout=0.1)
        self.search_thread = None

    def get_hint_move(self):
        return self.solution_cache[0] if self.solution_cache else None

    def get_full_solution(self):
        return self.solution_cache

# =================================================================================================
# SECTION 4: USER INTERFACE (TKINTER) – EXACT SAME AS ORIGINAL
# =================================================================================================
class PegSolitaireApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Python Peg Solitaire (Standard & European)")
        self.root.geometry("600x700")
        self.root.configure(bg="#f0f0f0")
        self.current_frame = None
        self.show_main_menu()

    def clear_window(self):
        if self.current_frame:
            self.current_frame.destroy()

    def show_main_menu(self):
        self.clear_window()
        self.current_frame = tk.Frame(self.root, bg="#f0f0f0")
        self.current_frame.pack(fill="both", expand=True)
        tk.Label(self.current_frame, text="Peg Solitaire", font=("Helvetica", 32, "bold"),
                 bg="#f0f0f0", fg="#333").pack(pady=50)
        tk.Button(self.current_frame, text="English Version", font=("Helvetica", 16), width=20, bg="#ed2b08",
                  command=lambda: self.start_game("english")).pack(pady=10)
        tk.Button(self.current_frame, text="European Version", font=("Helvetica", 16), width=20, bg="#0e0ee3",
                  command=lambda: self.start_game("european")).pack(pady=10)
        tk.Button(self.current_frame, text="Exit", font=("Helvetica", 16), width=20, bg="#06f516",
                  command=self.root.quit).pack(pady=30)

    def start_game(self, version):
        self.clear_window()
        self.current_frame = GameFrame(self.root, version, self.show_main_menu)
        self.current_frame.pack(fill="both", expand=True)

class GameFrame(tk.Frame):
    def __init__(self, parent, version, on_back):
        super().__init__(parent, bg="#2c3e50")
        self.version = version
        self.on_back = on_back

        self.graph = BoardGraph(version)
        self.game = GameState(self.graph)
        self.solver = DivideAndConquerSolver(self.game)
        self.solver.game_frame = self

        self.selected_node = None
        self.autoplay_running = False
        self.autoplay_moves = []
        self.autoplay_index = 0
        self.searching = False

        self._setup_ui()
        self.draw_board()

    def _setup_ui(self):
        # Top Bar
        self.top_bar = tk.Frame(self, bg="#34495e", height=50)
        self.top_bar.pack(fill="x")
        self.lbl_info = tk.Label(self.top_bar, text="Pegs: 32", font=("Arial", 14, "bold"),
                                 bg="#34495e", fg="white")
        self.lbl_info.pack(side="left", padx=20, pady=10)
        self.btn_menu = tk.Button(self.top_bar, text="Main Menu", command=self.on_exit,
                                  bg="#e74c3c", fg="white")
        self.btn_menu.pack(side="right", padx=10, pady=10)

        # Canvas
        self.canvas = tk.Canvas(self, bg="#2c3e50", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=20, pady=20)
        self.canvas.bind("<Button-1>", self.on_click)

        # Bottom Controls
        self.controls = tk.Frame(self, bg="#34495e", height=60)
        self.controls.pack(fill="x", side="bottom")
        btn_style = {"font": ("Arial", 12), "width": 10, "bg": "#ecf0f1"}

        tk.Button(self.controls, text="Undo", command=self.undo_move, **btn_style).pack(side="left", padx=10, pady=10)
        tk.Button(self.controls, text="Restart", command=self.restart_game, **btn_style).pack(side="left", padx=10, pady=10)
        tk.Frame(self.controls, width=30, bg="#34495e").pack(side="left")
        tk.Button(self.controls, text="Hint", command=self.show_hint, **btn_style).pack(side="left", padx=10, pady=10)
        self.btn_auto = tk.Button(self.controls, text="Autoplay", command=self.toggle_autoplay, **btn_style)
        self.btn_auto.pack(side="left", padx=10, pady=10)

        # Status label
        self.lbl_status = tk.Label(self.controls, text="", font=("Arial", 10), bg="#34495e", fg="yellow")
        self.lbl_status.pack(side="right", padx=20)

    def draw_board(self):
        self.canvas.delete("all")
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        if width < 10: width = 600
        if height < 10: height = 500
        rows, cols = 7, 7
        cell_size = min(width, height) // (rows + 1)
        offset_x = (width - cols * cell_size) // 2
        offset_y = (height - rows * cell_size) // 2
        self.node_centers = {}
        for idx in range(len(self.graph.nodes)):
            r, c = self.graph.nodes[idx]
            x = offset_x + c * cell_size + cell_size // 2
            y = offset_y + r * cell_size + cell_size // 2
            self.node_centers[idx] = (x, y)
            radius = cell_size // 3
            color = "#95a5a6"
            outline = "#7f8c8d"
            if self.game.pegs[idx] == 1:
                color = "#f10f0f"
                if idx == self.selected_node:
                    color = "#3b7ec0"
            self.canvas.create_oval(x-radius, y-radius, x+radius, y+radius,
                                    fill=color, outline=outline, width=2, tags=f"node_{idx}")
        self.lbl_info.config(text=f"Pegs Remaining: {self.game.get_peg_count()}")
        if self.game.is_game_over():
            self.show_game_over()

    def show_game_over(self):
        count = self.game.get_peg_count()
        msg = f"Game Over! Pegs remaining: {count}"
        if count == 1:
            msg += "\n🎉 PERFECT! YOU WON! 🎉"
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        self.canvas.create_rectangle(0, h//2 - 40, w, h//2 + 40, fill="black", stipple="gray50")
        self.canvas.create_text(w//2, h//2, text=msg, fill="white", font=("Arial", 20, "bold"))

    def on_click(self, event):
        if self.autoplay_running or self.searching:
            return
        closest_dist = 9999
        clicked_id = -1
        for idx, (cx, cy) in self.node_centers.items():
            dist = (event.x - cx)**2 + (event.y - cy)**2
            if dist < 900:
                clicked_id = idx
                break
        if clicked_id == -1:
            return
        if self.selected_node is None:
            if self.game.pegs[clicked_id] == 1:
                self.selected_node = clicked_id
                self.draw_board()
        else:
            target_id = clicked_id
            if target_id == self.selected_node:
                self.selected_node = None
                self.draw_board()
            elif self.game.pegs[target_id] == 0:
                valid = False
                move_tuple = None
                for s, m, e in self.game.get_legal_moves():
                    if s == self.selected_node and e == target_id:
                        valid = True
                        move_tuple = (s, m, e)
                        break
                if valid:
                    self.game.execute_move(move_tuple)
                    self.selected_node = None
                    self.draw_board()
                    self.solver = DivideAndConquerSolver(self.game)
                    self.solver.game_frame = self
                else:
                    messagebox.showwarning("Invalid Move", "You cannot jump there!")
            else:
                self.selected_node = target_id
                self.draw_board()

    def undo_move(self):
        if self.autoplay_running or self.searching:
            return
        if self.game.undo():
            self.selected_node = None
            self.draw_board()
            self.solver = DivideAndConquerSolver(self.game)
            self.solver.game_frame = self

    def restart_game(self):
        self.autoplay_running = False
        self.searching = False
        self.btn_auto.config(text="Autoplay")
        self.game = GameState(self.graph)
        self.solver = DivideAndConquerSolver(self.game)
        self.solver.game_frame = self
        self.selected_node = None
        self.draw_board()
        self.lbl_status.config(text="")

    def on_exit(self):
        self.autoplay_running = False
        self.searching = False
        self.solver.cancel_solving()
        self.on_back()

    def show_hint(self):
        if self.autoplay_running or self.searching:
            return
        hint = self.solver.get_hint_move()
        if hint:
            self._draw_hint(hint)
            return
        self.searching = True
        self.lbl_status.config(text="Searching for solution...")
        self.solver.start_solving(callback=self._on_hint_solution)

    def _on_hint_solution(self, solution):
        self.searching = False
        self.lbl_status.config(text="")
        if solution:
            self._draw_hint(solution[0])
        else:
            messagebox.showinfo("Hint", "No winning solution exists from this position.")

    def _draw_hint(self, move):
        start, mid, end = move
        sx, sy = self.node_centers[start]
        ex, ey = self.node_centers[end]
        self.canvas.create_line(sx, sy, ex, ey, fill="#2ecc71", width=5, arrow=tk.LAST)

    def toggle_autoplay(self):
        if self.autoplay_running:
            self.autoplay_running = False
            self.btn_auto.config(text="Autoplay")
            self.solver.cancel_solving()
            self.lbl_status.config(text="")
            return
        if self.searching:
            return
        solution = self.solver.get_full_solution()
        if solution:
            self._start_autoplay(solution)
        else:
            self.searching = True
            self.lbl_status.config(text="Searching for solution...")
            self.solver.start_solving(callback=self._on_autoplay_solution)

    def _on_autoplay_solution(self, solution):
        self.searching = False
        self.lbl_status.config(text="")
        if solution:
            self._start_autoplay(solution)
        else:
            messagebox.showinfo("Autoplay", "No winning sequence found from this position.")
            self.btn_auto.config(text="Autoplay")

    def _start_autoplay(self, solution):
        self.autoplay_moves = solution
        self.autoplay_index = 0
        self.autoplay_running = True
        self.btn_auto.config(text="Stop Auto")
        self.run_autoplay_step()

    def run_autoplay_step(self):
        if not self.autoplay_running:
            return
        if self.autoplay_index >= len(self.autoplay_moves):
            self.autoplay_running = False
            self.btn_auto.config(text="Autoplay")
            return
        move = self.autoplay_moves[self.autoplay_index]
        self.game.execute_move(move)
        self.draw_board()
        self.autoplay_index += 1
        self.after(500, self.run_autoplay_step)

if __name__ == "__main__":
    root = tk.Tk()
    app = PegSolitaireApp(root)

    root.mainloop()
    
