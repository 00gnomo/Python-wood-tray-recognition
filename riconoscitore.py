import numpy as np
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import os
import sys
import threading
import time
import cv2
import RPi.GPIO as GPIO  # Importa la libreria GPIO per Raspberry Pi
import pygame  # Per la riproduzione di suoni

# Configurazione GPIO per i LED e pulsante
LED_VERDE = 17  # Pin GPIO per LED verde (OK)
LED_ROSSO = 27  # Pin GPIO per LED rosso (Difetti)
PULSANTE = 25   # Pin GPIO per pulsante Next

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

def main():
    # Verifica le dipendenze richieste
    try:
        import cv2
        import numpy as np
        from PIL import Image, ImageTk
        import pygame
    except ImportError as e:
        print(f"ERRORE: Manca una dipendenza richiesta: {e}")
        print("Installa le dipendenze con: pip install opencv-python numpy pillow pygame")
        sys.exit(1)

    # Configura i GPIO
    setup_gpio()
    
    # Inizializza pygame per i suoni
    pygame.mixer.init()
    
    root = tk.Tk()
    root.title("Riconoscitore Difetti - Raspberry Pi")
    root.geometry("1200x800")
    
    # Crea e configura l'applicazione
    app = RiconoscitoreDifetti(root)
    
    # Avvia il loop principale
    root.mainloop()
    
    # Cleanup GPIO quando si chiude l'applicazione
    GPIO.cleanup()

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
        
        # Lista delle immagini nella cartella e indice corrente
        self.image_folder = "img"
        self.image_files = []
        self.current_image_index = -1
        self.load_image_list()
        
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
        
        # Stato complessivo della scatola
        self.all_components_ok = True
        
        # Thread per il monitoraggio del pulsante
        self.button_thread = None
        self.button_running = False
        
        # Caricamento dei suoni
        self.setup_sounds()
        
        # Crea l'interfaccia utente
        self.create_widgets()
        
        # Testo iniziale per l'applicazione
        self.log("Applicazione avviata. Premi 'Prossima Immagine' per analizzare le immagini nella cartella.")
        
        # Avvia il thread di monitoraggio del pulsante
        self.start_button_monitoring()
        
        # Imposta la routine di chiusura
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def setup_sounds(self):
        """Configura i suoni utilizzati nell'applicazione."""
        self.sounds = {}
        
        # Crea cartella dei suoni se non esiste
        sound_folder = "sounds"
        if not os.path.exists(sound_folder):
            os.makedirs(sound_folder)
            self.log(f"Cartella {sound_folder} creata.")
        
        # Percorsi dei file audio
        self.sound_files = {
            "next": os.path.join(sound_folder, "next.wav"),
            "ok": os.path.join(sound_folder, "ok.wav"),
            "error": os.path.join(sound_folder, "error.wav")
        }
        
        # Verifica e crea suoni di default se mancanti
        self.check_default_sounds()
        
        # Carica i suoni
        try:
            for name, path in self.sound_files.items():
                if os.path.exists(path):
                    self.sounds[name] = pygame.mixer.Sound(path)
                    self.log(f"Suono '{name}' caricato.")
                else:
                    self.log(f"File suono '{path}' non trovato.")
        except Exception as e:
            self.log(f"Errore nel caricamento dei suoni: {str(e)}")
    
    def check_default_sounds(self):
        """Verifica se i suoni di default esistono e li crea se necessario."""
        # Controllo se è necessario utilizzare beep di sistema
        try:
            import winsound
            self.has_winsound = True
        except ImportError:
            self.has_winsound = False
        
        # Questa è solo una verifica, i file audio devono essere forniti manualmente
        # o si utilizzeranno i beep di sistema su Windows o pygame su Linux
        for name, path in self.sound_files.items():
            if not os.path.exists(path):
                self.log(f"Suono '{name}' mancante. Verrà utilizzato un suono alternativo.")
    
    def load_image_list(self):
        """Carica la lista delle immagini dalla cartella."""
        try:
            # Verifica che la cartella esista
            if not os.path.exists(self.image_folder):
                os.makedirs(self.image_folder)
                self.log(f"Cartella {self.image_folder} creata perché non esisteva.")
            
            # Ottieni tutti i file immagine dalla cartella
            valid_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
            self.image_files = [
                f for f in os.listdir(self.image_folder) 
                if os.path.isfile(os.path.join(self.image_folder, f)) and 
                os.path.splitext(f)[1].lower() in valid_extensions
            ]
            
            # Ordina i file alfabeticamente
            self.image_files.sort()
            
            if not self.image_files:
                self.log(f"Nessuna immagine trovata nella cartella {self.image_folder}.")
            else:
                self.log(f"Trovate {len(self.image_files)} immagini nella cartella {self.image_folder}.")
            
            # Reset dell'indice corrente e dello stato della scatola
            self.current_image_index = -1
            self.all_components_ok = True
                
        except Exception as e:
            self.log(f"Errore nel caricamento delle immagini: {str(e)}")
    
    def reset_analysis(self):
        """Resetta l'analisi completa e torna alla prima immagine."""
        self.all_components_ok = True
        self.current_image_index = -1
        
        # Spegni i LED
        self.turn_off_leds()
        
        # Cancella risultati precedenti
        for area in self.area_results:
            self.area_results[area] = {"ok": True, "difetti": [], "percentuale": 0.0}
            self.results_tree.item(area, values=(area.replace("_", " ").title(), "N/A", "", ""))
        
        # Cancella il canvas
        self.canvas.delete("all")
        self.canvas.create_text(350, 300, text="Premi 'Prossima Immagine' per iniziare", fill="gray", font=("Arial", 14))
        
        # Reset etichette
        self.image_label.config(text="Nessuna immagine selezionata")
        self.progress_label.config(text=f"0/{len(self.image_files)}")
        
        self.log("Analisi resettata. Pronto per una nuova analisi.")
    
    def create_widgets(self):
        # Crea un menu in alto
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Menu File
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Ricarica Lista Immagini", command=self.load_image_list)
        file_menu.add_command(label="Salva Immagine Corrente", command=self.save_current_image)
        file_menu.add_separator()
        file_menu.add_command(label="Esci", command=self.root.quit)
        
        # Crea un frame principale diviso in due parti
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Pannello sinistro (visualizzazione immagine)
        left_frame = ttk.LabelFrame(main_paned, text="Visualizzazione")
        main_paned.add(left_frame, weight=3)
        
        # Canvas per mostrare l'immagine
        self.canvas = tk.Canvas(left_frame, bg="#e0e0e0", width=700, height=600)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.canvas.create_text(350, 300, text="Premi 'Prossima Immagine' per iniziare", fill="gray", font=("Arial", 14))
        
        # Pannello destro (controlli)
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)
        
        # Frame per controlli
        control_frame = ttk.LabelFrame(right_frame, text="Controlli")
        control_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Pulsante per passare all'immagine successiva
        self.next_button = ttk.Button(
            control_frame, 
            text="Prossima Immagine", 
            command=self.next_image
        )
        self.next_button.pack(fill=tk.X, padx=10, pady=10)
        
        # Reset analisi completa
        reset_button = ttk.Button(
            control_frame, 
            text="Reset Analisi", 
            command=self.reset_analysis
        )
        reset_button.pack(fill=tk.X, padx=10, pady=10)
        
        # Etichetta per mostrare il nome dell'immagine corrente
        self.image_label = ttk.Label(control_frame, text="Nessuna immagine selezionata")
        self.image_label.pack(padx=10, pady=5)
        
        # Etichetta per mostrare il progresso
        self.progress_label = ttk.Label(control_frame, text="0/0")
        self.progress_label.pack(padx=10, pady=5)
        
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
        
        # Stato dei LED
        led_frame = ttk.LabelFrame(control_frame, text="Stato LED")
        led_frame.pack(fill=tk.X, padx=10, pady=10)
        
        led_status_frame = ttk.Frame(led_frame)
        led_status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Indicatore LED Verde (OK)
        self.led_green_indicator = tk.Canvas(led_status_frame, width=20, height=20, bg="lightgray")
        self.led_green_indicator.pack(side=tk.LEFT, padx=5)
        self.led_green_indicator.create_oval(2, 2, 18, 18, fill="lightgray", outline="black", tags="green_led")
        ttk.Label(led_status_frame, text="LED Verde (OK)").pack(side=tk.LEFT, padx=5)
        
        # Indicatore LED Rosso (Difetti)
        led_status_frame2 = ttk.Frame(led_frame)
        led_status_frame2.pack(fill=tk.X, padx=5, pady=5)
        
        self.led_red_indicator = tk.Canvas(led_status_frame2, width=20, height=20, bg="lightgray")
        self.led_red_indicator.pack(side=tk.LEFT, padx=5)
        self.led_red_indicator.create_oval(2, 2, 18, 18, fill="lightgray", outline="black", tags="red_led")
        ttk.Label(led_status_frame2, text="LED Rosso (Difetti)").pack(side=tk.LEFT, padx=5)
        
        # Pulsanti per il controllo manuale dei LED
        led_buttons_frame = ttk.Frame(led_frame)
        led_buttons_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(led_buttons_frame, text="Test LED Verde", 
                 command=lambda: self.test_led(LED_VERDE)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(led_buttons_frame, text="Test LED Rosso", 
                 command=lambda: self.test_led(LED_ROSSO)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(led_buttons_frame, text="Spegni LED", 
                 command=self.turn_off_leds).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
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
        self.results_tree.column("Difetti", width=80)
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
    
    def next_image(self):
        """Passa all'immagine successiva nella cartella e la analizza."""
        if not self.image_files:
            messagebox.showinfo("Info", "Nessuna immagine disponibile nella cartella.")
            return
        
        self.current_image_index = (self.current_image_index + 1) % len(self.image_files)
        image_file = self.image_files[self.current_image_index]
        self.image_path = os.path.join(self.image_folder, image_file)
        
        try:
            self.original_image = cv2.imread(self.image_path)
            
            if self.original_image is None:
                raise ValueError(f"Impossibile leggere l'immagine {image_file}")
            
            # Aggiorna le etichette
            self.image_label.config(text=f"Immagine: {image_file}")
            self.progress_label.config(text=f"{self.current_image_index + 1}/{len(self.image_files)}")
            
            # Visualizza l'immagine caricata
            self.display_image(self.original_image)
            
            # Processa l'immagine
            self.process_image()
            
            self.log(f"Analisi immagine: {image_file}")
            
            # Se questa è l'ultima immagine, verifica lo stato complessivo
            if self.current_image_index == len(self.image_files) - 1:
                self.check_all_components()
            
        except Exception as e:
            # Riproduci suono di errore
            self.log(f"Errore nel caricamento dell'immagine {image_file}: {str(e)}")
    
    def check_all_components(self):
        """Verifica se tutti i componenti sono OK e attiva i LED appropriati."""
        # Controlla se ci sono stati difetti in tutte le immagini analizzate
        if self.all_components_ok:
            self.log("RISULTATO FINALE: Tutti i componenti della scatola sono OK")
            self.turn_on_led(LED_VERDE)
            self.update_led_indicators(LED_VERDE)
            # Riproduci suono positivo
        else:
            self.log("RISULTATO FINALE: Rilevati difetti in alcuni componenti della scatola")
            self.turn_on_led(LED_ROSSO)
            self.update_led_indicators(LED_ROSSO)
            # Riproduci suono errore
    
    def turn_on_led(self, led_pin):
        """Accende il LED specificato e spegne l'altro."""
        # Spegni entrambi i LED
        GPIO.output(LED_VERDE, GPIO.LOW)
        GPIO.output(LED_ROSSO, GPIO.LOW)
        
        # Accendi il LED specifico
        GPIO.output(led_pin, GPIO.HIGH)
    
    def turn_off_leds(self):
        """Spegne entrambi i LED."""
        GPIO.output(LED_VERDE, GPIO.LOW)
        GPIO.output(LED_ROSSO, GPIO.LOW)
        
        # Aggiorna indicatori visivi
        self.led_green_indicator.itemconfig("green_led", fill="lightgray")
        self.led_red_indicator.itemconfig("red_led", fill="lightgray")
        
        self.log("LED spenti")
    
    def test_led(self, led_pin):
        """Testa il LED specifico accendendolo per 2 secondi."""
        # Accendi il LED specificato
        self.turn_on_led(led_pin)
        
        # Aggiorna indicatori visivi
        self.update_led_indicators(led_pin)
        
        # Messaggio di log
        led_name = "verde" if led_pin == LED_VERDE else "rosso"
        self.log(f"Test LED {led_name} attivo")
        
        # Programma lo spegnimento dopo 2 secondi
        self.root.after(2000, self.turn_off_leds)
    
    def update_led_indicators(self, active_led):
        """Aggiorna gli indicatori visivi dei LED nell'interfaccia."""
        # Aggiorna indicatore LED Verde
        if active_led == LED_VERDE:
            self.led_green_indicator.itemconfig("green_led", fill="green")
            self.led_red_indicator.itemconfig("red_led", fill="lightgray")
        # Aggiorna indicatore LED Rosso
        elif active_led == LED_ROSSO:
            self.led_green_indicator.itemconfig("green_led", fill="lightgray")
            self.led_red_indicator.itemconfig("red_led", fill="red")
    
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
    
    def save_current_image(self):
        """Salva l'immagine correntemente visualizzata."""
        if self.current_view is None or self.current_view not in self.processed_images:
            messagebox.showwarning("Attenzione", "Nessuna immagine disponibile da salvare.")
            return
        
        file_path = f"risultato_{os.path.basename(self.image_path)}"
        
        try:
            # Crea una cartella per i risultati se non esiste
            result_folder = "risultati"
            if not os.path.exists(result_folder):
                os.makedirs(result_folder)
            
            # Percorso completo per il salvataggio
            save_path = os.path.join(result_folder, file_path)
            
            # Salva l'immagine corrente
            cv2.imwrite(save_path, self.processed_images[self.current_view])
            self.log(f"Immagine salvata: {save_path}")
            
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile salvare l'immagine: {str(e)}")
            self.log(f"Errore nel salvataggio dell'immagine: {str(e)}")
            
    def process_image(self):
        """Elabora l'immagine corrente con segmentazione avanzata."""
        if self.original_image is None:
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
            
            # Se ci sono difetti, imposta la flag per l'intero controllo della scatola su False
            if is_defective:
                self.all_components_ok = False
            
            # Aggiorna il TreeView con i risultati per ogni area
            for area, data in self.area_results.items():
                status = "OK" if data["ok"] else "DIFETTATO"
                difetti_str = ", ".join(data["difetti"]) if data["difetti"] else "Nessuno"
                percentuale_str = f"{data['percentuale']:.2f}%"
                
                self.results_tree.item(area, values=(area.replace("_", " ").title(), status, difetti_str, percentuale_str))
            
            # Aggiorna il combobox con le viste disponibili
            self.view_options.config(values=list(self.processed_images.keys()))
            
            # Passa alla vista "Risultato Analisi"
            self.view_var.set("Risultato Analisi")
            self.display_image(self.processed_images["Risultato Analisi"])
            self.current_view = "Risultato Analisi"
            
            # Log dei risultati
            self.log(f"Analisi completata. Stato dell'immagine: {status_text}. {total_defect_percent:.2f}% area totale difettata.")
        
        except Exception as e:
            self.log(f"Errore durante l'elaborazione dell'immagine: {str(e)}")
            messagebox.showerror("Errore", f"Si è verificato un errore durante l'elaborazione: {str(e)}")