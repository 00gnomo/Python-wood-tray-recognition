import cv2
import numpy as np

def detect_color_regions(image, lower_bound, upper_bound, color_contour):
    """Individua le zone di un determinato colore nell'immagine."""
    hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv_image, lower_bound, upper_bound)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    result_image = image.copy()
    cv2.drawContours(result_image, contours, -1, color_contour, 2)
    return result_image, mask

def detect_blue_and_red_regions(image):
    """Trova le zone blu e rosse e le evidenzia."""
    lower_blue = np.array([90, 50, 50])
    upper_blue = np.array([130, 255, 255])
    blue_image, blue_mask = detect_color_regions(image, lower_blue, upper_blue, (0, 255, 0))
    lower_red1 = np.array([0, 50, 50])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([170, 50, 50])
    upper_red2 = np.array([180, 255, 255])
    mask1 = cv2.inRange(cv2.cvtColor(image, cv2.COLOR_BGR2HSV), lower_red1, upper_red1)
    mask2 = cv2.inRange(cv2.cvtColor(image, cv2.COLOR_BGR2HSV), lower_red2, upper_red2)
    red_mask = cv2.bitwise_or(mask1, mask2)
    red_image, _ = detect_color_regions(image, lower_red1, upper_red1, (255, 0, 0))
    red_image, _ = detect_color_regions(red_image, lower_red2, upper_red2, (255, 0, 0))
    return blue_image, blue_mask, red_image, red_mask

def apply_colormap(image_path):
    """Applica una colormap a un'immagine e gestisce la selezione della visualizzazione."""
    colormap_list = [
        cv2.COLORMAP_AUTUMN, cv2.COLORMAP_BONE, cv2.COLORMAP_JET, cv2.COLORMAP_WINTER,
        cv2.COLORMAP_RAINBOW, cv2.COLORMAP_OCEAN, cv2.COLORMAP_SUMMER, cv2.COLORMAP_SPRING,
        cv2.COLORMAP_COOL, cv2.COLORMAP_HSV, cv2.COLORMAP_PINK, cv2.COLORMAP_HOT
    ]
    image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        print(f"Errore: Immagine non trovata nel percorso '{image_path}'.")
        return
    colored_image = cv2.applyColorMap(image, colormap_list[2])
    blue_detected, blue_mask, red_detected, red_mask = detect_blue_and_red_regions(colored_image)
    windows = {
        "Originale": image,
        "Colormap Applicata": colored_image,
        "Zone Blu Evidenziate": blue_detected,
        "Zone Rosse Evidenziate": red_detected,
        "Maschera Blu": blue_mask,
        "Maschera Rossa": red_mask
    }
    selected_window = list(windows.keys())[0]
    cv2.namedWindow("Visualizzazione", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Visualizzazione", 400, 400)
    def update_display(choice):
        nonlocal selected_window
        selected_window = choice
        cv2.imshow("Visualizzazione", windows[selected_window])
    cv2.namedWindow("Menu Selezione", cv2.WINDOW_NORMAL)
    def on_change(val):
        update_display(list(windows.keys())[val])
    cv2.createTrackbar("Seleziona Finestra", "Menu Selezione", 0, len(windows) - 1, on_change)
    update_display(selected_window)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

image_path = "images/v1.jpg"
apply_colormap(image_path)
