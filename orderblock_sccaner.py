"""
NSE Order Block Scanner - Desktop Application
Standalone Python app using Tkinter
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import yfinance as yf
import pandas as pd
from datetime import datetime
import threading
import time

# ============================================================================
# CONFIGURATION
# ============================================================================

SAMPLE_STOCKS = [
    "TCS.NS", "INFY.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "WIPRO.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "HINDUNILVR.NS",
    "LT.NS", "AXISBANK.NS", "KOTAKBANK.NS", "MARUTI.NS", "TITAN.NS",
    "ASIANPAINT.NS", "BAJFINANCE.NS", "ULTRACEMCO.NS", "NESTLEIND.NS", "HCLTECH.NS"
]

MIN_BULLISH_MOVE = 0.02
LOOKBACK_CANDLES = 50
ZONE_TOUCH_TOLERANCE = 0.001

# ============================================================================
# DATA FETCHING AND ANALYSIS FUNCTIONS
# ============================================================================

def fetch_stock_data(symbol):
    """Fetch stock data from Yahoo Finance"""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="60d", interval="1h")
        
        if df.empty:
            return None
        
        # Resample to 4H
        df = df.resample('4H').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).dropna()
        
        return df
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None


def detect_bullish_order_block(df):
    """Detect the last bullish order block"""
    if df is None or len(df) < 5:
        return None
    
    recent_df = df.tail(LOOKBACK_CANDLES).copy()
    recent_df['is_bearish'] = recent_df['Close'] < recent_df['Open']
    recent_df['is_bullish'] = recent_df['Close'] > recent_df['Open']
    recent_df['next_high'] = recent_df['High'].shift(-1)
    recent_df['move_percent'] = (recent_df['next_high'] - recent_df['Low']) / recent_df['Low']
    
    order_blocks = []
    
    for i in range(len(recent_df) - 3):
        current = recent_df.iloc[i]
        next_candle = recent_df.iloc[i + 1]
        
        if (current['is_bearish'] and 
            next_candle['is_bullish'] and 
            current['move_percent'] >= MIN_BULLISH_MOVE):
            
            subsequent_high = recent_df.iloc[i+1:i+4]['High'].max()
            if (subsequent_high - current['Low']) / current['Low'] >= MIN_BULLISH_MOVE:
                order_blocks.append({
                    'zone_high': current['High'],
                    'zone_low': current['Low'],
                    'timestamp': recent_df.index[i],
                    'strength': current['move_percent']
                })
    
    if order_blocks:
        return order_blocks[-1]
    return None


def check_zone_interaction(current_price, current_low, current_high, zone_high, zone_low):
    """Check if current candle is touching or inside the zone"""
    tolerance = zone_high * ZONE_TOUCH_TOLERANCE
    
    if zone_low <= current_price <= zone_high:
        return "Inside Zone"
    
    if (current_low - tolerance <= zone_high <= current_high + tolerance or
        current_low - tolerance <= zone_low <= current_high + tolerance):
        return "Touching Zone"
    
    if current_low > zone_high:
        return "Above Zone"
    
    return "Below Zone"


# ============================================================================
# MAIN APPLICATION CLASS
# ============================================================================

class OrderBlockScannerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NSE Order Block Scanner")
        self.root.geometry("1200x700")
        self.root.configure(bg='white')
        
        # Variables
        self.scan_results = []
        self.is_scanning = False
        self.stock_list = SAMPLE_STOCKS.copy()
        
        # Create UI
        self.create_ui()
        
    def create_ui(self):
        """Create the user interface"""
        
        # ===== HEADER =====
        header_frame = tk.Frame(self.root, bg='#2c3e50', height=80)
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        title_label = tk.Label(
            header_frame,
            text="📊 NSE Order Block Scanner",
            font=("Arial", 24, "bold"),
            bg='#2c3e50',
            fg='white'
        )
        title_label.pack(pady=20)
        
        # ===== MAIN CONTAINER =====
        main_container = tk.Frame(self.root, bg='white')
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # ===== LEFT PANEL (Controls) =====
        left_panel = tk.Frame(main_container, bg='#ecf0f1', width=300)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))
        left_panel.pack_propagate(False)
        
        # Settings Label
        settings_label = tk.Label(
            left_panel,
            text="⚙️ Settings",
            font=("Arial", 16, "bold"),
            bg='#ecf0f1',
            fg='#2c3e50'
        )
        settings_label.pack(pady=(20, 10), padx=20, anchor='w')
        
        # Stock List Selection
        stock_list_label = tk.Label(
            left_panel,
            text="Stock List:",
            font=("Arial", 10, "bold"),
            bg='#ecf0f1',
            fg='#2c3e50'
        )
        stock_list_label.pack(pady=(10, 5), padx=20, anchor='w')
        
        self.use_custom_var = tk.BooleanVar(value=False)
        custom_check = tk.Checkbutton(
            left_panel,
            text="Use Custom List",
            variable=self.use_custom_var,
            command=self.toggle_custom_list,
            bg='#ecf0f1',
            font=("Arial", 9)
        )
        custom_check.pack(padx=20, anchor='w')
        
        # Custom stock input
        self.custom_text = tk.Text(left_panel, height=8, width=30, font=("Arial", 9))
        self.custom_text.pack(pady=10, padx=20)
        self.custom_text.insert('1.0', "TCS\nINFY\nRELIANCE\nHDFCBANK\nICICIBANK")
        self.custom_text.config(state=tk.DISABLED)
        
        # Stock count label
        self.stock_count_label = tk.Label(
            left_panel,
            text=f"📈 Scanning {len(self.stock_list)} stocks",
            font=("Arial", 9),
            bg='#ecf0f1',
            fg='#27ae60'
        )
        self.stock_count_label.pack(padx=20, anchor='w')
        
        # Separator
        ttk.Separator(left_panel, orient='horizontal').pack(fill=tk.X, pady=20, padx=20)
        
        # Filter Options
        filter_label = tk.Label(
            left_panel,
            text="🔍 Filter:",
            font=("Arial", 10, "bold"),
            bg='#ecf0f1',
            fg='#2c3e50'
        )
        filter_label.pack(pady=(0, 5), padx=20, anchor='w')
        
        self.filter_var = tk.StringVar(value="All Scanned")
        filter_options = ["All Scanned", "Inside Zone Only", "Inside or Touching", "Active Zones"]
        
        for option in filter_options:
            rb = tk.Radiobutton(
                left_panel,
                text=option,
                variable=self.filter_var,
                value=option,
                command=self.apply_filter,
                bg='#ecf0f1',
                font=("Arial", 9)
            )
            rb.pack(padx=30, anchor='w')
        
        # Separator
        ttk.Separator(left_panel, orient='horizontal').pack(fill=tk.X, pady=20, padx=20)
        
        # Scan Button
        self.scan_button = tk.Button(
            left_panel,
            text="🔄 Start Scan",
            command=self.start_scan,
            bg='#27ae60',
            fg='white',
            font=("Arial", 12, "bold"),
            cursor='hand2',
            relief=tk.RAISED,
            bd=3
        )
        self.scan_button.pack(pady=10, padx=20, fill=tk.X)
        
        # Export Button
        self.export_button = tk.Button(
            left_panel,
            text="📥 Export CSV",
            command=self.export_csv,
            bg='#3498db',
            fg='white',
            font=("Arial", 10, "bold"),
            cursor='hand2',
            relief=tk.RAISED,
            bd=2,
            state=tk.DISABLED
        )
        self.export_button.pack(pady=5, padx=20, fill=tk.X)
        
        # Info Box
        info_frame = tk.LabelFrame(
            left_panel,
            text="ℹ️ Info",
            bg='#ecf0f1',
            font=("Arial", 9, "bold"),
            fg='#2c3e50'
        )
        info_frame.pack(pady=20, padx=20, fill=tk.BOTH)
        
        info_text = tk.Label(
            info_frame,
            text="Order Block Logic:\n\n"
                 "• Bearish candle before\n  strong bullish move\n\n"
                 "• Zone = High-Low range\n  of that candle\n\n"
                 "• Active = Price touching\n  or inside zone",
            font=("Arial", 8),
            bg='#ecf0f1',
            fg='#34495e',
            justify=tk.LEFT
        )
        info_text.pack(padx=10, pady=10)
        
        # ===== RIGHT PANEL (Results) =====
        right_panel = tk.Frame(main_container, bg='white')
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Status Frame
        status_frame = tk.Frame(right_panel, bg='white')
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.status_label = tk.Label(
            status_frame,
            text="Ready to scan. Click 'Start Scan' to begin.",
            font=("Arial", 11),
            bg='white',
            fg='#7f8c8d',
            anchor='w'
        )
        self.status_label.pack(side=tk.LEFT, fill=tk.X)
        
        # Progress Bar
        self.progress = ttk.Progressbar(
            status_frame,
            mode='determinate',
            length=300
        )
        self.progress.pack(side=tk.RIGHT, padx=10)
        self.progress.pack_forget()  # Hide initially
        
        # Metrics Frame
        self.metrics_frame = tk.Frame(right_panel, bg='white')
        self.metrics_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Create metric boxes
        self.metric_boxes = {}
        metrics = [
            ("Total Scanned", "#3498db"),
            ("Inside Zone", "#27ae60"),
            ("Touching Zone", "#f39c12"),
            ("Other", "#95a5a6")
        ]
        
        for idx, (label, color) in enumerate(metrics):
            box = tk.Frame(self.metrics_frame, bg=color, relief=tk.RAISED, bd=2)
            box.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            
            value_label = tk.Label(box, text="0", font=("Arial", 20, "bold"), bg=color, fg='white')
            value_label.pack(pady=(10, 0))
            
            name_label = tk.Label(box, text=label, font=("Arial", 9), bg=color, fg='white')
            name_label.pack(pady=(0, 10))
            
            self.metric_boxes[label] = value_label
        
        self.metrics_frame.pack_forget()  # Hide initially
        
        # Results Table Frame
        table_frame = tk.Frame(right_panel, bg='white')
        table_frame.pack(fill=tk.BOTH, expand=True)
        
        # Table Label
        self.table_label = tk.Label(
            table_frame,
            text="📋 Results",
            font=("Arial", 14, "bold"),
            bg='white',
            fg='#2c3e50',
            anchor='w'
        )
        self.table_label.pack(pady=(0, 10), anchor='w')
        
        # Create a container for tree and scrollbars
        tree_container = tk.Frame(table_frame, bg='white')
        tree_container.pack(fill=tk.BOTH, expand=True)
        
        # Create Treeview
        columns = ("Symbol", "Price", "Zone Low", "Zone High", "Zone Range", "Status", "Detected", "Strength")
        self.tree = ttk.Treeview(tree_container, columns=columns, show='headings', height=20)
        
        # Define column headings and widths
        col_widths = {
            "Symbol": 80,
            "Price": 90,
            "Zone Low": 90,
            "Zone High": 90,
            "Zone Range": 140,
            "Status": 110,
            "Detected": 140,
            "Strength": 80
        }
        
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=col_widths[col], anchor='center')
        
        # Add scrollbars
        vsb = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_container, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Grid layout for table and scrollbars
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        
        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)
        
        # Configure row colors
        self.tree.tag_configure('inside', background='#d4edda')
        self.tree.tag_configure('touching', background='#fff3cd')
        self.tree.tag_configure('other', background='white')
        
    def toggle_custom_list(self):
        """Toggle custom stock list input"""
        if self.use_custom_var.get():
            self.custom_text.config(state=tk.NORMAL)
        else:
            self.custom_text.config(state=tk.DISABLED)
            
    def update_stock_list(self):
        """Update the stock list based on selection"""
        if self.use_custom_var.get():
            custom_stocks = self.custom_text.get('1.0', tk.END).strip().split('\n')
            self.stock_list = [s.strip() + ".NS" for s in custom_stocks if s.strip()]
        else:
            self.stock_list = SAMPLE_STOCKS.copy()
        
        self.stock_count_label.config(text=f"📈 Scanning {len(self.stock_list)} stocks")
        
    def start_scan(self):
        """Start the scanning process in a separate thread"""
        if self.is_scanning:
            messagebox.showwarning("Scanning", "A scan is already in progress!")
            return
        
        self.update_stock_list()
        
        if not self.stock_list:
            messagebox.showerror("Error", "Stock list is empty!")
            return
        
        # Clear previous results
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        self.scan_results = []
        self.is_scanning = True
        self.scan_button.config(state=tk.DISABLED, bg='#95a5a6')
        self.export_button.config(state=tk.DISABLED)
        self.status_label.config(text="Scanning in progress...", fg='#e67e22')
        self.progress['value'] = 0
        self.progress['maximum'] = len(self.stock_list)
        self.progress.pack(side=tk.RIGHT, padx=10)
        
        # Start scan in thread
        thread = threading.Thread(target=self.scan_stocks)
        thread.daemon = True
        thread.start()
        
    def scan_stocks(self):
        """Scan stocks for order blocks"""
        results = []
        
        for idx, symbol in enumerate(self.stock_list):
            # Update progress
            self.root.after(0, self.update_progress, idx + 1, symbol)
            
            df = fetch_stock_data(symbol)
            
            if df is None or len(df) < 10:
                continue
            
            order_block = detect_bullish_order_block(df)
            
            if order_block is None:
                continue
            
            current_candle = df.iloc[-1]
            current_price = current_candle['Close']
            current_low = current_candle['Low']
            current_high = current_candle['High']
            
            status = check_zone_interaction(
                current_price, current_low, current_high,
                order_block['zone_high'], order_block['zone_low']
            )
            
            results.append({
                'Symbol': symbol.replace('.NS', ''),
                'Price': round(current_price, 2),
                'Zone Low': round(order_block['zone_low'], 2),
                'Zone High': round(order_block['zone_high'], 2),
                'Zone Range': f"{round(order_block['zone_low'], 2)} - {round(order_block['zone_high'], 2)}",
                'Status': status,
                'Detected': order_block['timestamp'].strftime('%Y-%m-%d %H:%M'),
                'Strength': f"{order_block['strength']*100:.1f}%"
            })
            
            time.sleep(0.1)
        
        self.scan_results = results
        self.root.after(0, self.scan_complete)
        
    def update_progress(self, value, symbol):
        """Update progress bar and status"""
        self.progress['value'] = value
        self.status_label.config(text=f"Scanning {symbol}... ({value}/{len(self.stock_list)})")
        
    def scan_complete(self):
        """Handle scan completion"""
        self.is_scanning = False
        self.scan_button.config(state=tk.NORMAL, bg='#27ae60')
        self.progress.pack_forget()
        
        if not self.scan_results:
            self.status_label.config(
                text="Scan completed. No order blocks detected.",
                fg='#e74c3c'
            )
            messagebox.showinfo("Scan Complete", "No order blocks detected in the scanned stocks.")
            return
        
        self.status_label.config(
            text=f"Scan completed! Found {len(self.scan_results)} stocks with order blocks.",
            fg='#27ae60'
        )
        
        self.export_button.config(state=tk.NORMAL)
        self.display_results()
        self.update_metrics()
        self.metrics_frame.pack(fill=tk.X, pady=(0, 10))
        
        messagebox.showinfo("Scan Complete", f"Found {len(self.scan_results)} stocks with order blocks!")
        
    def display_results(self):
        """Display results in the table"""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Apply filter
        filter_option = self.filter_var.get()
        
        for result in self.scan_results:
            # Apply filter
            if filter_option == "Inside Zone Only" and result['Status'] != "Inside Zone":
                continue
            elif filter_option == "Inside or Touching" and result['Status'] not in ["Inside Zone", "Touching Zone"]:
                continue
            elif filter_option == "Active Zones" and result['Status'] not in ["Inside Zone", "Touching Zone"]:
                continue
            
            # Determine tag for coloring
            if result['Status'] == "Inside Zone":
                tag = 'inside'
            elif result['Status'] == "Touching Zone":
                tag = 'touching'
            else:
                tag = 'other'
            
            # Insert into tree
            self.tree.insert('', tk.END, values=(
                result['Symbol'],
                result['Price'],
                result['Zone Low'],
                result['Zone High'],
                result['Zone Range'],
                result['Status'],
                result['Detected'],
                result['Strength']
            ), tags=(tag,))
            
    def apply_filter(self):
        """Apply filter to displayed results"""
        if self.scan_results:
            self.display_results()
            self.update_metrics()
            
    def update_metrics(self):
        """Update metric boxes"""
        total = len(self.scan_results)
        inside = len([r for r in self.scan_results if r['Status'] == "Inside Zone"])
        touching = len([r for r in self.scan_results if r['Status'] == "Touching Zone"])
        other = total - inside - touching
        
        self.metric_boxes["Total Scanned"].config(text=str(total))
        self.metric_boxes["Inside Zone"].config(text=str(inside))
        self.metric_boxes["Touching Zone"].config(text=str(touching))
        self.metric_boxes["Other"].config(text=str(other))
        
    def export_csv(self):
        """Export results to CSV"""
        if not self.scan_results:
            messagebox.showwarning("Export", "No results to export!")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"nse_orderblock_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        if filename:
            try:
                df = pd.DataFrame(self.scan_results)
                df.to_csv(filename, index=False)
                messagebox.showinfo("Export Success", f"Results exported to:\n{filename}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export:\n{str(e)}")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def main():
    root = tk.Tk()
    app = OrderBlockScannerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()