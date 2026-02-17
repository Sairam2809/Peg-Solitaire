import tkinter as tk
from tkinter import messagebox, ttk
import threading
import time

# ======================================================================
# BoardGraph – exactly as original
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
                "  XXX  ",
                "  XXX  ",
                "XXXXXXX",
                "XXXXXXX",
                "XXXXXXX",
                "  XXX  ",
                "  XXX  "
            ]
        else: # european
            layout = [
                "  XXX  ",
                " XXXXX ",
                "XXXXXXX",
                "XXXXXXX",
                "XXXXXXX",
                " XXXXX ",
                "  XXX  "
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
# GameState – unchanged
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
# QUICKSORT IMPLEMENTATION (in-place)
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
# PURE DIVIDE‑AND‑CONQUER SOLVER (no backtracking)
# ======================================================================
class RegionShrinkingDCSolver:
    """
    Region Shrinking / Central Expansion Solver (Pure Divide & Conquer).
    Strategy:
      - Inherits the Divide & Conquer structure (Spatial Splitting).
      - Enhances the 'Conquer' and 'Combine' phases with a Priority Heuristic.
      - PRIORITY: Linearly scan for valid moves, but execute them in an order
                  that effectively 'shrinks' the board from the outside in.
                  Priority = Distance of the removed peg (middle peg) from center.
                  Outer pegs are removed first.
    Algorithm:
      1. DIVIDE : Partition the board spatially into two halves.
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
        # Work on a COPY of the peg state so the UI board is untouched
        pegs = self.game.pegs[:]
        all_nodes = list(range(len(self.game.graph.nodes)))
        solution = self._solve_dc(all_nodes, pegs, split_by_row=True)
        if self.search_cancel:
            solution = None
        if self.callback:
            self.game_frame.after(0, self.callback, solution if solution else None)

    # ---- pure divide & conquer -------------------------------------------
    def _solve_dc(self, node_indices, pegs, split_by_row=True):
        """
        Pure D&C entry point.
        Args:
            node_indices : list of node IDs in the current region
            pegs : mutable list[int] of peg states (0/1)
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
        left_moves = self._solve_dc(left_half, pegs, not split_by_row)
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
            candidate_moves.reverse()   # because we want descending order

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
        left_set = set(left)
        right_set = set(right)
        all_set = left_set | right_set
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

            # 2. Sort by priority (descending) — replaced with quicksort
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
# UI – ENHANCED VERSION with Modern Design
# ======================================================================
class PegSolitaireApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Peg Solitaire - Region Shrinking Strategy")
        self.root.geometry("700x800")
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
        tk.Label(self.current_frame, text="Pure Divide & Conquer • No Backtracking",
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
        self._setup_ui()
        self.draw_board()

    def _setup_ui(self):
        # Top Bar with gradient effect
        self.top_bar = tk.Frame(self, bg=self.colors['primary'], height=70)
        self.top_bar.pack(fill="x")
        self.top_bar.pack_propagate(False)
       
        # Game info with icons
        info_frame = tk.Frame(self.top_bar, bg=self.colors['primary'])
        info_frame.pack(side="left", padx=20, pady=15)
       
        self.lbl_info = tk.Label(info_frame, text=f"🔴 PEGS: {self.game.get_peg_count()}",
                                 font=("Arial", 16, "bold"),
                                 bg=self.colors['primary'], fg=self.colors['text'])
        self.lbl_info.pack(side="left")
       
        tk.Frame(info_frame, width=20, bg=self.colors['primary']).pack(side="left")
       
        version_text = "🇬🇧 ENGLISH" if self.version == "english" else "🇪🇺 EUROPEAN"
        tk.Label(info_frame, text=version_text, font=("Arial", 12),
                bg=self.colors['primary'], fg=self.colors['highlight']).pack(side="left")
       
        # Menu button
        self.btn_menu = tk.Button(self.top_bar, text="🏠 MAIN MENU",
                                  command=self.on_exit,
                                  bg=self.colors['accent1'], fg="white",
                                  activebackground="#c0392b", activeforeground="white",
                                  font=("Arial", 12, "bold"), bd=0, cursor="hand2")
        self.btn_menu.pack(side="right", padx=20, pady=15)

        # Canvas with border
        canvas_frame = tk.Frame(self, bg=self.colors['secondary'], bd=2, relief="sunken")
        canvas_frame.pack(fill="both", expand=True, padx=30, pady=20)
       
        self.canvas = tk.Canvas(canvas_frame, bg=self.colors['bg'],
                                highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=5, pady=5)
        self.canvas.bind("<Button-1>", self.on_click)

        # Strategy Info Panel
        info_panel = tk.Frame(self, bg=self.colors['secondary'], height=60)
        info_panel.pack(fill="x", padx=30, pady=(0, 10))
       
        self.strategy_label = tk.Label(info_panel,
            text="📊 STRATEGY: Region Shrinking • Remove outer pegs first",
            font=("Arial", 11), bg=self.colors['secondary'], fg=self.colors['text'])
        self.strategy_label.pack(side="left", padx=20, pady=10)
       
        self.progress_label = tk.Label(info_panel, text="",
            font=("Arial", 11, "bold"), bg=self.colors['secondary'], fg=self.colors['highlight'])
        self.progress_label.pack(side="right", padx=20, pady=10)

        # Bottom Controls with modern styling
        self.controls = tk.Frame(self, bg=self.colors['primary'], height=80)
        self.controls.pack(fill="x", side="bottom")
        self.controls.pack_propagate(False)
       
        # Control buttons in a grid
        btn_frame = tk.Frame(self.controls, bg=self.colors['primary'])
        btn_frame.pack(expand=True)
       
        btn_style = {
            "font": ("Arial", 11, "bold"),
            "width": 12,
            "height": 2,
            "bd": 0,
            "cursor": "hand2",
            "fg": "white"
        }
       
        # Row 1
        tk.Button(btn_frame, text="↩️ UNDO", bg=self.colors['accent2'],
                 activebackground="#2980b9", command=self.undo_move, **btn_style).grid(row=0, column=0, padx=5, pady=5)
       
        tk.Button(btn_frame, text="🔄 RESTART", bg=self.colors['accent3'],
                 activebackground="#27ae60", command=self.restart_game, **btn_style).grid(row=0, column=1, padx=5, pady=5)
       
        tk.Button(btn_frame, text="💡 HINT", bg=self.colors['highlight'],
                 activebackground="#f39c12", command=self.show_hint, **btn_style).grid(row=0, column=2, padx=5, pady=5)
       
        # Row 2
        self.btn_auto = tk.Button(btn_frame, text="▶️ AUTOPLAY", bg=self.colors['accent1'],
                                  activebackground="#c0392b", command=self.toggle_autoplay, **btn_style)
        self.btn_auto.grid(row=1, column=0, padx=5, pady=5)
       
        self.btn_analyze = tk.Button(btn_frame, text="🔍 ANALYZE", bg="#9b59b6",
                                     activebackground="#8e44ad", command=self.analyze_position, **btn_style)
        self.btn_analyze.grid(row=1, column=1, padx=5, pady=5)
       
        self.btn_stats = tk.Button(btn_frame, text="📈 STATS", bg="#1abc9c",
                                   activebackground="#16a085", command=self.show_stats, **btn_style)
        self.btn_stats.grid(row=1, column=2, padx=5, pady=5)

        # Status bar
        self.status_bar = tk.Frame(self, bg=self.colors['secondary'], height=30)
        self.status_bar.pack(fill="x")
        self.status_bar.pack_propagate(False)
       
        self.lbl_status = tk.Label(self.status_bar, text="✅ Ready • Click a peg to start",
                                   font=("Arial", 10), bg=self.colors['secondary'], fg=self.colors['text'])
        self.lbl_status.pack(side="left", padx=20)
       
        self.lbl_timer = tk.Label(self.status_bar, text="",
                                  font=("Arial", 10), bg=self.colors['secondary'], fg=self.colors['highlight'])
        self.lbl_timer.pack(side="right", padx=20)

    def draw_board(self):
        self.canvas.delete("all")
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        if width < 10: width = 600
        if height < 10: height = 500
       
        rows, cols = 7, 7
        cell_size = min(width, height)//(rows+1)
        offset_x = (width - cols*cell_size)//2
        offset_y = (height - rows*cell_size)//2
       
        # Draw grid lines (subtle)
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
           
            # Draw peg with glow effect for selected
            radius = cell_size//3
            if self.game.pegs[idx] == 0:
                # Empty hole
                self.canvas.create_oval(x-radius, y-radius, x+radius, y+radius,
                                       fill=self.colors['secondary'],
                                       outline=self.colors['text'], width=2)
                # Inner shadow
                self.canvas.create_oval(x-radius+2, y-radius+2, x+radius-2, y+radius-2,
                                       fill=self.colors['secondary'], outline="")
            else:
                # Peg with gradient effect
                color = self.colors['accent1']
                if idx == self.selected_node:
                    color = self.colors['highlight']
                    # Glow effect
                    for i in range(3, 0, -1):
                        self.canvas.create_oval(x-radius-i, y-radius-i,
                                               x+radius+i, y+radius+i,
                                               fill="", outline=color, width=1, dash=(2,2))
               
                # Main peg
                self.canvas.create_oval(x-radius, y-radius, x+radius, y+radius,
                                       fill=color, outline="white", width=2)
                # Highlight
                self.canvas.create_oval(x-radius+3, y-radius+3, x+radius-5, y+radius-5,
                                       fill="", outline="white", width=1)
       
        # Update info
        self.lbl_info.config(text=f"🔴 PEGS: {self.game.get_peg_count()}")
        self.progress_label.config(text=f"📊 Progress: {32 - self.game.get_peg_count()}/31 moves")
       
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
        self.canvas.create_rectangle(0, h//2-60, w, h//2+60,
                                     fill="#000000", stipple="gray50")
       
        self.canvas.create_text(w//2, h//2-20, text=msg,
                               fill=color, font=("Arial", 24, "bold"))
        self.canvas.create_text(w//2, h//2+20, text=submsg,
                               fill="white", font=("Arial", 16))

    def on_click(self, event):
        if self.autoplay_running or self.searching:
            self.lbl_status.config(text="⏳ Please wait for current operation to complete...")
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
                self.lbl_status.config(text=f"📍 Selected peg at position {clicked}")
                self.draw_board()
        else:
            target = clicked
            if target == self.selected_node:
                self.selected_node = None
                self.lbl_status.config(text="✅ Selection cleared")
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
                    # Visual feedback
                    self.canvas.after(100, self._flash_move, move)
                    # Recreate solver for new state
                    self.solver = RegionShrinkingDCSolver(self.game)
                    self.solver.game_frame = self
                    self.lbl_status.config(text="✅ Move executed successfully")
                else:
                    self.lbl_status.config(text="❌ Not a valid jump!")
                    self.selected_node = target
                    self.draw_board()
            else:
                self.selected_node = target
                self.lbl_status.config(text=f"📍 Selected new peg at position {target}")
                self.draw_board()

    def _flash_move(self, move):
        """Flash the move for visual feedback"""
        s,m,e = move
        for node in [s,m,e]:
            x,y = self.node_centers[node]
            self.canvas.create_oval(x-20, y-20, x+20, y+20,
                                   outline=self.colors['highlight'], width=3, dash=(4,4))

    def undo_move(self):
        if self.autoplay_running or self.searching:
            return
        if self.game.undo():
            self.selected_node = None
            self.draw_board()
            self.solver = RegionShrinkingDCSolver(self.game)
            self.solver.game_frame = self
            self.lbl_status.config(text="↩️ Last move undone")
        else:
            self.lbl_status.config(text="⚠️ No moves to undo")

    def restart_game(self):
        self.autoplay_running = False
        self.searching = False
        self.btn_auto.config(text="▶️ AUTOPLAY")
        self.game = GameState(self.graph)
        self.solver = RegionShrinkingDCSolver(self.game)
        self.solver.game_frame = self
        self.selected_node = None
        self.draw_board()
        self.lbl_status.config(text="🔄 Game restarted")

    def on_exit(self):
        self.autoplay_running = False
        self.searching = False
        self.solver.cancel_solving()
        self.on_back()

    def show_hint(self):
        if self.autoplay_running or self.searching:
            return
        self.searching = True
        self.lbl_status.config(text="🔍 Searching for best move...")
        self.solver.start_solving(callback=self._on_hint_solution)

    def _on_hint_solution(self, solution):
        self.searching = False
        if solution:
            self.solver.solution_cache = solution
            move = solution[0]
            sx,sy = self.node_centers[move[0]]
            ex,ey = self.node_centers[move[2]]
           
            # Draw animated arrow
            self.canvas.create_line(sx,sy,ex,ey,
                                   fill=self.colors['accent3'], width=5,
                                   arrow=tk.LAST, arrowshape=(16,20,6))
           
            # Highlight the move
            self._flash_move(move)
           
            self.lbl_status.config(text=f"💡 Hint: Move from {move[0]} to {move[2]}")
        else:
            self.lbl_status.config(text="❌ No winning move found from this position")

    def toggle_autoplay(self):
        if self.autoplay_running:
            self.autoplay_running = False
            self.btn_auto.config(text="▶️ AUTOPLAY")
            self.solver.cancel_solving()
            self.lbl_status.config(text="⏹️ Autoplay stopped")
            return
           
        if self.searching:
            return
           
        self.searching = True
        self.lbl_status.config(text="🧠 Computing full solution (Region Shrinking)...")
        self.solver.start_solving(callback=self._on_autoplay_solution)

    def _on_autoplay_solution(self, solution):
        self.searching = False
        if solution:
            self.autoplay_moves = solution
            self.autoplay_index = 0
            self.autoplay_running = True
            self.btn_auto.config(text="⏸️ STOP")
            self.lbl_status.config(text=f"▶️ Playing solution ({len(solution)} moves)")
            self.run_autoplay_step()
        else:
            remaining = self.game.get_peg_count()
            if remaining == 1:
                self.lbl_status.config(text="🎉 Victory achieved!")
                self.autoplay_running = False
                self.btn_auto.config(text="▶️ AUTOPLAY")
            else:
                self.lbl_status.config(text=f"⚠️ D&C strategy completed with {remaining} pegs")
                self.autoplay_running = False
                self.btn_auto.config(text="▶️ AUTOPLAY")

    def run_autoplay_step(self):
        if not self.autoplay_running:
            return
           
        if self.autoplay_index >= len(self.autoplay_moves):
            if self.game.is_game_over():
                self.autoplay_running = False
                self.btn_auto.config(text="▶️ AUTOPLAY")
                remaining = self.game.get_peg_count()
                if remaining == 1:
                    self.lbl_status.config(text="🎉 AUTOPLAY COMPLETE - VICTORY!")
                else:
                    self.lbl_status.config(text=f"🏁 Autoplay finished - {remaining} pegs remain")
                return
           
            self.lbl_status.config(text="🔄 Planning next moves...")
            self.searching = True
            self.solver.start_solving(callback=self._on_autoplay_solution)
            return
           
        move = self.autoplay_moves[self.autoplay_index]
        if move not in self.game.get_legal_moves():
            self.autoplay_running = False
            self.btn_auto.config(text="▶️ AUTOPLAY")
            self.lbl_status.config(text="❌ Error: Solution invalid")
            return
           
        self.game.execute_move(move)
        self.draw_board()
       
        # Update progress
        progress = (self.autoplay_index + 1) / len(self.autoplay_moves) * 100
        self.lbl_status.config(text=f"▶️ Autoplay progress: {progress:.1f}% ({self.autoplay_index + 1}/{len(self.autoplay_moves)})")
       
        self.autoplay_index += 1
        self.after(600, self.run_autoplay_step)

    def analyze_position(self):
        """Analyze current position and show statistics"""
        legal_moves = self.game.get_legal_moves()
        peg_count = self.game.get_peg_count()
       
        if legal_moves:
            # Categorize moves by direction
            directions = {'horizontal': 0, 'vertical': 0}
            for s,m,e in legal_moves:
                r1,c1 = self.graph.nodes[s]
                r2,c2 = self.graph.nodes[e]
                if r1 == r2:
                    directions['horizontal'] += 1
                else:
                    directions['vertical'] += 1
           
            analysis = f"📊 Analysis: {len(legal_moves)} legal moves"
            analysis += f" | ↔️ {directions['horizontal']} horizontal"
            analysis += f" | ↕️ {directions['vertical']} vertical"
            analysis += f" | 📍 {peg_count} pegs"
           
            self.lbl_status.config(text=analysis)
           
            # Show in a message box with more detail
            messagebox.showinfo("Position Analysis",
                f"🔴 PEGS REMAINING: {peg_count}\n\n"
                f"🎯 LEGAL MOVES: {len(legal_moves)}\n"
                f" • Horizontal: {directions['horizontal']}\n"
                f" • Vertical: {directions['vertical']}\n\n"
                f"📈 PROGRESS: {32 - peg_count}/31 moves completed\n"
                f"💡 STRATEGY: Region Shrinking (remove outer pegs first)")
        else:
            self.lbl_status.config(text="📊 Analysis: Game over - no legal moves")
            messagebox.showinfo("Position Analysis",
                f"🏁 GAME OVER\n\nPegs remaining: {peg_count}\n\n"
                f"{'🎉 VICTORY!' if peg_count == 1 else 'Try restarting the game.'}")

    def show_stats(self):
        """Show game statistics"""
        peg_count = self.game.get_peg_count()
        history_length = len(self.game.history)
       
        stats = f"""📈 GAME STATISTICS
        Current pegs: {peg_count}
        Moves made: {history_length}
        Progress: {32 - peg_count}/31 moves
        🎯 STRATEGY INFO
        Algorithm: Pure Divide & Conquer
        Heuristic: Region Shrinking
        Priority: Remove outer pegs first
        💡 TIPS
        • Select a red peg, then click an empty hole
        • Only diagonal jumps are not allowed
        • Try to clear the board to a single peg"""
   
        messagebox.showinfo("Game Statistics", stats)

if __name__ == "__main__":
    root = tk.Tk()
    app = PegSolitaireApp(root)
    root.mainloop()