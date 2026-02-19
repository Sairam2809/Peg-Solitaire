import tkinter as tk
from tkinter import messagebox, ttk
import threading
import time


# BoardGraph 
# ======================================================================
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

    def _build_board_layout(self):
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
        self.adj_matrix = [[0]*n for _ in range(n)]
        for i in range(n):
            r1, c1 = self.nodes[i]
            for j in range(i+1, n):
                r2, c2 = self.nodes[j]
                if abs(r1-r2)+abs(c1-c2) == 1:
                    self.adj_matrix[i][j] = 1
                    self.adj_matrix[j][i] = 1

    def _precompute_jumps(self):
        n = len(self.nodes)
        directions = [(-1,0),(1,0),(0,-1),(0,1)]
        for i in range(n):
            r,c = self.nodes[i]
            for dr,dc in directions:
                mr,mc = r+dr, c+dc
                er,ec = r+2*dr, c+2*dc
                if (mr,mc) in self.node_to_id and (er,ec) in self.node_to_id:
                    self.valid_jumps.append((i, self.node_to_id[(mr,mc)], self.node_to_id[(er,ec)]))

# ======================================================================
# GameState 
# ======================================================================
class GameState:
    def __init__(self, graph):
        self.graph = graph
        self.pegs = [1]*len(graph.nodes)
        self.history = []
        centre = (3,3)
        if centre in graph.node_to_id:
            self.pegs[graph.node_to_id[centre]] = 0

    def get_legal_moves(self):
        moves = []
        for s,m,e in self.graph.valid_jumps:
            if self.pegs[s]==1 and self.pegs[m]==1 and self.pegs[e]==0:
                moves.append((s,m,e))
        return moves

    def execute_move(self, move):
        s,m,e = move
        self.history.append(self.pegs[:])
        self.pegs[s]=0; self.pegs[m]=0; self.pegs[e]=1

    def undo(self):
        if self.history:
            self.pegs = self.history.pop()
            return True
        return False

    def get_peg_count(self):
        return sum(self.pegs)

    def is_game_over(self):
        return len(self.get_legal_moves()) == 0


# ======================================================================
# Inplace Quick Sort Implementation
# ======================================================================
def quicksort(arr, key=lambda x: x):
    """In-place quicksort with key function support"""
    def _partition(low, high):
        pivot = key(arr[high])
        i = low - 1
        for j in range(low, high):
            if key(arr[j]) <= pivot:
                i += 1
                arr[i], arr[j] = arr[j], arr[i]
        arr[i+1], arr[high] = arr[high], arr[i+1]
        return i + 1

    def _quicksort(low, high):
        if low < high:
            pi = _partition(low, high)
            _quicksort(low, pi - 1)
            _quicksort(pi + 1, high)

    _quicksort(0, len(arr) - 1)
    return arr   # for chaining convenience (though we sort in-place)

# ======================================================================
# DIVIDE‑AND‑CONQUER 
# ======================================================================
class RegionShrinkingDCSolver:
    """
    Region Shrinking / Central Expansion Solver (Divide & Conquer).

    Strategy:
      - Inherits the Divide & Conquer structure (Spatial Splitting).
      - Enhances the 'Conquer' and 'Combine' phases with a Priority Heuristic.
      - PRIORITY: Linearly scan for valid moves, but execute them in an order
                  that effectively 'shrinks' the board from the outside in.
                  Priority = Distance of the removed peg (middle peg) from center.
                  Outer pegs are removed first.

    Algorithm:
      1. DIVIDE  : Partition the board spatially into two halves.
      2. CONQUER : Recursively process each half.
                   In base cases (small regions), moves are executed based on Priority.
      3. COMBINE : Execute cross-boundary moves, also sorted by Priority.

    No undo() is ever called (No Backtracking).
    """

    def __init__(self, game_state):
        self.game = game_state
        self.solution_cache = None
        self.search_thread = None
        self.search_cancel = False
        self.callback = None

    # ---- threading helpers ------------------------------------------------
    def start_solving(self, callback):
        """Run the D&C search in a background thread."""
        self.cancel_solving()
        self.search_cancel = False
        self.callback = callback
        self.search_thread = threading.Thread(target=self._threaded_search)
        self.search_thread.daemon = True
        self.search_thread.start()

    def _threaded_search(self):
        pegs = self.game.pegs[:]
        all_nodes = list(range(len(self.game.graph.nodes)))
        solution = self._solve_dc(all_nodes, pegs, split_by_row=True)
        if self.search_cancel:
            solution = None
        if self.callback:
            self.game_frame.after(0, self.callback, solution if solution else None)

    # ----  divide & conquer -------------------------------------------
    def _solve_dc(self, node_indices, pegs, split_by_row=True):
        """
        D&C entry point.

        Args:
            node_indices : list of node IDs in the current region
            pegs         : mutable list[int] of peg states (0/1)
            split_by_row : True → split by row; False → by column

        Returns:
            List of (start, mid, end) move tuples that were executed.
        """
        if self.search_cancel:
            return []

        # ── BASE CASE ──────────────────────────────────────────────
        # Region is too small to sub-divide: greedily execute moves BY PRIORITY.
        if len(node_indices) <= 3:
            return self._solve_small_region_priority(node_indices, pegs)

        # ── DIVIDE ─────────────────────────────────────────────────
        # Split the region spatially into two halves.
        left_half, right_half = self._spatial_split(node_indices, split_by_row)

        # ── CONQUER ────────────────────────────────────────────────
        # Recursively solve each sub-region (alternate the split axis).
        left_moves  = self._solve_dc(left_half,  pegs, not split_by_row)
        right_moves = self._solve_dc(right_half, pegs, not split_by_row)

        # ── COMBINE ────────────────────────────────────────────────
        # Execute cross-boundary moves between the two halves BY PRIORITY.
        cross_moves = self._execute_cross_boundary_moves_priority(
            left_half, right_half, pegs
        )

        return left_moves + right_moves + cross_moves

    # ---- Region Shrinking Heuristics --------------------------------------
    def _get_move_priority(self, move):
        """
        Calculate priority for a move (s, m, e).
        Higher priority = removing pegs further from center (Region Shrinking).
        Center is approx (3,3).
        """
        s, m, e = move
        # Get coordinates of the middle peg (the one being removed)
        r_m, c_m = self.game.graph.nodes[m]
        # Get coordinates of the start peg (the one moving)
        r_s, c_s = self.game.graph.nodes[s]
        
        # Distance from center (3,3)
        dist_m = abs(r_m - 3) + abs(c_m - 3)
        dist_s = abs(r_s - 3) + abs(c_s - 3)

        # Priority:
        # 1. Primary: Distance of removed peg (m). Remove outer pegs first!
        # 2. Secondary: Distance of start peg (s). Move outer pegs inward!
        return (dist_m * 10) + dist_s

    def _solve_small_region_priority(self, node_indices, pegs):
        """Greedily execute moves in region, prioritizing Region Shrinking."""
        region_set = set(node_indices)
        moves_made = []
        changed = True
        
        while changed:
            changed = False
            candidate_moves = []

            # 1. Collect all legal moves entirely within this region
            for s, m, e in self.game.graph.valid_jumps:
                if s in region_set and m in region_set and e in region_set:
                    if pegs[s] == 1 and pegs[m] == 1 and pegs[e] == 0:
                        priority = self._get_move_priority((s, m, e))
                        candidate_moves.append((priority, (s, m, e)))
            
            # 2. Sort by priority (descending)
            quicksort(candidate_moves, key=lambda x: x[0])
            candidate_moves.reverse()

            # 3. Execute the best move
            if candidate_moves:
                _, best_move = candidate_moves[0]
                s, m, e = best_move
                pegs[s] = 0; pegs[m] = 0; pegs[e] = 1
                moves_made.append((s, m, e))
                changed = True

        return moves_made

    def _execute_cross_boundary_moves_priority(self, left, right, pegs):
        """Execute cross-boundary moves, prioritizing Region Shrinking."""
        left_set  = set(left)
        right_set = set(right)
        all_set   = left_set | right_set
        moves_made = []
        changed = True

        while changed:
            changed = False
            candidate_moves = []

            # 1. Collect all legal moves spanning the boundary
            for s, m, e in self.game.graph.valid_jumps:
                if s in all_set and m in all_set and e in all_set:
                    involved = {s, m, e}
                    if involved & left_set and involved & right_set:
                        if pegs[s] == 1 and pegs[m] == 1 and pegs[e] == 0:
                            priority = self._get_move_priority((s, m, e))
                            candidate_moves.append((priority, (s, m, e)))

            # 2. Sort by priority (descending)
            quicksort(candidate_moves, key=lambda x: x[0])
            candidate_moves.reverse()   # descending order

            # 3. Execute the best move
            if candidate_moves:
                _, best_move = candidate_moves[0]
                s, m, e = best_move
                pegs[s] = 0; pegs[m] = 0; pegs[e] = 1
                moves_made.append((s, m, e))
                changed = True
                
        return moves_made

    # ---- helpers ----------------------------------------------------------
    def _spatial_split(self, node_indices, by_row):
        """Split nodes into two halves based on spatial position."""
        key = ((lambda i: self.game.graph.nodes[i][0]) if by_row
               else (lambda i: self.game.graph.nodes[i][1]))
        sorted_nodes = sorted(node_indices, key=key)
        mid = len(sorted_nodes) // 2
        return sorted_nodes[:mid], sorted_nodes[mid:]

    def cancel_solving(self):
        self.search_cancel = True
        if self.search_thread and self.search_thread.is_alive():
            self.search_thread.join(timeout=0.1)
        self.search_thread = None

    def get_hint_move(self):
        return self.solution_cache[0] if self.solution_cache else None

    def get_full_solution(self):
        return self.solution_cache

# ======================================================================
# UI – FIXED VERSION with Responsive Layout
# ======================================================================
class PegSolitaireApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Peg Solitaire")
        self.root.geometry("800x900")  # Increased window size
        self.root.minsize(700, 800)    # Set minimum window size
        self.root.configure(bg="#1a2634")
        
        # Set modern color scheme
        self.colors = {
            'bg': '#1a2634',
            'primary': '#2c3e50',
            'secondary': '#34495e',
            'accent1': '#e74c3c',
            'accent2': '#3498db',
            'accent3': '#2ecc71',
            'text': '#ecf0f1',
            'highlight': '#f1c40f'
        }
        
        self.current_frame = None
        self.show_main_menu()

    def clear_window(self):
        if self.current_frame:
            self.current_frame.destroy()

    def show_main_menu(self):
        self.clear_window()
        self.current_frame = tk.Frame(self.root, bg=self.colors['bg'])
        self.current_frame.pack(fill="both", expand=True)
        
        # Header with decorative line
        header_frame = tk.Frame(self.current_frame, bg=self.colors['bg'])
        header_frame.pack(pady=50)
        
        tk.Label(header_frame, text="♟️ PEG SOLITAIRE ♟️", 
                font=("Helvetica", 36, "bold"),
                bg=self.colors['bg'], fg=self.colors['accent3']).pack()
        
        tk.Frame(header_frame, height=2, width=400, bg=self.colors['accent1']).pack(pady=20)
        
        tk.Label(header_frame, text="Region Shrinking Strategy", 
                font=("Helvetica", 18, "italic"),
                bg=self.colors['bg'], fg=self.colors['highlight']).pack()
        
        # Button frame
        btn_frame = tk.Frame(self.current_frame, bg=self.colors['bg'])
        btn_frame.pack(pady=40)
        
        # Style for buttons
        btn_style = {
            "font": ("Helvetica", 16, "bold"),
            "width": 25,
            "height": 2,
            "bd": 0,
            "cursor": "hand2"
        }
        
        english_btn = tk.Button(btn_frame, text="🇬🇧 ENGLISH VERSION", 
                               bg=self.colors['accent1'], fg="white",
                               activebackground="#c0392b", activeforeground="white",
                               command=lambda: self.start_game("english"), **btn_style)
        english_btn.pack(pady=10)
        
        european_btn = tk.Button(btn_frame, text="🇪🇺 EUROPEAN VERSION", 
                                bg=self.colors['accent2'], fg="white",
                                activebackground="#2980b9", activeforeground="white",
                                command=lambda: self.start_game("european"), **btn_style)
        european_btn.pack(pady=10)
        
        exit_btn = tk.Button(btn_frame, text="✖️ EXIT", 
                            bg=self.colors['accent3'], fg="white",
                            activebackground="#27ae60", activeforeground="white",
                            command=self.root.quit, **btn_style)
        exit_btn.pack(pady=10)
        
        # Footer
        tk.Label(self.current_frame, text="Divide & Conquer ", 
                font=("Helvetica", 10), bg=self.colors['bg'], fg=self.colors['text']).pack(side="bottom", pady=20)

    def start_game(self, version):
        self.clear_window()
        self.current_frame = GameFrame(self.root, version, self.show_main_menu, self.colors)
        self.current_frame.pack(fill="both", expand=True)

class GameFrame(tk.Frame):
    def __init__(self, parent, version, on_back, colors):
        super().__init__(parent, bg=colors['bg'])
        self.version = version
        self.on_back = on_back
        self.colors = colors

        self.graph = BoardGraph(version)
        self.game = GameState(self.graph)
        self.solver = RegionShrinkingDCSolver(self.game)
        self.solver.game_frame = self

        self.selected_node = None
        self.autoplay_running = False
        self.autoplay_moves = []
        self.autoplay_index = 0
        self.searching = False
        
        # Animation variables
        self.hint_line = None
        self.last_move = None

        # Configure grid weights for responsive layout
        self.grid_rowconfigure(0, weight=0)  # Top bar
        self.grid_rowconfigure(1, weight=1)  # Canvas (expandable)
        self.grid_rowconfigure(2, weight=0)  # Strategy panel
        self.grid_rowconfigure(3, weight=0)  # Controls
        self.grid_rowconfigure(4, weight=0)  # Status bar
        self.grid_columnconfigure(0, weight=1)

        self._setup_ui()
        self.draw_board()

    def _setup_ui(self):
        # Top Bar
        self.top_bar = tk.Frame(self, bg=self.colors['primary'], height=60)
        self.top_bar.grid(row=0, column=0, sticky="ew")
        self.top_bar.grid_propagate(False)
        
        # Game info
        info_frame = tk.Frame(self.top_bar, bg=self.colors['primary'])
        info_frame.pack(side="left", padx=15, pady=10)
        
        self.lbl_info = tk.Label(info_frame, text=f"🔴 PEGS: {self.game.get_peg_count()}", 
                                 font=("Arial", 14, "bold"),
                                 bg=self.colors['primary'], fg=self.colors['text'])
        self.lbl_info.pack(side="left")
        
        tk.Frame(info_frame, width=15, bg=self.colors['primary']).pack(side="left")
        
        version_text = "🇬🇧 ENGLISH" if self.version == "english" else "🇪🇺 EUROPEAN"
        tk.Label(info_frame, text=version_text, font=("Arial", 11),
                bg=self.colors['primary'], fg=self.colors['highlight']).pack(side="left")
        
        # Menu button
        self.btn_menu = tk.Button(self.top_bar, text="🏠 MAIN MENU", 
                                  command=self.on_exit,
                                  bg=self.colors['accent1'], fg="white",
                                  activebackground="#c0392b", activeforeground="white",
                                  font=("Arial", 11, "bold"), bd=0, cursor="hand2")
        self.btn_menu.pack(side="right", padx=15, pady=10)

        # Canvas with border - expandable
        canvas_frame = tk.Frame(self, bg=self.colors['secondary'], bd=2, relief="sunken")
        canvas_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)
        
        self.canvas = tk.Canvas(canvas_frame, bg=self.colors['bg'], 
                                highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Configure>", self.on_canvas_configure)

        # Strategy Info Panel - compact
        info_panel = tk.Frame(self, bg=self.colors['secondary'], height=35)
        info_panel.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 5))
        info_panel.grid_propagate(False)
        
        self.strategy_label = tk.Label(info_panel, 
            text="📊 Region Shrinking • Remove outer pegs first", 
            font=("Arial", 10), bg=self.colors['secondary'], fg=self.colors['text'])
        self.strategy_label.pack(side="left", padx=10, pady=5)
        
        self.progress_label = tk.Label(info_panel, text=f"📈 {self.game.get_peg_count()}/32 pegs", 
            font=("Arial", 10, "bold"), bg=self.colors['secondary'], fg=self.colors['highlight'])
        self.progress_label.pack(side="right", padx=10, pady=5)

        # Bottom Controls - compact grid layout
        self.controls = tk.Frame(self, bg=self.colors['primary'], height=70)
        self.controls.grid(row=3, column=0, sticky="ew")
        self.controls.grid_propagate(False)
        
        # Control buttons in a single row
        btn_frame = tk.Frame(self.controls, bg=self.colors['primary'])
        btn_frame.pack(expand=True, fill="both", pady=5)
        
        btn_style = {
            "font": ("Arial", 10, "bold"),
            "width": 9,
            "height": 1,
            "bd": 0,
            "cursor": "hand2",
            "fg": "white"
        }
        
        # Single row of buttons
        tk.Button(btn_frame, text="↩️ UNDO", bg=self.colors['accent2'],
                 activebackground="#2980b9", command=self.undo_move, **btn_style).pack(side="left", padx=3, expand=True)
        
        tk.Button(btn_frame, text="🔄 RESTART", bg=self.colors['accent3'],
                 activebackground="#27ae60", command=self.restart_game, **btn_style).pack(side="left", padx=3, expand=True)
        
        self.btn_auto = tk.Button(btn_frame, text="▶️ AUTO", bg=self.colors['accent1'],
                                  activebackground="#c0392b", command=self.toggle_autoplay, **btn_style)
        self.btn_auto.pack(side="left", padx=3, expand=True)
        
        tk.Button(btn_frame, text="💡 HINT", bg=self.colors['highlight'],
                 activebackground="#f39c12", command=self.show_hint, **btn_style).pack(side="left", padx=3, expand=True)
        
        tk.Button(btn_frame, text="🔍 ANALYZE", bg="#9b59b6",
                 activebackground="#8e44ad", command=self.analyze_position, **btn_style).pack(side="left", padx=3, expand=True)
        
        tk.Button(btn_frame, text="📈 STATS", bg="#1abc9c",
                 activebackground="#16a085", command=self.show_stats, **btn_style).pack(side="left", padx=3, expand=True)
        
        # Status bar - compact
        self.status_bar = tk.Frame(self, bg=self.colors['secondary'], height=25)
        self.status_bar.grid(row=4, column=0, sticky="ew")
        self.status_bar.grid_propagate(False)
        
        self.lbl_status = tk.Label(self.status_bar, text="✅ Ready • Click a peg to start", 
                                   font=("Arial", 9), bg=self.colors['secondary'], fg=self.colors['text'])
        self.lbl_status.pack(side="left", padx=10, pady=2)
        
        self.lbl_timer = tk.Label(self.status_bar, text="", 
                                  font=("Arial", 9), bg=self.colors['secondary'], fg=self.colors['highlight'])
        self.lbl_timer.pack(side="right", padx=10, pady=2)

    def on_canvas_configure(self, event):
        """Redraw board when canvas is resized"""
        self.draw_board()

    def draw_board(self):
        self.canvas.delete("all")
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        
        # Ensure minimum dimensions
        if width < 100 or height < 100:
            return
            
        rows, cols = 7, 7
        # Calculate cell size to fit in available space
        cell_size = min((width - 40) // (cols + 1), (height - 40) // (rows + 1))
        cell_size = max(cell_size, 30)  # Minimum cell size
        
        offset_x = (width - cols * cell_size) // 2
        offset_y = (height - rows * cell_size) // 2
        
        # Draw grid lines
        for i in range(rows + 1):
            y = offset_y + i * cell_size
            self.canvas.create_line(offset_x, y, offset_x + cols * cell_size, y, 
                                   fill=self.colors['secondary'], width=1, dash=(2,4))
        for i in range(cols + 1):
            x = offset_x + i * cell_size
            self.canvas.create_line(x, offset_y, x, offset_y + rows * cell_size, 
                                   fill=self.colors['secondary'], width=1, dash=(2,4))
        
        self.node_centers = {}
        for idx in range(len(self.graph.nodes)):
            r,c = self.graph.nodes[idx]
            x = offset_x + c*cell_size + cell_size//2
            y = offset_y + r*cell_size + cell_size//2
            self.node_centers[idx] = (x,y)
            
            radius = max(cell_size//3, 10)  # Minimum radius
            
            if self.game.pegs[idx] == 0:
                # Empty hole
                self.canvas.create_oval(x-radius, y-radius, x+radius, y+radius,
                                       fill=self.colors['secondary'], 
                                       outline=self.colors['text'], width=2)
            else:
                # Peg
                color = self.colors['accent1']
                if idx == self.selected_node:
                    color = self.colors['highlight']
                    # Glow effect
                    self.canvas.create_oval(x-radius-2, y-radius-2, 
                                           x+radius+2, y+radius+2,
                                           fill="", outline=color, width=2, dash=(2,2))
                
                self.canvas.create_oval(x-radius, y-radius, x+radius, y+radius,
                                       fill=color, outline="white", width=2)
        
        # Update info
        self.lbl_info.config(text=f"🔴 PEGS: {self.game.get_peg_count()}")
        self.progress_label.config(text=f"📈 {self.game.get_peg_count()}/32 pegs")
        
        if self.game.is_game_over():
            self.show_game_over()

    def show_game_over(self):
        count = self.game.get_peg_count()
        if count == 1:
            msg = "🎉 VICTORY! 🎉"
            submsg = "Perfect solution found!"
            color = self.colors['accent3']
        else:
            msg = f"🏁 GAME OVER"
            submsg = f"Pegs remaining: {count}"
            color = self.colors['accent1']
            
        w,h = self.canvas.winfo_width(), self.canvas.winfo_height()
        
        # Semi-transparent overlay
        self.canvas.create_rectangle(0, h//2-40, w, h//2+40, 
                                     fill="#000000", stipple="gray50")
        
        self.canvas.create_text(w//2, h//2-15, text=msg, 
                               fill=color, font=("Arial", 20, "bold"))
        self.canvas.create_text(w//2, h//2+15, text=submsg, 
                               fill="white", font=("Arial", 14))

    def on_click(self, event):
        if self.autoplay_running or self.searching:
            self.lbl_status.config(text="⏳ Please wait...")
            return
            
        clicked = None
        for idx, (cx,cy) in self.node_centers.items():
            if (event.x-cx)**2 + (event.y-cy)**2 < 900:
                clicked = idx
                break
                
        if clicked is None:
            return
            
        if self.selected_node is None:
            if self.game.pegs[clicked]:
                self.selected_node = clicked
                self.lbl_status.config(text=f"📍 Selected peg")
                self.draw_board()
        else:
            target = clicked
            if target == self.selected_node:
                self.selected_node = None
                self.lbl_status.config(text="✅ Cleared")
                self.draw_board()
            elif self.game.pegs[target]==0:
                move = None
                for s,m,e in self.game.get_legal_moves():
                    if s==self.selected_node and e==target:
                        move = (s,m,e)
                        break
                if move:
                    self.game.execute_move(move)
                    self.selected_node = None
                    self.draw_board()
                    self.solver = RegionShrinkingDCSolver(self.game)
                    self.solver.game_frame = self
                    self.lbl_status.config(text="✅ Move executed")
                else:
                    self.lbl_status.config(text="❌ Invalid jump!")
                    self.selected_node = target
                    self.draw_board()
            else:
                self.selected_node = target
                self.lbl_status.config(text=f"📍 New peg selected")
                self.draw_board()

    def undo_move(self):
        if self.autoplay_running or self.searching:
            return
        if self.game.undo():
            self.selected_node = None
            self.draw_board()
            self.solver = RegionShrinkingDCSolver(self.game)
            self.solver.game_frame = self
            self.lbl_status.config(text="↩️ Undone")
        else:
            self.lbl_status.config(text="⚠️ No moves")

    def restart_game(self):
        self.autoplay_running = False
        self.searching = False
        self.btn_auto.config(text="▶️ AUTO")
        self.game = GameState(self.graph)
        self.solver = RegionShrinkingDCSolver(self.game)
        self.solver.game_frame = self
        self.selected_node = None
        self.draw_board()
        self.lbl_status.config(text="🔄 Restarted")

    def on_exit(self):
        self.autoplay_running = False
        self.searching = False
        self.solver.cancel_solving()
        self.on_back()

    def show_hint(self):
        if self.autoplay_running or self.searching:
            return
        self.searching = True
        self.lbl_status.config(text="🔍 Searching...")
        self.solver.start_solving(callback=self._on_hint_solution)

    def _on_hint_solution(self, solution):
        self.searching = False
        if solution:
            self.solver.solution_cache = solution
            move = solution[0]
            sx,sy = self.node_centers[move[0]]
            ex,ey = self.node_centers[move[2]]
            
            self.canvas.create_line(sx,sy,ex,ey, 
                                   fill=self.colors['accent3'], width=4, 
                                   arrow=tk.LAST, arrowshape=(12,16,6))
            self.lbl_status.config(text=f"💡 Hint: Move from {move[0]} to {move[2]}")
        else:
            self.lbl_status.config(text="❌ No hint available")

    def toggle_autoplay(self):
        if self.autoplay_running:
            self.autoplay_running = False
            self.btn_auto.config(text="▶️ AUTO")
            self.solver.cancel_solving()
            self.lbl_status.config(text="⏹️ Stopped")
            return
            
        if self.searching:
            return
            
        self.searching = True
        self.lbl_status.config(text="🧠 Computing...")
        self.solver.start_solving(callback=self._on_autoplay_solution)

    def _on_autoplay_solution(self, solution):
        self.searching = False
        if solution:
            self.autoplay_moves = solution
            self.autoplay_index = 0
            self.autoplay_running = True
            self.btn_auto.config(text="⏸️ STOP")
            self.lbl_status.config(text=f"▶️ Playing ({len(solution)} moves)")
            self.run_autoplay_step()
        else:
            remaining = self.game.get_peg_count()
            self.lbl_status.config(text=f"⚠️ Finished - {remaining} pegs")
            self.autoplay_running = False
            self.btn_auto.config(text="▶️ AUTO")

    def run_autoplay_step(self):
        if not self.autoplay_running:
            return
            
        if self.autoplay_index >= len(self.autoplay_moves):
            if self.game.is_game_over():
                self.autoplay_running = False
                self.btn_auto.config(text="▶️ AUTO")
                self.lbl_status.config(text="🎉 Autoplay complete!")
                return
            
            self.lbl_status.config(text="🔄 Planning...")
            self.searching = True
            self.solver.start_solving(callback=self._on_autoplay_solution)
            return
            
        move = self.autoplay_moves[self.autoplay_index]
        if move not in self.game.get_legal_moves():
            self.autoplay_running = False
            self.btn_auto.config(text="▶️ AUTO")
            self.lbl_status.config(text="❌ Error")
            return
            
        self.game.execute_move(move)
        self.draw_board()
        
        progress = (self.autoplay_index + 1) / len(self.autoplay_moves) * 100
        self.lbl_status.config(text=f"▶️ Progress: {progress:.0f}%")
        
        self.autoplay_index += 1
        self.after(500, self.run_autoplay_step)

    def analyze_position(self):
        """Analyze current position"""
        legal_moves = self.game.get_legal_moves()
        peg_count = self.game.get_peg_count()
        
        if legal_moves:
            directions = {'horizontal': 0, 'vertical': 0}
            for s,m,e in legal_moves:
                r1,c1 = self.graph.nodes[s]
                r2,c2 = self.graph.nodes[e]
                if r1 == r2:
                    directions['horizontal'] += 1
                else:
                    directions['vertical'] += 1
            
            self.lbl_status.config(text=f"📊 {len(legal_moves)} moves")
            
            messagebox.showinfo("Analysis", 
                f"🔴 PEGS: {peg_count}\n"
                f"🎯 MOVES: {len(legal_moves)}\n"
                f"   ↔️ Horizontal: {directions['horizontal']}\n"
                f"   ↕️ Vertical: {directions['vertical']}\n"
                f"📈 Progress: {32 - peg_count}/31 moves")
        else:
            self.lbl_status.config(text="📊 Game over")

    def show_stats(self):
        """Show game statistics"""
        peg_count = self.game.get_peg_count()
        history_length = len(self.game.history)
        
        stats = f"""📈 STATISTICS

        Current pegs: {peg_count}
        Moves made: {history_length}
        Progress: {32 - peg_count}/31 moves

        🎯 STRATEGY
        Algorithm: Divide & Conquer
        Heuristic: Region Shrinking
        Priority: Remove outer pegs first

        💡 TIPS
        • Select a red peg, then click an empty hole
        • Only diagonal jumps are not allowed
        • Try to clear the board to a single peg"""
        
        messagebox.showinfo("Statistics", stats)

if __name__ == "__main__":
    root = tk.Tk()
    app = PegSolitaireApp(root)
    root.mainloop()



