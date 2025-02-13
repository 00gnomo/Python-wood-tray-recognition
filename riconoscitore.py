import cv2

image_path = "v5.jpg" # path per l'immagine 

def apply_colormap(image_path, colormap=cv2.COLORMAP_JET):
    # Carica l'immagine in scala di grigi
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    
    if image is None:
        print("Errore: Immagine non trovata.")
        return
    
    # Applica la colormap
    colored_image = cv2.applyColorMap(image, colormap)
    
    # Ottieni le dimensioni originali dell'immagine
    height, width = image.shape[:2]
    
    # Crea finestre ridimensionabili mantenendo le proporzioni
    cv2.namedWindow("Originale", cv2.WINDOW_NORMAL)
    cv2.namedWindow("Colormap Applicata", cv2.WINDOW_NORMAL)
    cv2.namedWindow("Colormap Controller", cv2.WINDOW_NORMAL)
    
    # Imposta le dimensioni iniziali mantenendo il rapporto d'aspetto
    aspect_ratio = width / height
    new_width = 600
    new_height = int(new_width / aspect_ratio)
    
    cv2.resizeWindow("Originale", new_width, new_height)
    cv2.resizeWindow("Colormap Applicata", new_width, new_height)
    
    def update_colormap(val):
        new_colormap = val % 12  # OpenCV ha 12 colormap predefiniti
        new_colored_image = cv2.applyColorMap(image, new_colormap)
        cv2.imshow("Colormap Applicata", new_colored_image)
    
    cv2.createTrackbar("Colormap", "Colormap Controller", colormap, 11, update_colormap)
    
    # Mostra l'immagine originale e quella con la colormap
    cv2.imshow("Originale", image)
    cv2.imshow("Colormap Applicata", colored_image)
    
    # Attendi la chiusura della finestra
    cv2.waitKey(0)
    cv2.destroyAllWindows()

# Percorso dell'immagine da caricare

apply_colormap(image_path)