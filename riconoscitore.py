import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import os
import sys
import threading
import time
import cv2  # Import cv2 globally so it's available for all methods

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
        self.is_analyzing = False  # Flag per analisi continua
        self.capture_thread = None
        self.analysis_thread = None
        self.camera_index = 0  # Indice della webcam (0 = predefinita)
        self.available_cameras = []  # Lista delle webcam disponibili
        
        # Variabile per controllare la frequenza di aggiornamento dell'analisi
        self.last_analysis_time = 0
        self.analysis_interval = 0.5  # Secondi tra le analisi (default: 0.5s)
        
        # Buffer per ridurre lo sfarfallio
        self.frame_buffer = []
        self.buffer_size = 5 # Numero di frame da mediare
        
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
        
        # Rileva le webcam disponibili
        self.detect_cameras()
        
        # Crea l'interfaccia utente
        self.create_widgets()
        
        # Testo iniziale per l'applicazione
        self.log("Applicazione avviata. Seleziona una webcam e premi 'Avvia webcam' per iniziare.")
        
        # Imposta la routine di chiusura
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def detect_cameras(self):
        """Rileva le webcam disponibili nel sistema."""
        self.available_cameras = []
        
        # Prova diversi indici di camera fino a quando non fallisce l'apertura
        max_cameras = 10  # Limite massimo di tentativi
        
        for i in range(max_cameras):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                # Ottieni il nome della webcam se possibile
                ret, frame = cap.read()
                if ret:
                    name = f"Webcam {i}"
                    # In alcuni sistemi, è possibile ottenere il nome della webcam
                    try:
                        name = cap.getBackendName() + f" ({i})"
                    except:
                        pass
                    self.available_cameras.append((i, name))
                cap.release()
            else:
                break
        
        if not self.available_cameras:
            self.available_cameras.append((0, "Webcam predefinita"))
    
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
        
        # Selettore webcam
        camera_frame = ttk.Frame(webcam_frame)
        camera_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(camera_frame, text="Seleziona webcam: ").pack(side=tk.LEFT)
        
        self.camera_var = tk.StringVar()
        camera_names = [name for idx, name in self.available_cameras]
        if camera_names:
            self.camera_var.set(camera_names[0])
        
        self.camera_combo = ttk.Combobox(camera_frame, textvariable=self.camera_var, 
                                        values=camera_names, state="readonly")
        self.camera_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        self.start_button = ttk.Button(webcam_frame, text="Avvia Webcam", command=self.start_webcam)
        self.start_button.pack(fill=tk.X, padx=10, pady=5)
        
        self.stop_button = ttk.Button(webcam_frame, text="Ferma Webcam", command=self.stop_webcam, state=tk.DISABLED)
        self.stop_button.pack(fill=tk.X, padx=10, pady=5)
        
        # Checkbox per analisi continua
        self.continuous_analyze_var = tk.BooleanVar(value=False)
        self.continuous_analyze_check = ttk.Checkbutton(
            webcam_frame, 
            text="Analisi continua (LIVE)", 
            variable=self.continuous_analyze_var,
            command=self.toggle_continuous_analyze
        )
        self.continuous_analyze_check.pack(fill=tk.X, padx=10, pady=5)
        
        # Frame per la frequenza di analisi
        freq_frame = ttk.Frame(webcam_frame)
        freq_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(freq_frame, text="Intervallo analisi (sec): ").pack(side=tk.LEFT)
        
        self.analysis_interval_var = tk.DoubleVar(value=self.analysis_interval)
        freq_spinbox = ttk.Spinbox(freq_frame, from_=0.1, to=5.0, increment=0.1, 
                                 textvariable=self.analysis_interval_var, width=5,
                                 command=self.update_analysis_interval)
        freq_spinbox.pack(side=tk.LEFT, padx=5)
        
        # Frame per le impostazioni di buffering
        buffer_frame = ttk.Frame(webcam_frame)
        buffer_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(buffer_frame, text="Buffer anti-flickering: ").pack(side=tk.LEFT)
        
        self.buffer_size_var = tk.IntVar(value=self.buffer_size)
        buffer_spinbox = ttk.Spinbox(buffer_frame, from_=1, to=10, increment=1, 
                                   textvariable=self.buffer_size_var, width=5,
                                   command=self.update_buffer_size)
        buffer_spinbox.pack(side=tk.LEFT, padx=5)
        
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
    
    def update_buffer_size(self, event=None):
        """Aggiorna la dimensione del buffer anti-flickering."""
        new_size = self.buffer_size_var.get()
        if new_size < 1:
            new_size = 1
        elif new_size > 10:
            new_size = 10
        
        self.buffer_size = new_size
        self.buffer_size_var.set(new_size)
        
        # Svuota il buffer esistente
        self.frame_buffer = []
    
    def update_analysis_interval(self, event=None):
        """Aggiorna l'intervallo di tempo tra le analisi continue."""
        self.analysis_interval = self.analysis_interval_var.get()
    
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
            # Ottieni l'indice della webcam selezionata
            selected_camera = self.camera_var.get()
            camera_index = 0  # Default
            
            for idx, name in self.available_cameras:
                if name == selected_camera:
                    camera_index = idx
                    break
            
            # Inizializza la webcam
            self.capture = cv2.VideoCapture(camera_index)
            
            # Imposta risoluzione più alta se possibile
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            
            if not self.capture.isOpened():
                messagebox.showerror("Errore", f"Impossibile accedere alla webcam {selected_camera}.")
                self.log(f"Errore: Impossibile accedere alla webcam {selected_camera}.")
                return
            
            # Imposta flag di cattura
            self.is_capturing = True
            
            # Svuota il buffer dei frame
            self.frame_buffer = []
            
            # Attiva/disattiva i pulsanti
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.camera_combo.config(state=tk.DISABLED)
            
            # Avvia il thread di cattura
            self.capture_thread = threading.Thread(target=self.update_webcam_feed)
            self.capture_thread.daemon = True
            self.capture_thread.start()
            
            # Se l'analisi continua è attivata, avviala subito
            if self.continuous_analyze_var.get():
                self.toggle_continuous_analyze()
            
            self.log(f"Webcam {selected_camera} avviata.")
            
        except Exception as e:
            messagebox.showerror("Errore", f"Errore nell'avvio della webcam: {str(e)}")
            self.log(f"Errore nell'avvio della webcam: {str(e)}")
    
    def update_webcam_feed(self):
        """Aggiorna il feed della webcam in modo continuo. Versione migliorata con gestione ottimizzata."""
        last_display_time = 0
        display_interval = 1.0 / 30  # Limita a 30 fps per il display
        
        while self.is_capturing:
            try:
                # Leggi un frame dalla webcam
                ret, frame = self.capture.read()
                
                if not ret:
                    self.log("Errore nella lettura del frame dalla webcam.")
                    time.sleep(0.1)  # Piccola pausa prima di riprovare
                    continue
                
                # Specchia orizzontalmente il frame (più naturale per l'utente)
                frame = cv2.flip(frame, 1)
                
                # Aggiungi il frame al buffer
                self.frame_buffer.append(frame)
                
                # Mantieni il buffer alla giusta dimensione
                while len(self.frame_buffer) > self.buffer_size:
                    self.frame_buffer.pop(0)
                
                # Limita la frequenza di aggiornamento del display per evitare flickering
                current_time = time.time()
                enough_frames = len(self.frame_buffer) >= max(2, self.buffer_size // 2)
                
                if (current_time - last_display_time >= display_interval) and enough_frames:
                    # Stabilizzazione del frame (media dei frame nel buffer)
                    stabilized_frame = self.stabilize_frames(self.frame_buffer)
                    
                    # Visualizza il frame stabilizzato
                    self.display_webcam_frame(stabilized_frame)
                    
                    # Aggiorna il timestamp dell'ultimo display
                    last_display_time = current_time
                    
                    # Se l'analisi è continua, usa questo frame per l'analisi
                    if self.is_analyzing:
                        if current_time - self.last_analysis_time > self.analysis_interval:
                            self.original_image = stabilized_frame.copy()
                            # Elabora l'immagine in un thread separato
                            if (self.analysis_thread is None or 
                                not self.analysis_thread.is_alive()):
                                self.analysis_thread = threading.Thread(target=self.process_image)
                                self.analysis_thread.daemon = True
                                self.analysis_thread.start()
                                self.last_analysis_time = current_time
                
                # Pausa adattiva basata sul framerate target
                time.sleep(max(0.001, display_interval - (time.time() - current_time)))
                    
            except Exception as e:
                self.log(f"Errore nell'aggiornamento del feed webcam: {str(e)}")
                time.sleep(0.1)  # Pausa per evitare loop di errore rapidi
        
        # Rilascia la webcam quando esco dal ciclo
        if self.capture is not None and self.is_capturing == False:
            self.capture.release()
    
    def stabilize_frames(self, frames):
        """Stabilizza una serie di frame facendone la media per ridurre lo sfarfallio.
        Versione migliorata con pesi e controlli aggiuntivi."""
        if not frames:
            return None
        
        # Se c'è solo un frame, restituiscilo direttamente
        if len(frames) == 1:
            return frames[0]
        
        # Verifica che tutti i frame abbiano la stessa dimensione
        height, width = frames[0].shape[:2]
        for frame in frames[1:]:
            if frame.shape[0] != height or frame.shape[1] != width:
                # Se le dimensioni sono diverse, restituisci l'ultimo frame
                return frames[-1]
    
        # Applica pesi crescenti ai frame più recenti per una transizione più fluida
        # Questo dà più importanza ai frame più recenti riducendo il ritardo percepito
        total_weight = 0
        weighted_sum = np.zeros_like(frames[0], dtype=np.float32)
        
        for i, frame in enumerate(frames):
            # Usa un peso esponenziale (i frame più recenti hanno peso maggiore)
            weight = 1.5 ** i  # Il frame più recente avrà il peso maggiore
            weighted_sum += frame.astype(np.float32) * weight
            total_weight += weight
        
        # Normalizza per i pesi
        avg_frame = weighted_sum / total_weight
        
        # Applica un leggero filtro bilaterale per preservare i bordi ma ridurre il rumore
        avg_frame = cv2.bilateralFilter(avg_frame.astype(np.uint8), 5, 35, 35)
        
        return avg_frame.astype(np.uint8)
    
    def display_webcam_frame(self, frame):
        """Visualizza un frame dalla webcam nel canvas. Versione migliorata con double buffering."""
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
            
            # Applica una leggera sfocatura gaussiana per ridurre il rumore ad alta frequenza
            # che può causare flickering (valori bassi preservano i dettagli)
            frame_denoised = cv2.GaussianBlur(frame, (3, 3), 0.5)
            
            # Ridimensiona il frame
            resized = cv2.resize(frame_denoised, (new_width, new_height), interpolation=cv2.INTER_AREA)
            
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
        # Disattiva l'analisi continua se attiva
        if self.is_analyzing:
            self.is_analyzing = False
            self.continuous_analyze_var.set(False)
        
        self.is_capturing = False
        
        # Attendi che il thread di cattura termini
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(1.0)  # Attendi max 1 secondo
        
        # Rilascia la webcam
        if self.capture is not None:
            self.capture.release()
            self.capture = None
        
        # Svuota il buffer dei frame
        self.frame_buffer = []
        
        # Ripristina l'interfaccia
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.camera_combo.config(state="readonly")
        
        # Cancella il canvas
        self.canvas.delete("all")
        self.canvas.create_text(350, 300, text="Webcam fermata", fill="gray", font=("Arial", 14))
        
        self.log("Webcam fermata.")
    
    def toggle_continuous_analyze(self):
        """Attiva/disattiva l'analisi continua."""
        is_active = self.continuous_analyze_var.get()
        
        if is_active and self.is_capturing:
            self.is_analyzing = True
            self.last_analysis_time = 0  # Forza l'analisi immediata
            self.log(f"Analisi continua LIVE attivata con intervallo di {self.analysis_interval:.1f} secondi.")
        else:
            self.is_analyzing = False
            if is_active and not self.is_capturing:
                self.log("La webcam deve essere avviata per l'analisi continua.")
                self.continuous_analyze_var.set(False)
            else:
                self.log("Analisi continua LIVE disattivata.")
    
    def capture_and_analyze(self):
        """Cattura un frame dalla webcam e lo analizza manualmente."""
        if not self.is_capturing or self.capture is None:
            messagebox.showwarning("Attenzione", "La webcam non è attiva.")
            return
        
        try:
            # Se ci sono abbastanza frame nel buffer, usa la versione stabilizzata
            if len(self.frame_buffer) >= self.buffer_size:
                # Stabilizzazione del frame (media dei frame nel buffer)
                stabilized_frame = self.stabilize_frames(self.frame_buffer)
                self.original_image = stabilized_frame.copy()
            else:
                # Altrimenti, leggi un nuovo frame
                ret, frame = self.capture.read()
                if not ret:
                    messagebox.showerror("Errore", "Impossibile catturare il frame dalla webcam.")
                    return
                    
                # Specchia orizzontalmente il frame
                frame = cv2.flip(frame, 1)
                self.original_image = frame.copy()
            
            # Processa l'immagine
            self.process_image()
            
            self.log("Immagine catturata e analizzata.")
            
        except Exception as e:
            self.log(f"Errore durante la cattura: {str(e)}")
            messagebox.showerror("Errore", f"Si è verificato un errore: {str(e)}")
    
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
        
    def process_image(self):
        """Elabora l'immagine corrente con segmentazione avanzata."""
        if self.original_image is None:
            # Nessun messagebox in modalità thread
            self.log("Attenzione: Nessuna immagine disponibile per l'analisi.")
            return
        
        try:
            # Reset dei risultati dell'analisi
            for area in self.area_results:
                self.area_results[area] = {"ok": True, "difetti": [], "percentuale": 0.0}
            
            # Reset delle immagini elaborate
            self.processed_images = {}
            self.processed_images["Originale"] = self.original_image.copy()
            
            # Segmenta l'immagine in 5 aree (base + 4 lati)
            segmented_img, regions = self.segment_image(self.original_image)
            self.processed_images["Segmentazione"] = segmented_img
            
            # Converti l'immagine originale in scala di grigi
            gray_image = cv2.cvtColor(self.original_image, cv2.COLOR_BGR2GRAY)
            
            # Applica una colormap JET (per visualizzazione)
            colormap = cv2.COLORMAP_JET
            colored_image = cv2.applyColorMap(gray_image, colormap)
            self.processed_images["Colormap JET"] = colored_image
            
            # Analisi per ogni regione
            self.analyze_region("base", regions["base"], "base")
            self.analyze_region("lato_superiore", regions["lato_superiore"], "lato")
            self.analyze_region("lato_destro", regions["lato_destro"], "lato")
            self.analyze_region("lato_inferiore", regions["lato_inferiore"], "lato")
            self.analyze_region("lato_sinistro", regions["lato_sinistro"], "lato")
            
            # Crea un'immagine con i risultati combinati
            combined_result = self.original_image.copy()
            
            # Disegna rettangoli colorati in base allo stato di ogni regione
            for area, data in self.area_results.items():
                region_data = regions[area]
                x1, y1, x2, y2 = region_data["coords"]
                
                # Colore verde per regioni OK, rosso per difettate
                color = (0, 255, 0) if data["ok"] else (0, 0, 255)
                cv2.rectangle(combined_result, (x1, y1), (x2, y2), color, 2)
                
                # Aggiungi testo con percentuale difetti
                text = f"{area.replace('_', ' ').title()}: {data['percentuale']:.1f}%"
                cv2.putText(combined_result, text, (x1 + 5, y1 + 20), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            
            self.processed_images["Risultato Analisi"] = combined_result
            
            # Crea un'immagine combinata di tutti i difetti
            total_defect_mask = np.zeros_like(gray_image)
            for area, data in self.area_results.items():
                if "mask" in data and data["mask"] is not None:
                    # Estrai la regione dalla maschera totale
                    x1, y1, x2, y2 = regions[area]["coords"]
                    region_mask = np.zeros_like(gray_image)
                    region_mask[y1:y2, x1:x2] = data["mask"]
                    total_defect_mask = cv2.bitwise_or(total_defect_mask, region_mask)
            
            # Crea visualizzazione maschere
            defect_visualization = self.original_image.copy()
            defect_visualization[total_defect_mask > 0] = [0, 0, 255]  # Colora i difetti in rosso
            self.processed_images["Maschera Difetti"] = defect_visualization
            
            # Calcola percentuale totale di difetti
            total_pixels = gray_image.shape[0] * gray_image.shape[1]
            defect_pixels = cv2.countNonZero(total_defect_mask)
            total_defect_percent = (defect_pixels / total_pixels) * 100 if total_pixels > 0 else 0
            
            # Determina lo stato complessivo del prodotto
            is_defective = any(not data["ok"] for data in self.area_results.values())
            status_text = "DIFETTATO" if is_defective else "OK"
            
            # Aggiorna il TreeView con i risultati per ogni area
            for area, data in self.area_results.items():
                status = "OK" if data["ok"] else "DIFETTATO"
                difetti_str = ", ".join(data["difetti"]) if data["difetti"] else "Nessuno"
                percentuale_str = f"{data['percentuale']:.2f}%"
                
                # Usiamo root.after per essere thread-safe
                area_copy, status_copy, difetti_copy, perc_copy = area, status, difetti_str, percentuale_str
                self.root.after(0, lambda a=area_copy, s=status_copy, d=difetti_copy, p=perc_copy: 
                               self.results_tree.item(a, values=(a.replace("_", " ").title(), s, d, p)))
            
            # Aggiorna il combobox con le viste disponibili
            self.root.after(0, lambda: self.view_options.config(values=list(self.processed_images.keys())))
            
            # Passa alla vista "Risultato Analisi" se non è già in modalità continua
            if not self.is_analyzing or not self.current_view:
                self.root.after(0, lambda: self.view_var.set("Risultato Analisi"))
                self.root.after(0, lambda: self.display_image(self.processed_images["Risultato Analisi"]))
                self.current_view = "Risultato Analisi"
            elif self.current_view in self.processed_images:
                # Aggiorna la vista corrente
                self.root.after(0, lambda: self.display_image(self.processed_images[self.current_view]))
            
            # Log dei risultati (solo se non in analisi continua o ogni 5 secondi in analisi continua)
            if not self.is_analyzing or (time.time() % 5) < 1:
                self.root.after(0, lambda: self.log(
                    f"Analisi completata. Stato complessivo: {status_text}. {total_defect_percent:.2f}% area totale difettata."))
            
        except Exception as e:
            self.log(f"Errore durante l'elaborazione: {str(e)}")
    
    def analyze_region(self, region_name, region_data, region_type):
        """Analizza una regione specifica dell'immagine e identifica i difetti."""
        if region_data["img"] is None:
            self.area_results[region_name]["ok"] = False
            self.area_results[region_name]["difetti"].append("Regione mancante")
            self.area_results[region_name]["percentuale"] = 100.0
            return
        
        img = region_data["img"]
        result_mask = None
        defect_percentage = 0.0
        defects = []
        
        # Converti in scala di grigi se necessario
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()
        
        # 1. Analisi per zone scure (buchi, nodi, ecc.)
        dark_mask = self.detect_dark_features(gray)
        
        # 2. Analisi per zone chiare/rosse
        bright_mask = self.detect_bright_features(gray)
        
        # 3. Analisi dei bordi/contorni (per lati storti o danneggiati)
        edge_mask = None
        if region_type == "lato":
            edge_mask = self.detect_edge_issues(gray)
        
        # Combina le maschere per ottenere una maschera totale dei difetti
        combined_mask = np.zeros_like(gray)
        if dark_mask is not None:
            combined_mask = cv2.bitwise_or(combined_mask, dark_mask)
        if bright_mask is not None:
            combined_mask = cv2.bitwise_or(combined_mask, bright_mask)
        if edge_mask is not None:
            combined_mask = cv2.bitwise_or(combined_mask, edge_mask)
        
        # Calcola la percentuale di area difettata
        total_pixels = gray.shape[0] * gray.shape[1]
        if total_pixels > 0:
            defect_pixels = cv2.countNonZero(combined_mask)
            defect_percentage = (defect_pixels / total_pixels) * 100
        
        # Determina i tipi di difetti presenti
        if dark_mask is not None and cv2.countNonZero(dark_mask) > 0:
            if region_type == "base":
                defects.append("Nodi/buchi scuri")
            else:
                defects.append("Zone scure")
        
        if bright_mask is not None and cv2.countNonZero(bright_mask) > 0:
            if region_type == "base":
                defects.append("Irregolarità chiare")
            else:
                defects.append("Zone chiare/danneggiate")
        
        if edge_mask is not None and cv2.countNonZero(edge_mask) > 0:
            defects.append("Bordi irregolari/storti")
        
        # Determina se la regione è OK o difettata (basato sulla percentuale)
        is_ok = defect_percentage <= self.soglia_difetti
        
        # Salva i risultati
        self.area_results[region_name]["ok"] = is_ok
        self.area_results[region_name]["difetti"] = defects
        self.area_results[region_name]["percentuale"] = defect_percentage
        self.area_results[region_name]["mask"] = combined_mask
        
        # Crea visualizzazione per questa regione
        region_result = None
        if len(img.shape) == 3:
            region_result = img.copy()
            # Sovrapponi maschera in rosso
            overlay = img.copy()
            overlay[combined_mask > 0] = [0, 0, 255]  # Rosso
            cv2.addWeighted(overlay, 0.5, region_result, 0.5, 0, region_result)
            
            # Aggiungi informazioni
            cv2.putText(region_result, f"{region_name.replace('_', ' ').title()}", (10, 20), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
            cv2.putText(region_result, f"Difetti: {defect_percentage:.2f}%", (10, 40), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255) if not is_ok else (0, 255, 0), 2)
        
        # Salva l'immagine elaborata nelle viste disponibili
        if region_result is not None:
            self.processed_images[f"Analisi {region_name.replace('_', ' ').title()}"] = region_result
    
    def detect_dark_features(self, gray_img):
        """Rileva caratteristiche scure come buchi, nodi, ecc."""
        # Applica soglia per individuare le aree scure
        _, threshold_img = cv2.threshold(gray_img, self.soglia_colore_scuro, 255, cv2.THRESH_BINARY_INV)
        
        # Operazioni morfologiche per migliorare il rilevamento
        kernel = np.ones((3, 3), np.uint8)
        processed_mask = cv2.morphologyEx(threshold_img, cv2.MORPH_OPEN, kernel)
        
        # Filtra aree troppo piccole (rumore)
        contours, _ = cv2.findContours(processed_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_area = 10  # Area minima in pixel
        filtered_mask = np.zeros_like(processed_mask)
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area >= min_area:
                cv2.drawContours(filtered_mask, [contour], -1, 255, -1)
        
        return filtered_mask
    
    def detect_bright_features(self, gray_img):
        """Rileva caratteristiche chiare/rosse come graffi, danni, ecc."""
        # Applica soglia per individuare le aree chiare
        _, threshold_img = cv2.threshold(gray_img, self.soglia_colore_chiaro, 255, cv2.THRESH_BINARY)
        
        # Operazioni morfologiche per migliorare il rilevamento
        kernel = np.ones((3, 3), np.uint8)
        processed_mask = cv2.morphologyEx(threshold_img, cv2.MORPH_OPEN, kernel)
        
        # Filtra aree troppo piccole (rumore)
        contours, _ = cv2.findContours(processed_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_area = 10  # Area minima in pixel
        filtered_mask = np.zeros_like(processed_mask)
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area >= min_area:
                cv2.drawContours(filtered_mask, [contour], -1, 255, -1)
        
        return filtered_mask
    
    def detect_bright_features(self, gray_img):
            """Rileva caratteristiche chiare/rosse come graffi, danni, ecc."""
            # Applica soglia per individuare le aree chiare
            _, threshold_img = cv2.threshold(gray_img, self.soglia_colore_chiaro, 255, cv2.THRESH_BINARY)
            
            # Operazioni morfologiche per migliorare il rilevamento
            kernel = np.ones((3, 3), np.uint8)
            processed_mask = cv2.morphologyEx(threshold_img, cv2.MORPH_OPEN, kernel)
            
            # Filtra aree troppo piccole (rumore)
            contours, _ = cv2.findContours(processed_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            min_area = 10  # Area minima in pixel
            filtered_mask = np.zeros_like(processed_mask)
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if area >= min_area:
                    cv2.drawContours(filtered_mask, [contour], -1, 255, -1)
            
            return filtered_mask
    
    def detect_edge_issues(self, gray_img):
        """Rileva problemi nei bordi come lati storti o danneggiati."""
        # Applica Canny per rilevare i bordi
        edges = cv2.Canny(gray_img, self.soglia_canny_min, self.soglia_canny_max)
        
        # Dilata i bordi per una migliore visualizzazione
        kernel = np.ones((3, 3), np.uint8)
        dilated_edges = cv2.dilate(edges, kernel, iterations=1)
        
        # Trova linee con Hough Transform
        lines = cv2.HoughLinesP(dilated_edges, 1, np.pi/180, 50, minLineLength=30, maxLineGap=10)
        
        # Crea una maschera per memorizzare le aree problematiche
        edge_mask = np.zeros_like(gray_img)
        
        # Se ci sono linee, analizzale
        if lines is not None:
            # Calcola l'orientamento principale delle linee
            angles = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                if x2 - x1 == 0:  # Evita divisione per zero
                    angle = 90
                else:
                    angle = np.abs(np.arctan((y2 - y1) / (x2 - x1)) * 180 / np.pi)
                angles.append(angle)
            
            # Trova l'angolo mediano (orientamento principale)
            median_angle = np.median(angles) if angles else 0
            
            # Identifica linee che deviano significativamente dall'orientamento principale
            threshold_angle = 15  # Soglia di deviazione in gradi
            for line in lines:
                x1, y1, x2, y2 = line[0]
                if x2 - x1 == 0:
                    angle = 90
                else:
                    angle = np.abs(np.arctan((y2 - y1) / (x2 - x1)) * 180 / np.pi)
                
                # Se la linea devia dall'orientamento principale, marcala come problematica
                if np.abs(angle - median_angle) > threshold_angle:
                    cv2.line(edge_mask, (x1, y1), (x2, y2), 255, 2)
        
        return edge_mask
    
    def display_image(self, image):
            """Visualizza un'immagine nel canvas."""
            if image is None:
                return
            
            try:
                # Ottieni le dimensioni del canvas
                canvas_width = self.canvas.winfo_width()
                canvas_height = self.canvas.winfo_height()
                
                # Se il canvas non è ancora stato renderizzato, usa dimensioni di backup
                if canvas_width < 50 or canvas_height < 50:
                    canvas_width = 700
                    canvas_height = 600
                
                # Dimensioni originali dell'immagine
                height, width = image.shape[:2]
                
                # Calcola il fattore di scala per adattare l'immagine al canvas
                scale = min(canvas_width/width, canvas_height/height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                
                # Ridimensiona l'immagine
                resized = cv2.resize(image, (new_width, new_height))
                
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
                self.log(f"Errore nella visualizzazione dell'immagine: {str(e)}")
        
    def change_view(self, event=None):
            """Cambia la visualizzazione corrente."""
            view_name = self.view_var.get()
            if view_name in self.processed_images:
                self.display_image(self.processed_images[view_name])
                self.current_view = view_name
        
    def log(self, message):
            """Aggiunge un messaggio al log."""
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            log_message = f"[{timestamp}] {message}\n"
            self.log_text.insert(tk.END, log_message)
            self.log_text.see(tk.END)  # Scorre alla fine
        
    def on_close(self):
            """Funzione chiamata quando si chiude l'applicazione."""
            self.stop_webcam()
            self.root.destroy()


# Esegue il programma principale se lo script viene eseguito direttamente
if __name__ == "__main__":
    main()