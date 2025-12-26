import tkinter as tk
from tkinter import messagebox
# ================================================================================================
# SECTION 1: GRAPH & BOARD REPRESENTATION (ADJACENCY MATRIX)
# ================================================================================================
class BoardGraph:
    """
    Represents the Peg Solitaire Board using an Adjacency Matrix.
    STRATEGY EXPLANATION:
    Instead of a simple 2D array, we map every valid hole on the board to a unique integer index (0 to N-1).
    We then construct an adjacency matrix `adj_matrix` of size NxN.
    - Representation:
      Nodes are holes on the board.
      Edges exist between nodes that are physically adjacent (distance 1).
    
    - Move Validation (Jumps):
      A move is valid if:
      1. We start at Node A (Peg exists).
      2. We jump over Node B (Peg exists).
      3. We land on Node C (Empty).
      4. A, B, and C form a straight line of adjacency: A is adj to B, B is adj to C.
      The Direction must be preserved (e.g., Row index changes by +1 twice).

    This structure separates the topological definition of the board from the game state logic.
    """
    
    """
    Adjacency matrix representation of pegsolitaire board is used here 
    because it allows for efficient checking of valid moves and jumps.
    Here each node has atmost 4 connections which make small graph as dense
    so adjacency matrix is more preferred than other representations.
    """
    """
    Layout helps as a bridge between visual board and mathematical graph
    With help of the layout we can easily build any shape of board easily
    """
    def __init__(self, version="english"):
        self.version = version
        self.nodes = [] # List of (r, c) tuples, index in this list is ID
        self.node_to_id = {} # Map (r, c) -> ID
        self.adj_matrix = [] # NxN adjacency matrix
        self.valid_jumps = [] # Pre-calculated valid jumps for efficiency
        self._build_board_layout()
        self._build_adjacency_matrix()
        self._precompute_jumps()
    def _build_board_layout(self):
        """Definitions of board shapes."""
        layout = []
        if self.version == "english":
            # Standard English 33-hole cross
            layout = [
                "  XXX  ",
                "  XXX  ",
                "XXXXXXX",
                "XXXXXXX",
                "XXXXXXX",
                "  XXX  ",
                "  XXX  "
            ]
        else: # European
            # European 37-hole circle-ish
            layout = [
                "  XXX  ",
                " XXXXX ",
                "XXXXXXX",
                "XXXXXXX",
                "XXXXXXX",
                " XXXXX ",
                "  XXX  "
            ]
        
        # Create Nodes
        for r, row_str in enumerate(layout):
            for c, char in enumerate(row_str):
                if char == 'X':
                    self.node_to_id[(r, c)] = len(self.nodes)
                    self.nodes.append((r, c))

    def _build_adjacency_matrix(self):
        """Constructs the adjacency matrix based on Manhattan distance of 1.
           Manhattan distance means measuring distance b/w 2 points on a grid 
           where we are allowed to move horizontally or vertically.
        """
        n = len(self.nodes)
        self.adj_matrix = [[0] * n for _ in range(n)]
        
        for i in range(n):
            r1, c1 = self.nodes[i]
            for j in range(i + 1, n):
                r2, c2 = self.nodes[j]
                # Check for adjacency (Up, Down, Left, Right)
                dist = abs(r1 - r2) + abs(c1 - c2)
                if dist == 1:
                    self.adj_matrix[i][j] = 1
                    self.adj_matrix[j][i] = 1
    def _precompute_jumps(self):
        """
        Pre-calculates all geometrically possible jumps to avoid doing this every frame.
        A jump is defined by a tuple of IDs: (start_id, mid_id, end_id).
        """
        n = len(self.nodes)
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)] # U, D, L, R
        
        for i in range(n):
            r, c = self.nodes[i]
            
            for dr, dc in directions:
                # Calculate potential mid and end coordinates
                mid_r, mid_c = r + dr, c + dc
                end_r, end_c = r + 2*dr, c + 2*dc
                
                # Check if these coordinates exist in our graph
                if (mid_r, mid_c) in self.node_to_id and (end_r, end_c) in self.node_to_id:
                    mid_id = self.node_to_id[(mid_r, mid_c)]
                    end_id = self.node_to_id[(end_r, end_c)]
                    
                    # Store as valid structural jump
                    self.valid_jumps.append((i, mid_id, end_id))

# =================================================================================================
# SECTION 2: GAME LOGIC & STATE MANAGEMENT
# =================================================================================================

class GameState:
    """
    Manages the dynamic state of the game (where pegs are).
    Decoupled from the GUI.
    """
    def __init__(self, graph):
        self.graph = graph
        self.pegs = [1] * len(graph.nodes) # 1 = Peg, 0 = Empty
        self.history = [] # Stack for Undo
        
        # Set initial empty hole (center usually)
        center_r, center_c = 3, 3
        if (center_r, center_c) in graph.node_to_id:
            center_id = graph.node_to_id[(center_r, center_c)]
            self.pegs[center_id] = 0

    def get_legal_moves(self):
        """
        Filters pre-computed jumps based on current peg configuration.
        Rule: Start=1, Mid=1, End=0.
        """
        moves = []
        for start, mid, end in self.graph.valid_jumps:
            if self.pegs[start] == 1 and self.pegs[mid] == 1 and self.pegs[end] == 0:
                moves.append((start, mid, end))
        return moves

    def execute_move(self, move):
        """
        Applies a move and saves history.
        move: (start_id, mid_id, end_id)
        """
        start, mid, end = move
        self.history.append(list(self.pegs)) # Deep copy state
        
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
# SECTION 3: GREEDY SOLVER (HEURISTIC AI)
# =================================================================================================

class GreedySolver:
    """
    Implements a Greedy Algorithm to find the best move.
    STRATEGY EXPLANATION:
    The solver looks 1 step ahead (greedy) to maximize a heuristic score.
    Heuristic Function H(state):
    1. Mobility: +10 points for every valid move available in the *next* state. 
       - Why? Keeping options open prevents getting stuck (very important in Peg Solitaire).
    2. Centrality: +5 points if the jump lands in the center region (3x3 box).
       - Why? Pegs in the center can reach more areas than pegs on edges.
    3. Isolation Penalty: -15 points for creating an isolated peg (peg with no neighbors).
       - Why? Isolated pegs are usually impossible to remove unless another peg comes to them.
    
    Tie-Breaking:
    If multiple moves have the same score, choose the one that moves a peg towards the center 3,3.
    """
    
    def __init__(self, game_state):
        self.game = game_state

    def get_best_move(self):
        legal_moves = self.game.get_legal_moves()
        if not legal_moves:
            return None

        best_score = -float('inf')
        best_moves = []
        
        # Save current state to restore after simulation
        original_pegs = list(self.game.pegs)

        for move in legal_moves:
            start, mid, end = move
            
            # 1. Simulate Move
            self.game.pegs[start] = 0
            self.game.pegs[mid] = 0
            self.game.pegs[end] = 1
            
            # 2. Calculate Score
            score = 0
            
            # Mobility
            next_moves = self.game.get_legal_moves()
            score += len(next_moves) * 10
            
            # Centrality (Target is center)
            end_r, end_c = self.game.graph.nodes[end]
            if 2 <= end_r <= 4 and 2 <= end_c <= 4:
                score += 5
            
            # Improved Heuristic: Check for isolated pegs?
            # (Omitted for performance speed in Python, but 'Mobility' usually covers this implicitly)
            
            if score > best_score:
                best_score = score
                best_moves = [move]
            elif score == best_score:
                best_moves.append(move)
            
            # 3. Restore State
            self.game.pegs = list(original_pegs)
            
        # Tie-breaker: Pick random or specific one from best_moves
        # We pick the first one which is usually fine
        return best_moves[0] if best_moves else None


# =================================================================================================
# SECTION 4: USER INTERFACE (TKINTER)
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

    # --- Main Menu ---

    def show_main_menu(self):
        self.clear_window()
        self.current_frame = tk.Frame(self.root, bg="#f0f0f0")
        self.current_frame.pack(fill="both", expand=True)

        tk.Label(self.current_frame, text="Peg Solitaire", font=("Helvetica", 32, "bold"), bg="#f0f0f0", fg="#333").pack(pady=50)
        
        tk.Button(self.current_frame, text="English Version", font=("Helvetica", 16), width=20,bg="#ed2b08",
                  command=lambda: self.start_game("english")).pack(pady=10)
        
        tk.Button(self.current_frame, text="European Version", font=("Helvetica", 16), width=20,bg="#0e0ee3",
                  command=lambda: self.start_game("european")).pack(pady=10)

        tk.Button(self.current_frame, text="Exit", font=("Helvetica", 16), width=20,bg="#06f516",
                  command=self.root.quit).pack(pady=30)

    # --- Game Loop & UI ---

    def start_game(self, version):
        self.clear_window()
        self.current_frame = GameFrame(self.root, version, self.show_main_menu)
        self.current_frame.pack(fill="both", expand=True)

class GameFrame(tk.Frame):
    def __init__(self, parent, version, on_back):
        super().__init__(parent, bg="#2c3e50")
        self.version = version
        self.on_back = on_back
        
        # Initialize Game Logic
        self.graph = BoardGraph(version)
        self.game = GameState(self.graph)
        self.solver = GreedySolver(self.game)
        
        # UI State
        self.selected_node = None
        self.autoplay_running = False
        
        self._setup_ui()
        self.draw_board()

    def _setup_ui(self):
        # Top Bar (Stats)
        self.top_bar = tk.Frame(self, bg="#34495e", height=50)
        self.top_bar.pack(fill="x")
        
        self.lbl_info = tk.Label(self.top_bar, text="Pegs: 32", font=("Arial", 14, "bold"), bg="#34495e", fg="white")
        self.lbl_info.pack(side="left", padx=20, pady=10)
        
        self.btn_menu = tk.Button(self.top_bar, text="Main Menu", command=self.on_exit, bg="#e74c3c", fg="white")
        self.btn_menu.pack(side="right", padx=10, pady=10)

        # Canvas for Board
        self.canvas = tk.Canvas(self, bg="#2c3e50", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=20, pady=20)
        self.canvas.bind("<Button-1>", self.on_click)

        # Bottom Bar (Controls)
        self.controls = tk.Frame(self, bg="#34495e", height=60)
        self.controls.pack(fill="x", side="bottom")

        btn_style = {"font": ("Arial", 12), "width": 10, "bg": "#ecf0f1"}
        
        tk.Button(self.controls, text="Undo", command=self.undo_move, **btn_style).pack(side="left", padx=10, pady=10)
        tk.Button(self.controls, text="Restart", command=self.restart_game, **btn_style).pack(side="left", padx=10, pady=10)
        
        tk.Frame(self.controls, width=30, bg="#34495e").pack(side="left") # Spacer
        
        tk.Button(self.controls, text="Hint", command=self.show_hint, **btn_style).pack(side="left", padx=10, pady=10)
        self.btn_auto = tk.Button(self.controls, text="Autoplay", command=self.toggle_autoplay, **btn_style)
        self.btn_auto.pack(side="left", padx=10, pady=10)

    # --- Drawing ---

    def draw_board(self):
        self.canvas.delete("all")
        
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        # Default fallback if canvas not rendered yet
        if width < 10: width = 600
        if height < 10: height = 500
            
        # Board dimensions
        rows = 7
        cols = 7
        cell_size = min(width, height) // (rows + 1)
        offset_x = (width - cols * cell_size) // 2
        offset_y = (height - rows * cell_size) // 2
        self.node_centers = {} # ID -> (x, y)
        # 1. Draw connections (optional, but shows graph structure)
        # We won't draw lines to keep it clean, but holes imply structure.

        # 2. Draw Holes/Pegs
        for idx in range(len(self.graph.nodes)):
            r, c = self.graph.nodes[idx]
            x = offset_x + c * cell_size + cell_size // 2
            y = offset_y + r * cell_size + cell_size // 2
            self.node_centers[idx] = (x, y)
            
            radius = cell_size // 3
            
            color = "#95a5a6" # Empty hole (Gray)
            outline = "#7f8c8d"
            
            if self.game.pegs[idx] == 1:
                color = "#f10f0f" # Peg (Gold)
                if idx == self.selected_node:
                    color = "#3b7ec0" # Selected (Orange)
            
            # Draw Circle
            self.canvas.create_oval(x-radius, y-radius, x+radius, y+radius, fill=color, outline=outline, width=2, tags=f"node_{idx}")

        self.lbl_info.config(text=f"Pegs Remaining: {self.game.get_peg_count()}")
        
        if self.game.is_game_over():
            self.show_game_over()
    def show_game_over(self):
        count = self.game.get_peg_count()
        msg = f"Game Over! Pegs remaining: {count}"
        if count == 1:
            msg += "\n🎉 PERFECT! YOU WON! 🎉"
        # Draw overlay
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        self.canvas.create_rectangle(0, h//2 - 40, w, h//2 + 40, fill="black", stipple="gray50")
        self.canvas.create_text(w//2, h//2, text=msg, fill="white", font=("Arial", 20, "bold"))
    # --- Interaction ---
    def on_click(self, event):
        if self.autoplay_running: return # Disable interact during autoplay
        # Find clicked node
        closest_dist = 9999
        clicked_id = -1
        for idx, (cx, cy) in self.node_centers.items():
            dist = (event.x - cx)**2 + (event.y - cy)**2
            if dist < 900: # 30px radius squared
                clicked_id = idx
                closest_dist = dist
                break
        
        if clicked_id == -1: return

        # Logic
        if self.selected_node is None:
            # Select Peg
            if self.game.pegs[clicked_id] == 1:
                self.selected_node = clicked_id
                self.draw_board()
        else:
            # Move attempt
            target_id = clicked_id
            
            if target_id == self.selected_node:
                # Deselect
                self.selected_node = None
                self.draw_board()
            elif self.game.pegs[target_id] == 0:
                # Check valid moves
                valid = False
                move_tuple = None
                
                # We need to find the Move Tuple (start, mid, end) that matches selection
                # Since graph stores valid jumps, we check them
                moves = self.game.get_legal_moves()
                for s, m, e in moves:
                    if s == self.selected_node and e == target_id:
                        valid = True
                        move_tuple = (s, m, e)
                        break
                
                if valid:
                    self.game.execute_move(move_tuple)
                    self.selected_node = None
                    self.draw_board()
                else:
                    messagebox.showwarning("Invalid Move", "You cannot jump there!")
            else:
                # Clicked another peg, switch selection
                self.selected_node = target_id
                self.draw_board()

    def undo_move(self):
        if self.game.undo():
            self.selected_node = None
            self.draw_board()

    def restart_game(self):
        self.autoplay_running = False
        self.btn_auto.config(text="Autoplay")
        self.game = GameState(self.graph)
        self.solver = GreedySolver(self.game)
        self.selected_node = None
        self.draw_board()

    def on_exit(self):
        self.autoplay_running = False
        self.on_back()

    # --- AI Features ---

    def show_hint(self):
        if self.autoplay_running: return
        move = self.solver.get_best_move()
        if move:
            start, mid, end = move
            # Highlight hint on canvas
            sx, sy = self.node_centers[start]
            ex, ey = self.node_centers[end]
            self.canvas.create_line(sx, sy, ex, ey, fill="#2ecc71", width=5, arrow=tk.LAST)
        else:
            messagebox.showinfo("Hint", "No moves available!")

    def toggle_autoplay(self):
        if self.autoplay_running:
            self.autoplay_running = False
            self.btn_auto.config(text="Autoplay")
        else:
            self.autoplay_running = True
            self.btn_auto.config(text="Stop Auto")
            self.run_autoplay_step()

    def run_autoplay_step(self):
        if not self.autoplay_running or self.game.is_game_over():
            self.autoplay_running = False
            self.btn_auto.config(text="Autoplay")
            return

        move = self.solver.get_best_move()
        if move:
            self.game.execute_move(move)
            self.draw_board()
            # Schedule next step
            self.after(500, self.run_autoplay_step)
        else:
            self.autoplay_running = False

if __name__ == "__main__":
    root = tk.Tk()
    app = PegSolitaireApp(root)
    root.mainloop()
#--------------------------------------------------------------------------------------








"""
https://medium.com/%40aksblog/peg-of-solitaire-game-busted-with-ai-c5f73466f8c3
"""
