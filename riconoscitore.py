import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import os
import sys
import threading
import time
<<<<<<< Updated upstream
=======
import cv2
import RPi.GPIO as GPIO  # Importa la libreria GPIO per Raspberry Pi
import pygame  # Per la riproduzione di suoni

# Configurazione GPIO per i LED e pulsante
LED_VERDE = 17  # Pin GPIO per LED verde (OK)
LED_ROSSO = 27  # Pin GPIO per LED rosso (Difetti)
PULSANTE = 25   # Pin GPIO per pulsante Next
print("FANCULO ALLE VERIFICHE DI SISTEMI W IL JIGSAW")
def setup_gpio():
    """Configura i pin GPIO per i LED e pulsante."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    
    # Configura i pin LED come output
    GPIO.setup(LED_VERDE, GPIO.OUT)
    GPIO.setup(LED_ROSSO, GPIO.OUT)
    
    # Configura il pin pulsante come input con pull-up
    GPIO.setup(PULSANTE, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    # Inizialmente spegni entrambi i LED
    GPIO.output(LED_VERDE, GPIO.LOW)
    GPIO.output(LED_ROSSO, GPIO.LOW)
>>>>>>> Stashed changes

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
    root.title("Riconoscitore Difetti - Webcam")
    root.geometry("1000x700")
    
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
        left_frame = ttk.LabelFrame(main_paned, text="Visualizzazione Webcam")
        main_paned.add(left_frame, weight=3)
        
        # Canvas per mostrare l'immagine
        self.canvas = tk.Canvas(left_frame, bg="#e0e0e0", width=600, height=500)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.canvas.create_text(300, 250, text="Avvia la webcam per iniziare", fill="gray", font=("Arial", 14))
        
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
        results_frame = ttk.LabelFrame(control_frame, text="Risultati Analisi")
        results_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.dark_area_var = tk.StringVar(value="Area scura: N/A")
        dark_area_label = ttk.Label(results_frame, textvariable=self.dark_area_var)
        dark_area_label.pack(anchor=tk.W, padx=5, pady=2)
        
        self.bright_area_var = tk.StringVar(value="Area chiara: N/A")
        bright_area_label = ttk.Label(results_frame, textvariable=self.bright_area_var)
        bright_area_label.pack(anchor=tk.W, padx=5, pady=2)
        
        self.total_area_var = tk.StringVar(value="Area difettata totale: N/A")
        total_area_label = ttk.Label(results_frame, textvariable=self.total_area_var)
        total_area_label.pack(anchor=tk.W, padx=5, pady=2)
        
        self.status_var = tk.StringVar(value="Stato: N/A")
        self.status_label = ttk.Label(results_frame, textvariable=self.status_var)
        self.status_label.pack(anchor=tk.W, padx=5, pady=2)
        
        # Log delle operazioni
        log_frame = ttk.LabelFrame(right_frame, text="Log")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.log_text = tk.Text(log_frame, wrap=tk.WORD, height=10, width=30)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        log_scrollbar = ttk.Scrollbar(self.log_text, orient=tk.VERTICAL, command=self.log_text.yview)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=log_scrollbar.set)
    
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
                canvas_width = 600
                canvas_height = 500
            
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
        
<<<<<<< Updated upstream
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
        self.canvas.create_text(300, 250, text="Webcam fermata", fill="gray", font=("Arial", 14))
        
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
    
    def process_image(self):
        """Elabora l'immagine corrente."""
        if self.original_image is None:
            messagebox.showwarning("Attenzione", "Nessuna immagine disponibile per l'analisi.")
            return
        
        try:
            # Converti in scala di grigi
            gray_image = cv2.cvtColor(self.original_image, cv2.COLOR_BGR2GRAY)
            
            # Reset delle immagini elaborate
            self.processed_images = {}
            self.processed_images["Originale"] = self.original_image.copy()
            
            # Applica una colormap JET (default)
            colormap = cv2.COLORMAP_JET
            colored_image = cv2.applyColorMap(gray_image, colormap)
            self.processed_images["Colormap JET"] = colored_image
            
            # Rileva zone scure
            dark_image, dark_mask, dark_percent = self.detect_dark_regions(gray_image, self.soglia_colore_scuro)
            self.processed_images["Zone Scure"] = dark_image
            
            # Rileva zone chiare/rosse
            bright_image, bright_mask, bright_percent = self.detect_bright_regions(gray_image, self.soglia_colore_chiaro)
            self.processed_images["Zone Chiare"] = bright_image
            
            # Crea un'immagine combinata che mostra entrambi i tipi di difetti
            combined_image, combined_mask, total_percent = self.combine_defects(
                gray_image, dark_mask, bright_mask, dark_percent, bright_percent)
            self.processed_images["Difetti Combinati"] = combined_image
            
            # Aggiungi le maschere alle visualizzazioni
            self.processed_images["Maschera Zone Scure"] = cv2.cvtColor(dark_mask, cv2.COLOR_GRAY2BGR)
            self.processed_images["Maschera Zone Chiare"] = cv2.cvtColor(bright_mask, cv2.COLOR_GRAY2BGR)
            self.processed_images["Maschera Combinata"] = cv2.cvtColor(combined_mask, cv2.COLOR_GRAY2BGR)
            
            # Determina se il pezzo è difettato (basato sull'area difettata totale)
            is_defective = total_percent > self.soglia_difetti
            status_text = "DIFETTATO" if is_defective else "OK"
            
            # Aggiorna i risultati dell'analisi
            # Usiamo tk.CallAfter per aggiornare l'UI in modo thread-safe
            self.root.after(0, lambda: self.dark_area_var.set(f"Area scura: {dark_percent:.2f}%"))
            self.root.after(0, lambda: self.bright_area_var.set(f"Area chiara: {bright_percent:.2f}%"))
            self.root.after(0, lambda: self.total_area_var.set(f"Area difettata totale: {total_percent:.2f}%"))
            self.root.after(0, lambda: self.status_var.set(f"Stato: {status_text}"))
            
            # Imposta lo stato con colore
            if is_defective:
                self.root.after(0, lambda: self.status_label.config(foreground="red"))
            else:
                self.root.after(0, lambda: self.status_label.config(foreground="green"))
            
            # Aggiorna il combobox con le viste disponibili
            self.root.after(0, lambda: self.view_options.config(values=list(self.processed_images.keys())))
            
            # Passa alla vista "Difetti Combinati"
            self.root.after(0, lambda: self.view_var.set("Difetti Combinati"))
            self.root.after(0, lambda: self.display_image(self.processed_images["Difetti Combinati"]))
            self.current_view = "Difetti Combinati"
            
            # Log dei risultati (utilizzando after per essere thread-safe)
            self.root.after(0, lambda: self.log(
                f"Analisi completata. Area scura: {dark_percent:.2f}%, Area chiara: {bright_percent:.2f}%, "
                f"Totale: {total_percent:.2f}%. Stato: {status_text}"))
            
        except Exception as e:
            self.log(f"Errore durante l'elaborazione: {str(e)}")
            messagebox.showerror("Errore", f"Si è verificato un errore: {str(e)}")
    
    def detect_dark_regions(self, gray_image, threshold=50):
        """Rileva le regioni scure e calcola la percentuale."""
        # Applica soglia per individuare le aree scure
        _, threshold_image = cv2.threshold(gray_image, threshold, 255, cv2.THRESH_BINARY_INV)
        
        # Operazioni morfologiche per migliorare il rilevamento
        kernel = np.ones((5, 5), np.uint8)
        processed_mask = cv2.morphologyEx(threshold_image, cv2.MORPH_OPEN, kernel)
        
        # Calcola la percentuale di area scura
        total_pixels = processed_mask.shape[0] * processed_mask.shape[1]
        dark_pixels = cv2.countNonZero(processed_mask)
        dark_percent = (dark_pixels / total_pixels) * 100
        
        # Crea un'immagine a colori per evidenziare le aree scure
        contours, _ = cv2.findContours(processed_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        result_image = cv2.cvtColor(gray_image, cv2.COLOR_GRAY2BGR)
        cv2.drawContours(result_image, contours, -1, (0, 0, 255), 2)  # Contorni rossi per zone scure
        
        # Aggiungi testo con la percentuale e parametri
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(result_image, f"Area scura: {dark_percent:.2f}%", (10, 30), 
                   font, 0.7, (0, 0, 255), 2)
        cv2.putText(result_image, f"Soglia scuro: {threshold}", (10, 60), 
                   font, 0.7, (255, 255, 0), 2)
        
        return result_image, processed_mask, dark_percent
    
    def detect_bright_regions(self, gray_image, threshold=200):
        """Rileva le regioni chiare e calcola la percentuale."""
        # Applica soglia per individuare le aree chiare
        _, threshold_image = cv2.threshold(gray_image, threshold, 255, cv2.THRESH_BINARY)
        
        # Operazioni morfologiche per migliorare il rilevamento
        kernel = np.ones((5, 5), np.uint8)
        processed_mask = cv2.morphologyEx(threshold_image, cv2.MORPH_OPEN, kernel)
        
        # Calcola la percentuale di area chiara
        total_pixels = processed_mask.shape[0] * processed_mask.shape[1]
        bright_pixels = cv2.countNonZero(processed_mask)
        bright_percent = (bright_pixels / total_pixels) * 100
        
        # Crea un'immagine a colori per evidenziare le aree chiare
        contours, _ = cv2.findContours(processed_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        result_image = cv2.cvtColor(gray_image, cv2.COLOR_GRAY2BGR)
        cv2.drawContours(result_image, contours, -1, (0, 255, 0), 2)  # Contorni verdi per zone chiare
        
        # Aggiungi testo con la percentuale e parametri
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(result_image, f"Area chiara: {bright_percent:.2f}%", (10, 30), 
                   font, 0.7, (0, 255, 0), 2)
        cv2.putText(result_image, f"Soglia chiaro: {threshold}", (10, 60), 
                   font, 0.7, (255, 255, 0), 2)
        
        return result_image, processed_mask, bright_percent
    
    def combine_defects(self, gray_image, dark_mask, bright_mask, dark_percent, bright_percent):
        """Combina le maschere dei difetti scuri e chiari."""
        # Combina le maschere con OR
        combined_mask = cv2.bitwise_or(dark_mask, bright_mask)
        
        # Ricalcola la percentuale totale (poiché potrebbero esserci sovrapposizioni)
        total_pixels = combined_mask.shape[0] * combined_mask.shape[1]
        defect_pixels = cv2.countNonZero(combined_mask)
        total_percent = (defect_pixels / total_pixels) * 100
        
        # Crea un'immagine a colori per evidenziare tutte le aree difettate
        result_image = cv2.cvtColor(gray_image, cv2.COLOR_GRAY2BGR)
        
        # Disegna contorni per zone scure (rosso)
        contours_dark, _ = cv2.findContours(dark_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(result_image, contours_dark, -1, (0, 0, 255), 2)
        
        # Disegna contorni per zone chiare (verde)
        contours_bright, _ = cv2.findContours(bright_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(result_image, contours_bright, -1, (0, 255, 0), 2)
        
        # Crea un overlay colorato per visualizzare meglio le aree difettate
        overlay = result_image.copy()
        # Colora aree scure in blu semi-trasparente
        overlay[dark_mask > 0] = [255, 0, 0]  # BGR: blu
        # Colora aree chiare in verde semi-trasparente
        overlay[bright_mask > 0] = [0, 255, 0]  # BGR: verde
        
        # Combina con l'immagine originale
        alpha = 0.3  # Trasparenza dell'overlay
        cv2.addWeighted(overlay, alpha, result_image, 1 - alpha, 0, result_image)
        
        # Aggiungi testo con percentuali e parametri
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(result_image, f"Area scura: {dark_percent:.2f}%", (10, 30), 
                   font, 0.7, (0, 0, 255), 2)
        cv2.putText(result_image, f"Area chiara: {bright_percent:.2f}%", (10, 60), 
                   font, 0.7, (0, 255, 0), 2)
        cv2.putText(result_image, f"Area totale difettata: {total_percent:.2f}%", (10, 90), 
                   font, 0.7, (255, 255, 255), 2)
        
        status_text = "DIFETTATO" if total_percent > self.soglia_difetti else "OK"
        status_color = (0, 0, 255) if total_percent > self.soglia_difetti else (0, 255, 0)
        cv2.putText(result_image, f"Stato: {status_text}", (10, 120), 
                   font, 0.7, status_color, 2)
        
        return result_image, combined_mask, total_percent
=======
        # Spegni i LED prima di uscire
        self.turn_off_leds()
        self.root.destroy()


# Esegue il programma principale se lo script viene eseguito direttamente
>>>>>>> Stashed changes
