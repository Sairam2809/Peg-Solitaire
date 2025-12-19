import tkinter as tk
from tkinter import messagebox, Toplevel, ttk
import copy

# ---------------- VERSION SELECTION DIALOG ----------------
class VersionSelectionDialog:
    def __init__(self, root):
        self.result = None
        self.dialog = Toplevel(root)
        self.dialog.title("Peg Solitaire")
        self.dialog.geometry("550x450")
        self.dialog.resizable(False, False)
        
        self.dialog.transient(root)
        self.dialog.grab_set()
        self.dialog.configure(bg="#1a1a2e")
        
        # Animated header with gradient effect
        header_frame = tk.Frame(self.dialog, bg="#0f3460", height=120)
        header_frame.pack(fill="x")
        header_frame.pack_propagate(False)
        
        tk.Label(
            header_frame, text="✦ PEG SOLITAIRE ✦",
            font=('Helvetica', 32, 'bold'),
            bg="#0f3460", fg="#00d4ff"
        ).pack(expand=True, pady=(15, 5))
        
        tk.Label(
            header_frame, text="Classic Strategy Puzzle",
            font=('Helvetica', 13, 'italic'),
            bg="#0f3460", fg="#16c79a"
        ).pack()
        
        # Content
        content_frame = tk.Frame(self.dialog, bg="#1a1a2e", padx=40, pady=30)
        content_frame.pack(fill="both", expand=True)
        
        tk.Label(
            content_frame, text="Choose Your Board",
            font=('Helvetica', 18, 'bold'),
            bg="#1a1a2e", fg="#ffffff"
        ).pack(pady=(0, 25))
        
        # Version cards with better styling
        desc_frame = tk.Frame(content_frame, bg="#16213e", padx=20, pady=20, relief="flat", bd=0)
        desc_frame.pack(pady=(0, 30))
        
        tk.Label(
            desc_frame, 
            text="🎯 English Board: 7×7 with corner cutouts (33 pegs)\n💎 European Board: 7×7 diamond pattern (37 pegs)",
            font=('Helvetica', 11),
            bg="#16213e", fg="#e0e0e0", 
            justify="left",
            padx=10, pady=5
        ).pack()
        
        # Button container
        btn_frame = tk.Frame(content_frame, bg="#1a1a2e")
        btn_frame.pack()
        
        # Styled buttons with hover effects
        for version, text, color, emoji in [
            ('english', 'ENGLISH BOARD', '#e74c3c', '🎯'),
            ('european', 'EUROPEAN BOARD', '#00d4ff', '💎')
        ]:
            btn = tk.Button(
                btn_frame, 
                text=f"{emoji}  {text}",
                font=('Helvetica', 13, 'bold'),
                width=22, height=2,
                bg=color, fg="white",
                activebackground=self.darken_color(color),
                activeforeground="white",
                relief="flat", 
                cursor="hand2",
                bd=0,
                command=lambda v=version: self.select(v)
            )
            btn.pack(pady=8)
            self.add_hover_effect(btn, color)
        
        # Elegant footer
        footer_frame = tk.Frame(self.dialog, bg="#0f0f1e", height=45)
        footer_frame.pack(fill="x", side="bottom")
        tk.Label(
            footer_frame, 
            text="Built with Python • Tkinter",
            font=('Helvetica', 10, 'italic'),
            bg="#0f0f1e", fg="#808080"
        ).pack(pady=12)
        
        root.wait_window(self.dialog)
    
    def select(self, version):
        self.result = version
        self.dialog.destroy()
    
    def darken_color(self, color):
        # Simple color darkening
        colors = {
            '#e74c3c': '#c0392b',
            '#00d4ff': '#0099cc',
            '#16c79a': '#11a87d'
        }
        return colors.get(color, color)
    
    def add_hover_effect(self, button, color):
        darker = self.darken_color(color)
        button.bind("<Enter>", lambda e: button.config(bg=darker))
        button.bind("<Leave>", lambda e: button.config(bg=color))


# ---------------- MAIN GAME GUI ----------------
class PegSolitaireGUI:
    def __init__(self, root, version):
        self.root = root
        self.version = version
        self.root.title(f"Peg Solitaire – {self.version.capitalize()}")
        
        # Enhanced modern color scheme
        self.colors = {
            'bg': '#1a1a2e',
            'board_bg': '#16213e',
            'peg': '#e74c3c',
            'selected_peg': '#00d4ff',
            'hole': '#0f3460',
            'valid_hole': '#16c79a',
            'text': '#ffffff',
            'button_bg': '#00d4ff',
            'button_hover': '#0099cc',
            'accent': '#16c79a',
            'panel_bg': '#16213e'
        }
        
        self.root.configure(bg=self.colors['bg'])
        
        # Game variables
        self.cell_size = 64
        self.selected = None
        self.move_count = 0
        self.pegs_count = 0
        self.game_over_flag = False
        self.move_history = []
        self.auto_play_running = False
        
        # Create main container
        self.main = tk.Frame(root, bg=self.colors['bg'], padx=25, pady=25)
        self.main.pack(fill="both", expand=True)
        
        # Header
        self.create_header()
        
        # Game area
        game_frame = tk.Frame(self.main, bg=self.colors['bg'])
        game_frame.pack(fill="both", expand=True, pady=(15, 0))
        
        # Left panel
        left_panel = tk.Frame(game_frame, bg=self.colors['bg'], width=220)
        left_panel.pack(side="left", fill="y", padx=(0, 25))
        
        # Right panel
        right_panel = tk.Frame(game_frame, bg=self.colors['bg'])
        right_panel.pack(side="right", fill="both", expand=True)
        
        # Create panels
        self.create_stats_panel(left_panel)
        self.create_controls_panel(left_panel)
        
        # Canvas
        self.canvas = tk.Canvas(
            right_panel,
            width=520,
            height=520,
            bg=self.colors['board_bg'],
            highlightthickness=2,
            highlightbackground=self.colors['accent'],
            relief="flat"
        )
        self.canvas.pack(expand=True)
        
        # Bind events
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Motion>", self.on_hover)
        
        # Initialize
        self.initial_board()
        self.draw_board()
        self.update_stats()
        
    def create_header(self):
        header_frame = tk.Frame(self.main, bg=self.colors['bg'])
        header_frame.pack(fill="x", pady=(0, 15))
        
        # Title container
        title_container = tk.Frame(header_frame, bg=self.colors['bg'])
        title_container.pack()
        
        title = tk.Label(
            title_container,
            text="✦ PEG SOLITAIRE ✦",
            font=('Helvetica', 28, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['button_bg']
        )
        title.pack()
        
        self.subtitle = tk.Label(
            title_container,
            text=f"{self.version.upper()} VERSION",
            font=('Helvetica', 15, 'bold'),
            bg=self.colors['bg'],
            fg=self.colors['accent']
        )
        self.subtitle.pack()
        
    def create_stats_panel(self, parent):
        stats_frame = tk.Frame(
            parent,
            bg=self.colors['panel_bg'],
            relief="flat",
            bd=0
        )
        stats_frame.pack(fill="x", pady=(0, 20))
        
        # Panel title
        tk.Label(
            stats_frame,
            text="📊 GAME STATS",
            font=('Helvetica', 13, 'bold'),
            bg=self.colors['panel_bg'],
            fg=self.colors['text'],
            pady=12
        ).pack()
        
        # Separator
        tk.Frame(stats_frame, height=2, bg=self.colors['accent']).pack(fill="x", padx=20)
        
        # Stats
        stats_container = tk.Frame(stats_frame, bg=self.colors['panel_bg'])
        stats_container.pack(fill="x", padx=25, pady=15)
        
        self.move_label = tk.Label(
            stats_container,
            text="Moves: 0",
            font=('Helvetica', 15, 'bold'),
            bg=self.colors['panel_bg'],
            fg=self.colors['button_bg'],
            anchor="w"
        )
        self.move_label.pack(pady=8, anchor="w")
        
        self.pegs_label = tk.Label(
            stats_container,
            text="Pegs: 0",
            font=('Helvetica', 15, 'bold'),
            bg=self.colors['panel_bg'],
            fg=self.colors['peg'],
            anchor="w"
        )
        self.pegs_label.pack(pady=8, anchor="w")
        
        self.status_label = tk.Label(
            stats_container,
            text="● Playing",
            font=('Helvetica', 13),
            bg=self.colors['panel_bg'],
            fg=self.colors['accent'],
            anchor="w"
        )
        self.status_label.pack(pady=8, anchor="w")
        
    def create_controls_panel(self, parent):
        controls_frame = tk.Frame(
            parent,
            bg=self.colors['panel_bg'],
            relief="flat",
            bd=0
        )
        controls_frame.pack(fill="x", pady=(0, 20))
        
        # Panel title
        tk.Label(
            controls_frame,
            text="🎮 CONTROLS",
            font=('Helvetica', 13, 'bold'),
            bg=self.colors['panel_bg'],
            fg=self.colors['text'],
            pady=12
        ).pack()
        
        # Separator
        tk.Frame(controls_frame, height=2, bg=self.colors['accent']).pack(fill="x", padx=20)
        
        # Buttons container
        btn_container = tk.Frame(controls_frame, bg=self.colors['panel_bg'])
        btn_container.pack(fill="x", padx=20, pady=15)
        
        buttons = [
            ("💡 Hint", self.greedy_hint, self.colors['accent']),
            ("🔄 Switch Version", self.switch_version, '#9b59b6'),
            ("↺ Restart", self.restart, self.colors['button_bg']),
            ("🤖 Auto Play", self.toggle_auto_play, '#f39c12'),
            ("⏪ Undo", self.undo_move, '#95a5a6'),
        ]
        
        for text, command, color in buttons:
            btn = tk.Button(
                btn_container,
                text=text,
                font=('Helvetica', 11, 'bold'),
                width=18,
                height=1,
                bg=color,
                fg="white",
                activebackground=self.darken_color(color),
                activeforeground="white",
                relief="flat",
                cursor="hand2",
                bd=0,
                command=command
            )
            btn.pack(pady=6)
            self.add_button_hover(btn, color)
        
        # Instructions
        info_frame = tk.Frame(controls_frame, bg=self.colors['panel_bg'])
        info_frame.pack(fill="x", pady=(12, 10))
        
        tk.Label(
            info_frame,
            text="HOW TO PLAY:",
            font=('Helvetica', 10, 'bold'),
            bg=self.colors['panel_bg'],
            fg=self.colors['text']
        ).pack(anchor="w", padx=25)
        
        tk.Label(
            info_frame,
            text="• Click peg to select\n• Click hole to jump\n• Jump over adjacent peg\n• Goal: 1 peg remaining",
            font=('Helvetica', 9),
            bg=self.colors['panel_bg'],
            fg="#b0b0b0",
            justify="left"
        ).pack(anchor="w", padx=25, pady=(5, 8))
    
    def darken_color(self, color):
        colors = {
            '#00d4ff': '#0099cc',
            '#16c79a': '#11a87d',
            '#e74c3c': '#c0392b',
            '#f39c12': '#d68910',
            '#9b59b6': '#7d3c98',
            '#95a5a6': '#7f8c8d'
        }
        return colors.get(color, color)
    
    def add_button_hover(self, button, color):
        darker = self.darken_color(color)
        button.bind("<Enter>", lambda e: button.config(bg=darker))
        button.bind("<Leave>", lambda e: button.config(bg=color))
    
    # ---------------- VERSION SWITCHING ----------------
    def switch_version(self):
        if self.auto_play_running:
            messagebox.showwarning("Auto Play Active", "Please stop auto play before switching versions.")
            return
        
        new_version = 'european' if self.version == 'english' else 'english'
        
        if self.move_count > 0:
            response = messagebox.askyesno(
                "Switch Version",
                f"Switch from {self.version.upper()} to {new_version.upper()}?\n\n"
                "Current game progress will be lost.",
                icon='question'
            )
            if not response:
                return
        
        self.version = new_version
        self.subtitle.config(text=f"{self.version.upper()} VERSION")
        self.root.title(f"Peg Solitaire – {self.version.capitalize()}")
        self.initial_board()
        self.draw_board()
        self.update_stats()
    
    # ---------------- GAME SETUP ----------------
    def initial_board(self):
        self.game_over_flag = False
        self.move_count = 0
        self.selected = None
        self.move_history = []
        self.auto_play_running = False
        
        if self.version == 'english':
            self.board = [
                [-1,-1,1,1,1,-1,-1],
                [-1,-1,1,1,1,-1,-1],
                [1,1,1,1,1,1,1],
                [1,1,1,0,1,1,1],
                [1,1,1,1,1,1,1],
                [-1,-1,1,1,1,-1,-1],
                [-1,-1,1,1,1,-1,-1]
            ]
        else:
            self.board = [
                [-1,-1,1,1,1,-1,-1],
                [-1,1,1,1,1,1,-1],
                [1,1,1,1,1,1,1],
                [1,1,1,0,1,1,1],
                [1,1,1,1,1,1,1],
                [-1,1,1,1,1,1,-1],
                [-1,-1,1,1,1,-1,-1]
            ]
        
        self.update_status("Playing")
    
    # ---------------- DRAW BOARD ----------------
    def draw_board(self):
        self.canvas.delete("all")
        
        for r in range(7):
            for c in range(7):
                if self.board[r][c] == -1:
                    continue
                
                x1 = c * self.cell_size + 35
                y1 = r * self.cell_size + 35
                x2 = x1 + self.cell_size - 10
                y2 = y1 + self.cell_size - 10
                
                # Draw hole
                self.canvas.create_oval(
                    x1, y1, x2, y2,
                    fill=self.colors['hole'],
                    outline="#0a1f3d",
                    width=2
                )
                
                # Draw peg or empty
                if self.board[r][c] == 1:
                    # Shadow
                    self.canvas.create_oval(
                        x1+5, y1+5, x2+5, y2+5,
                        fill="#991f1f",
                        outline=""
                    )
                    # Peg with gradient effect
                    self.canvas.create_oval(
                        x1+2, y1+2, x2+2, y2+2,
                        fill="#c0392b",
                        outline=""
                    )
                    self.canvas.create_oval(
                        x1, y1, x2, y2,
                        fill=self.colors['peg'],
                        outline="#ff6b6b",
                        width=2
                    )
                elif self.board[r][c] == 0:
                    # Empty hole
                    self.canvas.create_oval(
                        x1+8, y1+8, x2-8, y2-8,
                        fill="#0f3460",
                        outline="#1a4d7a",
                        width=1
                    )
        
        # Highlight selected peg
        if self.selected:
            r, c = self.selected
            if self.board[r][c] == 1:
                x1 = c * self.cell_size + 35
                y1 = r * self.cell_size + 35
                x2 = x1 + self.cell_size - 10
                y2 = y1 + self.cell_size - 10
                
                # Animated glow
                for i in range(4, 0, -1):
                    self.canvas.create_oval(
                        x1-i*2, y1-i*2, x2+i*2, y2+i*2,
                        outline=self.colors['selected_peg'],
                        width=2
                    )
        
        # Draw coordinates
        for i in range(7):
            self.canvas.create_text(
                35 + i * self.cell_size + (self.cell_size - 10) / 2,
                20,
                text=chr(65 + i),
                font=('Helvetica', 11, 'bold'),
                fill=self.colors['accent']
            )
            self.canvas.create_text(
                20,
                35 + i * self.cell_size + (self.cell_size - 10) / 2,
                text=str(i + 1),
                font=('Helvetica', 11, 'bold'),
                fill=self.colors['accent']
            )
    
    # ---------------- GAME LOGIC ----------------
    def on_click(self, event):
        if self.game_over_flag or self.auto_play_running:
            return
        
        r = (event.y - 35) // self.cell_size
        c = (event.x - 35) // self.cell_size
        
        if not (0 <= r < 7 and 0 <= c < 7):
            return
        
        if self.selected is None and self.board[r][c] == 1:
            self.selected = (r, c)
            self.draw_board()
        else:
            if self.selected:
                if self.try_move(self.selected, (r, c)):
                    self.move_history.append(copy.deepcopy(self.board))
                    self.move_count += 1
                    if self.check_game_over():
                        return
                self.selected = None
                self.draw_board()
        
        self.update_stats()
    
    def on_hover(self, event):
        pass
    
    def try_move(self, src, dest):
        r, c = src
        nr, nc = dest
        
        if self.board[nr][nc] != 0:
            return False
        
        dr, dc = nr - r, nc - c
        if (abs(dr) == 2 and dc == 0) or (abs(dc) == 2 and dr == 0):
            mr, mc = (r+nr)//2, (c+nc)//2
            if self.board[mr][mc] == 1:
                self.board[r][c] = 0
                self.board[mr][mc] = 0
                self.board[nr][nc] = 1
                return True
        return False
    
    def undo_move(self):
        if self.auto_play_running:
            return
        if len(self.move_history) > 0:
            self.board = self.move_history.pop()
            self.move_count = max(0, self.move_count - 1)
            self.selected = None
            self.game_over_flag = False
            self.update_status("Playing")
            self.draw_board()
            self.update_stats()
    
    def get_valid_moves(self):
        moves = []
        for r in range(7):
            for c in range(7):
                if self.board[r][c] == 1:
                    for dr, dc in [(2,0),(-2,0),(0,2),(0,-2)]:
                        nr, nc = r+dr, c+dc
                        if 0 <= nr < 7 and 0 <= nc < 7:
                            if self.board[nr][nc] == 0 and self.board[(r+nr)//2][(c+nc)//2] == 1:
                                moves.append((r,c,nr,nc))
        return moves
    
    def heuristic(self, pos):
        r, c = pos
        return abs(r - 3) + abs(c - 3)
    
    def get_greedy_move(self):
        moves = self.get_valid_moves()
        if not moves:
            return None
        moves.sort(key=lambda m: self.heuristic((m[0], m[1])), reverse=True)
        return moves[0]
    
    # ---------------- AUTO PLAY ----------------
    def toggle_auto_play(self):
        if self.game_over_flag:
            return
        
        if self.auto_play_running:
            self.auto_play_running = False
            self.update_status("Playing")
        else:
            self.auto_play_running = True
            self.update_status("Auto Playing...")
            self.greedy_auto_play()
    
    def greedy_auto_play(self):
        if not self.auto_play_running or self.game_over_flag:
            self.auto_play_running = False
            return
        
        move = self.get_greedy_move()
        if move is None:
            self.auto_play_running = False
            self.check_game_over()
            return
        
        r, c, nr, nc = move
        
        self.move_history.append(copy.deepcopy(self.board))
        self.board[r][c] = 0
        self.board[(r+nr)//2][(c+nc)//2] = 0
        self.board[nr][nc] = 1
        
        self.move_count += 1
        self.draw_board()
        self.update_stats()
        
        self.root.after(500, self.greedy_auto_play)
    
    # ---------------- HINT ----------------
    def greedy_hint(self):
        move = self.get_greedy_move()
        if move is None:
            messagebox.showinfo("💡 Hint", "No valid moves available.")
            return
        
        r, c, nr, nc = move
        messagebox.showinfo(
            "💡 Suggested Move",
            f"Move peg from {chr(65+c)}{r+1} → {chr(65+nc)}{nr+1}\n\n"
            f"This will jump over {chr(65+(c+nc)//2)}{(r+nr)//2+1}",
            icon='info'
        )
    
    # ---------------- GAME OVER ----------------
    def check_game_over(self):
        pegs = sum(row.count(1) for row in self.board)
        moves = self.get_valid_moves()
        
        if self.version == 'english':
            if pegs == 1 and self.board[3][3] == 1:
                self.update_status("Victory! 🎉")
                messagebox.showinfo(
                    "🎉 Perfect Victory!",
                    f"Congratulations!\n\n"
                    f"Total Moves: {self.move_count}\n"
                    f"Final Score: {33 - self.move_count}/32",
                    icon='info'
                )
                self.game_over_flag = True
                return True
        else:
            if pegs == 1:
                self.update_status("Victory! 🎉")
                messagebox.showinfo(
                    "🎉 Perfect Victory!",
                    f"Congratulations!\n\n"
                    f"Total Moves: {self.move_count}\n"
                    f"Final Score: {37 - self.move_count}/36",
                    icon='info'
                )
                self.game_over_flag = True
                return True
        
        if pegs > 1 and not moves:
            self.update_status("Game Over")
            messagebox.showinfo(
                "Game Over",
                f"No more moves!\n\n"
                f"Pegs Remaining: {pegs}\n"
                f"Try again!",
                icon='info'
            )
            self.game_over_flag = True
            return True
        
        return False
    
    def update_status(self, status):
        self.status_label.config(text=f"● {status}")
        if "Victory" in status:
            self.status_label.config(fg="#16c79a")
        elif "Game Over" in status:
            self.status_label.config(fg="#e74c3c")
        elif "Auto" in status:
            self.status_label.config(fg="#f39c12")
        else:
            self.status_label.config(fg=self.colors['accent'])
    
    def update_stats(self):
        pegs = sum(row.count(1) for row in self.board)
        self.pegs_count = pegs
        self.move_label.config(text=f"Moves: {self.move_count}")
        self.pegs_label.config(text=f"Pegs: {pegs}")
    
    def restart(self):
        if self.auto_play_running:
            self.auto_play_running = False
        self.initial_board()
        self.draw_board()
        self.update_stats()


# ---------------- MAIN ----------------
if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("950x720")
    root.resizable(False, False)
    
    # Center window
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')
    
    # Show dialog
    dialog = VersionSelectionDialog(root)
    
    if dialog.result:
        PegSolitaireGUI(root, dialog.result)
        root.mainloop()                                              
