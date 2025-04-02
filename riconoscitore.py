import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import os
import sys
import threading
import time

def main():
    # Verifica le dipendenze richieste
    try:
        import cv2
        import numpy as np
        from PIL import Image, ImageTk
    except ImportError as e:
        print(f"ERRORE: Manca una dipendenza richiesta: {e}")
        print("Installa le dipendenze con: pip install opencv-python numpy pillow")
        sys.exit(1)

    root = tk.Tk()
    root.title("Riconoscitore Difetti - Avanzato")
    root.geometry("1200x800")
    
    # Crea e configura l'applicazione
    app = RiconoscitoreDifetti(root)
    
    # Avvia il loop principale
    root.mainloop()

class RiconoscitoreDifetti:
    def __init__(self, root):
        self.root = root
        
        # Valore soglia difetti (%)
        self.soglia_difetti = 5.0
        
        # Valore soglia colore scuro (0-255)
        self.soglia_colore_scuro = 50
        
        # Valore soglia per zone chiare/rosse (0-255)
        self.soglia_colore_chiaro = 200
        
        # Valore soglia per rilevamento bordi
        self.soglia_canny_min = 50
        self.soglia_canny_max = 150
        
        # Parametri per la segmentazione
        self.base_roi_percent = 40  # % dell'immagine che rappresenta la base
        
        # Variabili per la webcam
        self.capture = None
        self.is_capturing = False
        self.capture_thread = None
        self.camera_index = 0  # Indice della webcam (0 = predefinita)
        
        # Percorso dell'immagine corrente
        self.image_path = None
        self.original_image = None
        self.processed_images = {}
        self.current_view = None
        
        # Risultati dell'analisi per area
        self.area_results = {
            "base": {"ok": True, "difetti": [], "percentuale": 0.0},
            "lato_superiore": {"ok": True, "difetti": [], "percentuale": 0.0},
            "lato_destro": {"ok": True, "difetti": [], "percentuale": 0.0},
            "lato_inferiore": {"ok": True, "difetti": [], "percentuale": 0.0},
            "lato_sinistro": {"ok": True, "difetti": [], "percentuale": 0.0}
        }
        
        # Crea l'interfaccia utente
        self.create_widgets()
        
        # Testo iniziale per l'applicazione
        self.log("Applicazione avviata. Premi 'Avvia webcam' per iniziare.")
        
        # Imposta la routine di chiusura
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def create_widgets(self):
        # Crea un menu in alto
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Menu File
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Carica Immagine", command=self.load_image)
        file_menu.add_command(label="Salva Immagine Corrente", command=self.save_current_image)
        file_menu.add_separator()
        file_menu.add_command(label="Esci", command=self.root.quit)
        
        # Menu Elaborazione
        process_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Elaborazione", menu=process_menu)
        process_menu.add_command(label="Scatta e Analizza", command=self.capture_and_analyze)
        
        # Crea un frame principale diviso in due parti
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Pannello sinistro (visualizzazione immagine)
        left_frame = ttk.LabelFrame(main_paned, text="Visualizzazione")
        main_paned.add(left_frame, weight=3)
        
        # Canvas per mostrare l'immagine
        self.canvas = tk.Canvas(left_frame, bg="#e0e0e0", width=700, height=600)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.canvas.create_text(350, 300, text="Avvia la webcam per iniziare", fill="gray", font=("Arial", 14))
        
        # Pannello destro (controlli)
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)
        
        # Frame per controlli
        control_frame = ttk.LabelFrame(right_frame, text="Controlli")
        control_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Controlli webcam
        webcam_frame = ttk.LabelFrame(control_frame, text="Controlli Webcam")
        webcam_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.start_button = ttk.Button(webcam_frame, text="Avvia Webcam", command=self.start_webcam)
        self.start_button.pack(fill=tk.X, padx=10, pady=5)
        
        self.stop_button = ttk.Button(webcam_frame, text="Ferma Webcam", command=self.stop_webcam, state=tk.DISABLED)
        self.stop_button.pack(fill=tk.X, padx=10, pady=5)
        
        self.capture_button = ttk.Button(webcam_frame, text="Scatta e Analizza", command=self.capture_and_analyze, state=tk.DISABLED)
        self.capture_button.pack(fill=tk.X, padx=10, pady=5)
        
        # Checkbox per analisi automatica
        self.auto_analyze_var = tk.BooleanVar(value=False)
        self.auto_analyze_check = ttk.Checkbutton(
            webcam_frame, 
            text="Analisi automatica continua", 
            variable=self.auto_analyze_var,
            command=self.toggle_auto_analyze
        )
        self.auto_analyze_check.pack(fill=tk.X, padx=10, pady=5)
        
        # Frame per la frequenza di analisi
        freq_frame = ttk.Frame(webcam_frame)
        freq_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(freq_frame, text="Intervallo analisi (sec): ").pack(side=tk.LEFT)
        
        self.analysis_freq_var = tk.DoubleVar(value=1.0)
        freq_spinbox = ttk.Spinbox(freq_frame, from_=0.1, to=10.0, increment=0.1, 
                                   textvariable=self.analysis_freq_var, width=5)
        freq_spinbox.pack(side=tk.LEFT, padx=5)
        
        # Controlli per parametri di segmentazione
        segment_frame = ttk.LabelFrame(control_frame, text="Parametri Segmentazione")
        segment_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(segment_frame, text="Dimensione base (%): ").pack(anchor=tk.W, padx=10, pady=5)
        self.base_roi_var = tk.IntVar(value=self.base_roi_percent)
        base_scale = ttk.Scale(segment_frame, from_=10, to=70, 
                              variable=self.base_roi_var, 
                              command=self.update_base_roi)
        base_scale.pack(fill=tk.X, padx=10, pady=5)
        
        # Soglia per la sensibilità colore SCURO
        dark_frame = ttk.LabelFrame(control_frame, text="Sensibilità Zone Scure")
        dark_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.dark_var = tk.IntVar(value=self.soglia_colore_scuro)
        dark_scale = ttk.Scale(dark_frame, from_=0, to=255, 
                              variable=self.dark_var, 
                              command=self.update_dark_threshold)
        dark_scale.pack(fill=tk.X, padx=5, pady=5)
        
        self.dark_label = ttk.Label(dark_frame, text=f"Soglia zone scure: {self.soglia_colore_scuro}")
        self.dark_label.pack(pady=5)
        
        # Soglia per la sensibilità alle zone CHIARE/ROSSE
        bright_frame = ttk.LabelFrame(control_frame, text="Sensibilità Zone Chiare/Rosse")
        bright_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.bright_var = tk.IntVar(value=self.soglia_colore_chiaro)
        bright_scale = ttk.Scale(bright_frame, from_=100, to=255, 
                                variable=self.bright_var, 
                                command=self.update_bright_threshold)
        bright_scale.pack(fill=tk.X, padx=5, pady=5)
        
        self.bright_label = ttk.Label(bright_frame, text=f"Soglia zone chiare: {self.soglia_colore_chiaro}")
        self.bright_label.pack(pady=5)
        
        # Soglia per il rilevamento dei bordi (Canny)
        edge_frame = ttk.LabelFrame(control_frame, text="Parametri Rilevamento Bordi")
        edge_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(edge_frame, text="Soglia Minima:").pack(anchor=tk.W, padx=10, pady=2)
        self.canny_min_var = tk.IntVar(value=self.soglia_canny_min)
        canny_min_scale = ttk.Scale(edge_frame, from_=0, to=255, 
                                   variable=self.canny_min_var, 
                                   command=self.update_canny_min)
        canny_min_scale.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(edge_frame, text="Soglia Massima:").pack(anchor=tk.W, padx=10, pady=2)
        self.canny_max_var = tk.IntVar(value=self.soglia_canny_max)
        canny_max_scale = ttk.Scale(edge_frame, from_=0, to=255, 
                                   variable=self.canny_max_var, 
                                   command=self.update_canny_max)
        canny_max_scale.pack(fill=tk.X, padx=10, pady=5)
        
        # Soglia per il rilevamento dei difetti complessivi
        threshold_frame = ttk.LabelFrame(control_frame, text="Soglia Difetti Totali")
        threshold_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.threshold_var = tk.DoubleVar(value=self.soglia_difetti)
        threshold_scale = ttk.Scale(threshold_frame, from_=0.1, to=30.0, 
                                   variable=self.threshold_var, 
                                   command=self.update_threshold)
        threshold_scale.pack(fill=tk.X, padx=5, pady=5)
        
        self.threshold_label = ttk.Label(threshold_frame, text=f"Soglia: {self.soglia_difetti:.1f}%")
        self.threshold_label.pack(pady=5)
        
        # Visualizzazioni disponibili
        views_frame = ttk.LabelFrame(control_frame, text="Visualizzazioni")
        views_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.view_var = tk.StringVar()
        self.view_options = ttk.Combobox(views_frame, textvariable=self.view_var, state="readonly")
        self.view_options.pack(fill=tk.X, padx=5, pady=5)
        self.view_options.bind("<<ComboboxSelected>>", self.change_view)
        
        # Risultati analisi
        results_frame = ttk.LabelFrame(right_frame, text="Risultati Analisi")
        results_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Treeview per mostrare i risultati delle diverse aree
        self.results_tree = ttk.Treeview(results_frame, columns=("Area", "Stato", "Difetti", "Percentuale"))
        self.results_tree.heading("#0", text="")
        self.results_tree.heading("Area", text="Area")
        self.results_tree.heading("Stato", text="Stato")
        self.results_tree.heading("Difetti", text="Difetti")
        self.results_tree.heading("Percentuale", text="% Difetti")
        
        self.results_tree.column("#0", width=0, stretch=False)
        self.results_tree.column("Area", width=100)
        self.results_tree.column("Stato", width=70)
        self.results_tree.column("Difetti", width=200)
        self.results_tree.column("Percentuale", width=80)
        
        self.results_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Inserisci le aree nel TreeView
        self.results_tree.insert("", "end", iid="base", values=("Base", "N/A", "", ""))
        self.results_tree.insert("", "end", iid="lato_superiore", values=("Lato Superiore", "N/A", "", ""))
        self.results_tree.insert("", "end", iid="lato_destro", values=("Lato Destro", "N/A", "", ""))
        self.results_tree.insert("", "end", iid="lato_inferiore", values=("Lato Inferiore", "N/A", "", ""))
        self.results_tree.insert("", "end", iid="lato_sinistro", values=("Lato Sinistro", "N/A", "", ""))
        
        # Log delle operazioni
        log_frame = ttk.LabelFrame(right_frame, text="Log")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_text = tk.Text(log_frame, wrap=tk.WORD, height=8, width=30)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        log_scrollbar = ttk.Scrollbar(self.log_text, orient=tk.VERTICAL, command=self.log_text.yview)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=log_scrollbar.set)
    
    def load_image(self):
        """Carica un'immagine da file."""
        file_path = filedialog.askopenfilename(
            title="Seleziona un'immagine",
            filetypes=[("Immagini", "*.jpg *.jpeg *.png *.bmp"), ("Tutti i file", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            self.image_path = file_path
            self.original_image = cv2.imread(file_path)
            
            if self.original_image is None:
                raise ValueError("Impossibile leggere l'immagine")
            
            # Visualizza l'immagine caricata
            self.display_image(self.original_image)
            
            # Processa l'immagine
            self.process_image()
            
            self.log(f"Immagine caricata: {os.path.basename(file_path)}")
            
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile caricare l'immagine: {str(e)}")
            self.log(f"Errore nel caricamento dell'immagine: {str(e)}")
    
    def save_current_image(self):
        """Salva l'immagine correntemente visualizzata."""
        if self.current_view is None or self.current_view not in self.processed_images:
            messagebox.showwarning("Attenzione", "Nessuna immagine disponibile da salvare.")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="Salva immagine come",
            defaultextension=".jpg",
            filetypes=[("JPEG", "*.jpg"), ("PNG", "*.png"), ("Tutti i file", "*.*")]
        )
        
        if not file_path:
            return
        
        try:
            # Salva l'immagine corrente
            cv2.imwrite(file_path, self.processed_images[self.current_view])
            self.log(f"Immagine salvata: {os.path.basename(file_path)}")
            
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile salvare l'immagine: {str(e)}")
            self.log(f"Errore nel salvataggio dell'immagine: {str(e)}")
    
    def update_threshold(self, event=None):
        """Aggiorna l'etichetta della soglia quando viene modificata."""
        self.soglia_difetti = self.threshold_var.get()
        self.threshold_label.config(text=f"Soglia: {self.soglia_difetti:.1f}%")
    
    def update_dark_threshold(self, event=None):
        """Aggiorna l'etichetta della soglia colore scuro quando viene modificata."""
        self.soglia_colore_scuro = self.dark_var.get()
        self.dark_label.config(text=f"Soglia zone scure: {self.soglia_colore_scuro}")
    
    def update_bright_threshold(self, event=None):
        """Aggiorna l'etichetta della soglia colore chiaro quando viene modificata."""
        self.soglia_colore_chiaro = self.bright_var.get()
        self.bright_label.config(text=f"Soglia zone chiare: {self.soglia_colore_chiaro}")
    
    def update_canny_min(self, event=None):
        """Aggiorna la soglia minima per Canny."""
        self.soglia_canny_min = self.canny_min_var.get()
    
    def update_canny_max(self, event=None):
        """Aggiorna la soglia massima per Canny."""
        self.soglia_canny_max = self.canny_max_var.get()
    
    def update_base_roi(self, event=None):
        """Aggiorna la dimensione della base ROI."""
        self.base_roi_percent = self.base_roi_var.get()
    
    def start_webcam(self):
        """Avvia la cattura dalla webcam."""
        try:
            # Inizializza la webcam
            self.capture = cv2.VideoCapture(self.camera_index)
            
            if not self.capture.isOpened():
                messagebox.showerror("Errore", "Impossibile accedere alla webcam.")
                self.log("Errore: Impossibile accedere alla webcam.")
                return
            
            # Imposta flag di cattura
            self.is_capturing = True
            
            # Attiva/disattiva i pulsanti
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.capture_button.config(state=tk.NORMAL)
            
            # Avvia il thread di cattura
            self.capture_thread = threading.Thread(target=self.update_webcam_feed)
            self.capture_thread.daemon = True
            self.capture_thread.start()
            
            self.log("Webcam avviata.")
            
        except Exception as e:
            messagebox.showerror("Errore", f"Errore nell'avvio della webcam: {str(e)}")
            self.log(f"Errore nell'avvio della webcam: {str(e)}")
    
    def update_webcam_feed(self):
        """Aggiorna il feed della webcam in modo continuo."""
        last_analysis_time = 0
        
        while self.is_capturing:
            try:
                # Leggi un frame dalla webcam
                ret, frame = self.capture.read()
                
                if not ret:
                    self.log("Errore nella lettura del frame dalla webcam.")
                    break
                
                # Specchia orizzontalmente il frame (più naturale per l'utente)
                frame = cv2.flip(frame, 1)
                
                # Visualizza il frame live
                self.display_webcam_frame(frame)
                
                # Analisi automatica se abilitata
                current_time = time.time()
                if (self.auto_analyze_var.get() and 
                    current_time - last_analysis_time > self.analysis_freq_var.get()):
                    # Salva l'ultimo frame per elaborarlo
                    self.original_image = frame.copy()
                    # Elabora l'immagine in un thread separato per non bloccare l'UI
                    analysis_thread = threading.Thread(target=self.process_image)
                    analysis_thread.daemon = True
                    analysis_thread.start()
                    last_analysis_time = current_time
                
                # Breve pausa per non sovraccaricare la CPU
                time.sleep(0.03)
                
            except Exception as e:
                self.log(f"Errore nell'aggiornamento del feed webcam: {str(e)}")
                break
        
        # Rilascia la webcam quando esco dal ciclo
        if self.capture is not None and self.is_capturing == False:
            self.capture.release()
    
    def display_webcam_frame(self, frame):
        """Visualizza un frame dalla webcam nel canvas."""
        if frame is None:
            return
        
        try:
            # Ottieni le dimensioni del canvas
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            # Se il canvas non è ancora stato renderizzato, usa dimensioni di backup
            if canvas_width < 50 or canvas_height < 50:
                canvas_width = 700
                canvas_height = 600
            
            # Dimensioni originali del frame
            height, width = frame.shape[:2]
            
            # Calcola il fattore di scala per adattare il frame al canvas
            scale = min(canvas_width/width, canvas_height/height)
            new_width = int(width * scale)
            new_height = int(height * scale)
            
            # Ridimensiona il frame
            resized = cv2.resize(frame, (new_width, new_height))
            
            # Converti da BGR a RGB per PIL
            display_image = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            
            # Converti in formato PIL
            pil_image = Image.fromarray(display_image)
            
            # Converti in formato Tkinter
            tk_image = ImageTk.PhotoImage(image=pil_image)
            
            # Salva un riferimento all'immagine (per evitare il garbage collection)
            self.tk_image = tk_image
            
            # Mostra l'immagine nel canvas
            self.canvas.delete("all")
            self.canvas.create_image(canvas_width//2, canvas_height//2, image=tk_image)
            
        except Exception as e:
            self.log(f"Errore nella visualizzazione del frame: {str(e)}")
    
    def stop_webcam(self):
        """Ferma la cattura dalla webcam."""
        self.is_capturing = False
        
        # Attendi che il thread di cattura termini
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(1.0)  # Attendi max 1 secondo
        
        # Rilascia la webcam
        if self.capture is not None:
            self.capture.release()
            self.capture = None
        
        # Ripristina l'interfaccia
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.capture_button.config(state=tk.DISABLED)
        
        # Cancella il canvas
        self.canvas.delete("all")
        self.canvas.create_text(350, 300, text="Webcam fermata", fill="gray", font=("Arial", 14))
        
        self.log("Webcam fermata.")
    
    def capture_and_analyze(self):
        """Cattura un frame dalla webcam e lo analizza."""
        if not self.is_capturing or self.capture is None:
            messagebox.showwarning("Attenzione", "La webcam non è attiva.")
            return
        
        try:
            # Leggi un frame dalla webcam
            ret, frame = self.capture.read()
            
            if not ret:
                messagebox.showerror("Errore", "Impossibile catturare il frame dalla webcam.")
                return
                
            # Specchia orizzontalmente il frame
            frame = cv2.flip(frame, 1)
            
            # Salva il frame come immagine originale
            self.original_image = frame.copy()
            
            # Processa l'immagine
            self.process_image()
            
            self.log("Immagine catturata e analizzata.")
            
        except Exception as e:
            self.log(f"Errore durante la cattura: {str(e)}")
            messagebox.showerror("Errore", f"Si è verificato un errore: {str(e)}")
    
    def toggle_auto_analyze(self):
        """Attiva/disattiva l'analisi automatica."""
        auto_analyze = self.auto_analyze_var.get()
        if auto_analyze:
            self.log(f"Analisi automatica attivata con intervallo di {self.analysis_freq_var.get():.1f} secondi.")
        else:
            self.log("Analisi automatica disattivata.")
    
    def segment_image(self, image):
        """Segmenta l'immagine in base (centro) e 4 lati (superiore, inferiore, sinistro, destro)."""
        height, width = image.shape[:2]
        
        # Calcola la dimensione del quadrato centrale (base)
        base_size = min(width, height) * self.base_roi_percent / 100
        
        # Calcola le coordinate del quadrato centrale
        center_x, center_y = width // 2, height // 2
        half_size = base_size // 2
        
        # Definisci le coordinate delle regioni (x1, y1, x2, y2)
        # Base (centro)
        base_x1 = int(center_x - half_size)
        base_y1 = int(center_y - half_size)
        base_x2 = int(center_x + half_size)
        base_y2 = int(center_y + half_size)
        
        # Lato superiore
        top_x1 = base_x1
        top_y1 = 0
        top_x2 = base_x2
        top_y2 = base_y1
        
        # Lato destro
        right_x1 = base_x2
        right_y1 = base_y1
        right_x2 = width
        right_y2 = base_y2
        
        # Lato inferiore
        bottom_x1 = base_x1
        bottom_y1 = base_y2
        bottom_x2 = base_x2
        bottom_y2 = height
        
        # Lato sinistro
        left_x1 = 0
        left_y1 = base_y1
        left_x2 = base_x1
        left_y2 = base_y2
        
        # Crea una copia dell'immagine per visualizzare la segmentazione
        segmented_img = image.copy()
        
        # Disegna rettangoli per visualizzare le regioni
        # Base (centro) - giallo
        cv2.rectangle(segmented_img, (base_x1, base_y1), (base_x2, base_y2), (0, 255, 255), 2)
        cv2.putText(segmented_img, "Base", (base_x1 + 10, base_y1 + 20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
        
        # Lato superiore - blu
        cv2.rectangle(segmented_img, (top_x1, top_y1), (top_x2, top_y2), (255, 0, 0), 2)
        cv2.putText(segmented_img, "Lato Sup", (top_x1 + 10, top_y1 + 20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        
        # Lato destro - verde
        cv2.rectangle(segmented_img, (right_x1, right_y1), (right_x2, right_y2), (0, 255, 0), 2)
        cv2.putText(segmented_img, "Lato Dx", (right_x1 + 10, right_y1 + 20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Lato inferiore - rosso
        cv2.rectangle(segmented_img, (bottom_x1, bottom_y1), (bottom_x2, bottom_y2), (0, 0, 255), 2)
        cv2.putText(segmented_img, "Lato Inf", (bottom_x1 + 10, bottom_y1 + 20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        
        # Lato sinistro - ciano
        cv2.rectangle(segmented_img, (left_x1, left_y1), (left_x2, left_y2), (255, 255, 0), 2)
        cv2.putText(segmented_img, "Lato Sx", (left_x1 + 10, left_y1 + 20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
        
        # Estrai le regioni dall'immagine originale
        base_region = image[base_y1:base_y2, base_x1:base_x2].copy()
        top_region = image[top_y1:top_y2, top_x1:top_x2].copy() if top_y2 > top_y1 else None
        right_region = image[right_y1:right_y2, right_x1:right_x2].copy() if right_x2 > right_x1 else None
        bottom_region = image[bottom_y1:bottom_y2, bottom_x1:bottom_x2].copy() if bottom_y2 > bottom_y1 else None
        left_region = image[left_y1:left_y2, left_x1:left_x2].copy() if left_x2 > left_x1 else None
        
        # Coordinate delle regioni per riferimento futuro
        regions = {
            "base": {"img": base_region, "coords": (base_x1, base_y1, base_x2, base_y2)},
            "lato_superiore": {"img": top_region, "coords": (top_x1, top_y1, top_x2, top_y2)},
            "lato_destro": {"img": right_region, "coords": (right_x1, right_y1, right_x2, right_y2)},
            "lato_inferiore": {"img": bottom_region, "coords": (bottom_x1, bottom_y1, bottom_x2, bottom_y2)},
            "lato_sinistro": {"img": left_region, "coords": (left_x1, left_y1, left_x2, left_y2)}
        }
        
        return segmented_img, regions