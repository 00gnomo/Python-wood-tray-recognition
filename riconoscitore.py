import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import os
import sys

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
    root.title("Riconoscitore Difetti")
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
        
        # Percorso dell'immagine corrente
        self.image_path = None
        self.original_image = None
        self.processed_images = {}
        self.current_view = None
        
        # Crea l'interfaccia utente
        self.create_widgets()
        
        # Testo iniziale per l'applicazione
        self.log("Applicazione avviata. Carica un'immagine per iniziare.")
    
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
        process_menu.add_command(label="Elabora Immagine", command=self.process_image)
        
        # Crea un frame principale diviso in due parti
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Pannello sinistro (visualizzazione immagine)
        left_frame = ttk.LabelFrame(main_paned, text="Visualizzazione Immagine")
        main_paned.add(left_frame, weight=3)
        
        # Canvas per mostrare l'immagine
        self.canvas = tk.Canvas(left_frame, bg="#e0e0e0", width=600, height=500)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.canvas.create_text(300, 250, text="Carica un'immagine per iniziare", fill="gray", font=("Arial", 14))
        
        # Pannello destro (controlli)
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=1)
        
        # Frame per controlli
        control_frame = ttk.LabelFrame(right_frame, text="Controlli")
        control_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Pulsante per caricare immagine
        load_button = ttk.Button(control_frame, text="Carica Immagine", command=self.load_image)
        load_button.pack(fill=tk.X, padx=10, pady=10)
        
        # Pulsante per elaborare l'immagine
        process_button = ttk.Button(control_frame, text="Elabora Immagine", command=self.process_image)
        process_button.pack(fill=tk.X, padx=10, pady=5)
        
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
        # Rielabora l'immagine se è già stata caricata
        if self.original_image is not None and "Zone Scure" in self.processed_images:
            self.process_image()
    
    def update_dark_threshold(self, event=None):
        """Aggiorna l'etichetta della soglia colore scuro quando viene modificata."""
        self.soglia_colore_scuro = self.dark_var.get()
        self.dark_label.config(text=f"Soglia zone scure: {self.soglia_colore_scuro}")
        # Rielabora l'immagine se è già stata caricata
        if self.original_image is not None and "Zone Scure" in self.processed_images:
            self.process_image()
    
    def update_bright_threshold(self, event=None):
        """Aggiorna l'etichetta della soglia colore chiaro quando viene modificata."""
        self.soglia_colore_chiaro = self.bright_var.get()
        self.bright_label.config(text=f"Soglia zone chiare: {self.soglia_colore_chiaro}")
        # Rielabora l'immagine se è già stata caricata
        if self.original_image is not None and "Zone Chiare" in self.processed_images:
            self.process_image()
    
    def load_image(self):
        """Carica un'immagine da file."""
        try:
            # Richiedi il percorso del file all'utente
            file_path = filedialog.askopenfilename(
                title="Seleziona un'immagine",
                filetypes=[
                    ("Immagini", "*.jpg *.jpeg *.png *.bmp"),
                    ("Tutti i file", "*.*")
                ]
            )
            
            # Se l'utente annulla, esci dalla funzione
            if not file_path:
                return
            
            # Carica l'immagine con OpenCV
            self.image_path = file_path
            self.original_image = cv2.imread(file_path)
            
            if self.original_image is None:
                self.log(f"Errore: Impossibile caricare l'immagine {file_path}")
                messagebox.showerror("Errore", "Impossibile caricare l'immagine selezionata.")
                return
            
            # Reset delle immagini elaborate e visualizzazioni
            self.processed_images = {}
            self.processed_images["Originale"] = self.original_image.copy()
            
            # Aggiorna il combobox con le viste disponibili
            self.view_options["values"] = ["Originale"]
            self.view_options.current(0)
            self.current_view = "Originale"
            
            # Visualizza l'immagine originale
            self.display_image(self.original_image)
            
            # Aggiorna il log
            filename = os.path.basename(file_path)
            self.log(f"Immagine caricata: {filename}")
            
            # Reset dei risultati di analisi
            self.dark_area_var.set("Area scura: N/A")
            self.bright_area_var.set("Area chiara: N/A")
            self.total_area_var.set("Area difettata totale: N/A")
            self.status_var.set("Stato: N/A")
            
        except Exception as e:
            self.log(f"Errore durante il caricamento: {str(e)}")
            messagebox.showerror("Errore", f"Si è verificato un errore: {str(e)}")
    
    def process_image(self):
        """Elabora l'immagine corrente."""
        if self.original_image is None:
            messagebox.showwarning("Attenzione", "Carica prima un'immagine.")
            return
        
        try:
            self.log("Elaborazione dell'immagine in corso...")
            
            # Converti in scala di grigi se necessario
            if len(self.original_image.shape) == 3:
                gray_image = cv2.cvtColor(self.original_image, cv2.COLOR_BGR2GRAY)
            else:
                gray_image = self.original_image.copy()
            
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
            self.dark_area_var.set(f"Area scura: {dark_percent:.2f}%")
            self.bright_area_var.set(f"Area chiara: {bright_percent:.2f}%")
            self.total_area_var.set(f"Area difettata totale: {total_percent:.2f}%")
            
            # Imposta lo stato con colore
            self.status_var.set(f"Stato: {status_text}")
            if is_defective:
                self.status_label.config(foreground="red")
            else:
                self.status_label.config(foreground="green")
            
            # Aggiorna il combobox con le viste disponibili
            self.view_options["values"] = list(self.processed_images.keys())
            
            # Passa alla vista "Difetti Combinati" se è la prima elaborazione
            if self.current_view not in self.processed_images:
                self.view_var.set("Difetti Combinati")
                self.display_image(self.processed_images["Difetti Combinati"])
                self.current_view = "Difetti Combinati"
            else:
                # Altrimenti aggiorna la vista corrente
                self.display_image(self.processed_images[self.current_view])
            
            self.log(f"Elaborazione completata. Area scura: {dark_percent:.2f}%, Area chiara: {bright_percent:.2f}%, "
                   f"Totale: {total_percent:.2f}%. Stato: {status_text}")
            
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
    
    def display_image(self, cv_image):
        """Visualizza un'immagine OpenCV nel canvas."""
        if cv_image is None:
            return
        
        # Pulisci il canvas
        self.canvas.delete("all")
        
        # Ottieni le dimensioni del canvas
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        # Se il canvas non è ancora stato renderizzato, usa dimensioni di backup
        if canvas_width < 50 or canvas_height < 50:
            canvas_width = 600
            canvas_height = 500
        
        # Dimensioni originali dell'immagine
        height, width = cv_image.shape[:2]
        
        # Calcola il fattore di scala per adattare l'immagine al canvas
        scale = min(canvas_width/width, canvas_height/height)
        new_width = int(width * scale)
        new_height = int(height * scale)
        
        # Ridimensiona l'immagine
        resized = cv2.resize(cv_image, (new_width, new_height))
        
        # Converti da BGR a RGB
        if len(resized.shape) == 3:  # Immagine a colori
            display_image = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        else:  # Immagine in scala di grigi
            display_image = cv2.cvtColor(resized, cv2.COLOR_GRAY2RGB)
        
        # Converti in formato PIL
        pil_image = Image.fromarray(display_image)
        
        # Converti in formato Tkinter
        tk_image = ImageTk.PhotoImage(image=pil_image)
        
        # Salva un riferimento all'immagine (per evitare il garbage collection)
        self.tk_image = tk_image
        
        # Mostra l'immagine nel canvas
        self.canvas.create_image(canvas_width//2, canvas_height//2, image=tk_image)
    
    def change_view(self, event=None):
        """Cambia la visualizzazione in base alla selezione."""
        selected_view = self.view_var.get()
        if selected_view in self.processed_images:
            self.display_image(self.processed_images[selected_view])
            self.current_view = selected_view
            self.log(f"Visualizzazione cambiata: {selected_view}")
    
    def save_current_image(self):
        """Salva l'immagine attualmente visualizzata."""
        if self.current_view not in self.processed_images:
            messagebox.showwarning("Attenzione", "Nessuna immagine da salvare.")
            return
        
        try:
            # Richiedi all'utente dove salvare il file
            file_path = filedialog.asksaveasfilename(
                defaultextension=".jpg",
                filetypes=[
                    ("JPEG", "*.jpg"),
                    ("PNG", "*.png"),
                    ("BMP", "*.bmp"),
                    ("Tutti i file", "*.*")
                ]
            )
            
            if not file_path:
                return
            
            # Salva l'immagine
            cv2.imwrite(file_path, self.processed_images[self.current_view])
            
            self.log(f"Immagine salvata: {os.path.basename(file_path)}")
            messagebox.showinfo("Successo", f"Immagine salvata come {os.path.basename(file_path)}")
            
        except Exception as e:
            self.log(f"Errore durante il salvataggio: {str(e)}")
            messagebox.showerror("Errore", f"Si è verificato un errore: {str(e)}")
    
    def log(self, message):
        """Aggiunge un messaggio al log."""
        # Inserisci il messaggio alla fine del widget di testo
        self.log_text.insert(tk.END, message + "\n")
        # Scrolla automaticamente alla fine
        self.log_text.see(tk.END)
        # Stampa anche sulla console per debug
        print(message)

if __name__ == "__main__":
    main()